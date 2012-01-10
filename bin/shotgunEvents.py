#!/usr/bin/env python
#
# Init file for Shotgun event daemon
#
# chkconfig: 345 99 00
# description: Shotgun event daemon
#
### BEGIN INIT INFO
# Provides: shotgunEvent
# Required-Start: $network
# Should-Start: $remote_fs
# Required-Stop: $network
# Should-Stop: $remote_fs
# Default-Start: 2 3 4 5
# Short-Description: Shotgun event daemon
# Description: Shotgun event daemon
### END INIT INFO

"""
For an overview of shotgunEvents, please see raw documentation in the docs
folder or an html compiled version at:

http://shotgunsoftware.github.com/shotgunEvents
"""
from shotgunevents import version
from shotgunevents import log
from shotgunevents import daemonizer
from shotgunevents import config
from shotgunevents import plugin

import sys
import os
import argparse
import time
import socket
import traceback

try:
    import cPickle as pickle
except ImportError:
    import pickle

import shotgun as sg

__version__ = version.version()
__version_info__ = (0, 9)

class EventDaemonError(Exception):
    pass

class Engine(daemonizer.Daemon):
    """
    The engine holds the main loop of event processing.
    """

    def __init__(self, configPath):
        """
        """
        self._continue = True
        self._eventIdData = {}

        # Read/parse the config
        self.config = config.Config(configPath)

        # Get config values
        self._pluginCollections = [plugin.PluginCollection(self, s) 
                                   for s in self.config.getPluginPaths()]
        self._sg = sg.Shotgun(
            self.config.getShotgunURL(),
            self.config.getEngineScriptName(),
            self.config.getEngineScriptKey()
        )
        self._max_conn_retries = self.config.getint('daemon', 'max_conn_retries')
        self._conn_retry_sleep = self.config.getint('daemon', 'conn_retry_sleep')
        self._fetch_interval = self.config.getint('daemon', 'fetch_interval')
        self._use_session_uuid = self.config.getboolean('shotgun', 'use_session_uuid')

        self.log = log.engineLogger(self.config)
        self.setEmailsOnLogger(self.log, True)
        super(Engine, self).__init__('shotgunEvent', self.config.getEnginePIDFile())

    def start(self, daemonize=True):
        if not daemonize:
            # Setup the stdout logger
            log.addStdOut()

        super(Engine, self).start(daemonize)

    def setEmailsOnLogger(self, logger, emails):
        log.setEmailsOnLogger(self.config, logger, emails)
        
    def _run(self):
        """
        Start the processing of events.

        The last processed id is loaded up from persistent storage on disk and
        the main loop is started.
        """
        # TODO: Take value from config
        socket.setdefaulttimeout(60)

        # Notify which version of shotgun api we are using
        self.log.info('Using Shotgun version %s' % sg.__version__)

        try:
            for collection in self._pluginCollections:
                collection.load()

            self._loadEventIdData()

            self._mainLoop()
        except KeyboardInterrupt, err:
            self.log.warning('Keyboard interrupt. Cleaning up...')
        except Exception, err:
            self.log.critical('Crash!!!!! Unexpected error (%s) in main loop.\n\n%s', type(err), 
                              traceback.format_exc(err))

    def _loadEventIdData(self):
        """
        Load the last processed event id from the disk

        If no event has ever been processed or if the eventIdFile has been
        deleted from disk, no id will be recoverable. In this case, we will try
        contacting Shotgun to get the latest event's id and we'll start
        processing from there.
        """
        eventIdFile = self.config.getEventIdFile()

        if eventIdFile and os.path.exists(eventIdFile):
            try:
                fh = open(eventIdFile)
                try:
                    self._eventIdData = pickle.load(fh)

                    # Provide event id info to the plugin collections. Once
                    # they've figured out what to do with it, ask them for their
                    # last processed id.
                    for collection in self._pluginCollections:
                        state = self._eventIdData.get(collection.path)
                        if state:
                            collection.setState(state)
                except pickle.UnpicklingError:
                    fh.close()

                    # Backwards compatibility:
                    # Reopen the file to try to read an old-style int
                    fh = open(eventIdFile)
                    line = fh.readline().strip()
                    if line.isdigit():
                        # The _loadEventIdData got an old-style id file containing a single
                        # int which is the last id properly processed.
                        lastEventId = int(line)
                        self.log.debug('Read last event id (%d) from file.', lastEventId)
                        for collection in self._pluginCollections:
                            collection.setState(lastEventId)
                fh.close()
            except OSError, err:
                raise EventDaemonError('Could not load event id from file.\n\n%s' % 
                                       traceback.format_exc(err))
        else:
            # No id file?
            # Get the event data from the database.
            conn_attempts = 0
            lastEventId = None
            while lastEventId is None:
                order = [{'column':'id', 'direction':'desc'}]
                try:
                    result = self._sg.find_one("EventLogEntry", filters=[], fields=['id'], 
                                               order=order)
                except (sg.ProtocolError, sg.ResponseError, socket.err), err: #@UndefinedVariable  
                    conn_attempts = self._checkConnectionAttempts(conn_attempts, str(err))
                except Exception, err:
                    msg = "Unknown error: %s" % str(err)
                    conn_attempts = self._checkConnectionAttempts(conn_attempts, msg)
                else:
                    lastEventId = result['id']
                    self.log.info('Last event id (%d) from the Shotgun database.', lastEventId)

                    for collection in self._pluginCollections:
                        collection.setState(lastEventId)

            self._saveEventIdData()

    def _mainLoop(self):
        """
        Run the event processing loop.

        General behavior:
        - Load plugins from disk - see L{load} method.
        - Get new events from Shotgun
        - Loop through events
        - Loop through each plugin
        - Loop through each callback
        - Send the callback an event
        - Once all callbacks are done in all plugins, save the eventId
        - Go to the next event
        - Once all events are processed, wait for the defined fetch interval time and start over.

        Caveats:
        - If a plugin is deemed "inactive" (an error occured during
          registration), skip it.
        - If a callback is deemed "inactive" (an error occured during callback
          execution), skip it.
        - Each time through the loop, if the pidFile is gone, stop.
        """
        self.log.debug('Starting the event processing loop.')
        while self._continue:
            # Process events
            for event in self._getNewEvents():
                for collection in self._pluginCollections:
                    collection.process(event)
                self._saveEventIdData()

            time.sleep(self._fetch_interval)

            # Reload plugins
            for collection in self._pluginCollections:
                collection.load()
                
            # Make sure that newly loaded events have proper state.
            self._loadEventIdData()

        self.log.debug('Shuting down event processing loop.')

    def _cleanup(self):
        self._continue = False

    def _getNewEvents(self):
        """
        Fetch new events from Shotgun.

        @return: Recent events that need to be processed by the engine.
        @rtype: I{list} of Shotgun event dictionaries.
        """
        nextEventId = None
        for newId in [coll.getNextUnprocessedEventId() for coll in self._pluginCollections]:
            if newId is not None and (nextEventId is None or newId < nextEventId):
                nextEventId = newId

        if nextEventId is not None:
            filters = [['id', 'greater_than', nextEventId - 1]]
            fields = ['id', 'event_type', 'attribute_name', 'meta', 'entity', 'user', 'project', 
                      'session_uuid']
            order = [{'column':'id', 'direction':'asc'}]
    
            conn_attempts = 0
            while True:
                try:
                    return self._sg.find("EventLogEntry", filters=filters, fields=fields, 
                                         order=order, filter_operator='all')
                except (sg.ProtocolError, sg.ResponseError, socket.error), err:
                    conn_attempts = self._checkConnectionAttempts(conn_attempts, str(err))
                except Exception, err:
                    msg = "Unknown error: %s" % str(err)
                    conn_attempts = self._checkConnectionAttempts(conn_attempts, msg)

        return []

    def _saveEventIdData(self):
        """
        Save an event Id to persistant storage.

        Next time the engine is started it will try to read the event id from
        this location to know at which event it should start processing.
        """
        eventIdFile = self.config.getEventIdFile()

        if eventIdFile is not None:
            for collection in self._pluginCollections:
                self._eventIdData[collection.path] = collection.getState()

            for dummy_colPath, state in self._eventIdData.items():
                if state:
                    try:
                        fh = open(eventIdFile, 'w')
                        pickle.dump(self._eventIdData, fh)
                        fh.close()
                    except OSError, err:
                        self.log.error('Can not write event id data to %s.\n\n%s', eventIdFile, 
                                       traceback.format_exc(err))
                    break
            else:
                self.log.warning('No state was found. Not saving to disk.')

    def _checkConnectionAttempts(self, conn_attempts, msg):
        conn_attempts += 1
        if conn_attempts == self._max_conn_retries:
            self.log.error('Unable to connect to Shotgun (attempt %s of %s): %s', conn_attempts, 
                           self._max_conn_retries, msg)
            conn_attempts = 0
            time.sleep(self._conn_retry_sleep)
        else:
            self.log.warning('Unable to connect to Shotgun (attempt %s of %s): %s', conn_attempts, 
                             self._max_conn_retries, msg)
        return conn_attempts


def parseArgs():
    '''
        Get the command line args
    '''
    parser = argparse.ArgumentParser(description='Run Shotgun Event Daemon')
    parser.add_argument('-s', '--server', dest='server', help='Shotgun Server Host',
                        default="From Config File")
    parser.add_argument('-c', '--config', dest='configFile',
                        action = 'store', 
                        help = 'Config File Location',
                        default=False)
    parser.add_argument('op', choices = ['start', 'stop', 'restart', 'foreground'], 
                        help = 'daemon operation')
    return parser.parse_args()

def main():
    cmdOptions = parseArgs()
    daemon = Engine(_getConfigPath())

    # Find the function to call on the daemon
    func = getattr(daemon, cmdOptions.op, None)

    # If no function was found, report error.
    if func is None:
        print "Unknown command: %s" % cmdOptions.op 
        return 2

    # Call the requested function
    func()
    return 0

def _getConfigPath():
    """
    Get the path of the shotgunEventDaemon configuration file.
    """
    paths = ['/etc']

    # Get the current path of the daemon script
    scriptPath = sys.argv[0]
    if scriptPath != '' and scriptPath != '-c':
        # Make absolute path and eliminate any symlinks if any.
        scriptPath = os.path.abspath(scriptPath)
        scriptPath = os.path.realpath(scriptPath)

        # Add the script's directory to the paths we'll search for the config.
        paths[:0] = [os.path.dirname(scriptPath)]

    # Search for a config file.
    for path in paths:
        path = os.path.join(path, 'shotgunEventDaemon.conf')
        if os.path.exists(path):
            return path

    # No config file was found
    raise EventDaemonError('Config path not found!')


if __name__ == '__main__':
    sys.exit(main())
