'''
Created on Jan 6, 2012

@author: cmihaly
'''

import logging.handlers

EMAIL_FORMAT_STRING = """Time: %(asctime)s
Logger: %(name)s
Path: %(pathname)s
Function: %(funcName)s
Line: %(lineno)d

%(message)s"""

class CustomSMTPHandler(logging.handlers.SMTPHandler):
    """
    A custom SMTPHandler subclass that will adapt it's subject depending on the
    error severity.
    """

    LEVEL_SUBJECTS = {
        logging.ERROR: 'ERROR - Shotgun event daemon.',
        logging.CRITICAL: 'CRITICAL - Shotgun event daemon.',
    }

    def getSubject(self, record):
        subject = logging.handlers.SMTPHandler.getSubject(self, record)
        if record.levelno in self.LEVEL_SUBJECTS:
            return subject + ' ' + self.LEVEL_SUBJECTS[record.levelno]
        return subject

def engineLogger(config):
    # Setup the logger for the main engine
    if config.getLogMode() == 0:
        # Set the root logger for file output.
        rootLogger = logging.getLogger()
        rootLogger.config = config
        _setFilePathOnLogger(rootLogger, config.getLogFile())
        print config.getLogFile()

        # Set the engine logger for email output.
        log = logging.getLogger('engine')
    else:
        # Set the engine logger for file and email output.
        log = logging.getLogger('engine')
        log.config = config
        _setFilePathOnLogger(log, config.getLogFile())

    log.setLevel(config.getLogLevel())
    return log

def addStdOut():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logging.getLogger().addHandler(handler)

def setEmailsOnLogger(config, logger, emails):
    # Configure the logger for email output
    _removeHandlersFromLogger(logger, logging.handlers.SMTPHandler)

    if emails is False:
        return

    smtpServer = config.getSMTPServer()
    fromAddr = config.getFromAddr()
    emailSubject = config.getEmailSubject()
    username = config.getEmailUsername()
    password = config.getEmailPassword()

    if emails is True:
        toAddrs = config.getToAddrs()
    elif isinstance(emails, (list, tuple)):
        toAddrs = emails
    else:
        msg = 'Argument emails should be True to use the default addresses, False to not send any emails or a list of recipient addresses. Got %s.'
        raise ValueError(msg % type(emails))

    _addMailHandlerToLogger(logger, smtpServer, fromAddr, toAddrs, emailSubject, username, password)

def pluginLogger(engine, name):
    # Setup the plugin's logger
    logger = logging.getLogger('plugin.' + name)
    logger.config = engine.config
    engine.setEmailsOnLogger(logger, True)
    logger.setLevel(engine.config.getLogLevel())
    if engine.config.getLogMode() == 1:
        _setFilePathOnLogger(logger, engine.config.getLogFile('plugin.' + name))
    return logger

def callbackLogger(engine, loggerName):
    # TODO: Get rid of this protected member access
    logger = logging.getLogger(loggerName)
    logger.config = engine.config
    return logger



def _setFilePathOnLogger(logger, path):
    # Remove any previous handler.
    _removeHandlersFromLogger(logger, logging.handlers.TimedRotatingFileHandler)

    # Add the file handler
    handler = logging.handlers.TimedRotatingFileHandler(path, 'midnight', backupCount=10)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


def _removeHandlersFromLogger(logger, handlerTypes=None):
    """
    Remove all handlers or handlers of a specified type from a logger.

    @param logger: The logger who's handlers should be processed.
    @type logger: A logging.Logger object
    @param handlerTypes: A type of handler or list/tuple of types of handlers
        that should be removed from the logger. If I{None}, all handlers are
        removed.
    @type handlerTypes: L{None}, a logging.Handler subclass or
        I{list}/I{tuple} of logging.Handler subclasses.
    """
    for handler in logger.handlers:
        if handlerTypes is None or isinstance(handler, handlerTypes):
            logger.removeHandler(handler)


def _addMailHandlerToLogger(logger, smtpServer, fromAddr, toAddrs, emailSubject, username=None, password=None):
    """
    Configure a logger with a handler that sends emails to specified
    addresses.

    The format of the email is defined by L{LogFactory.EMAIL_FORMAT_STRING}.

    @note: Any SMTPHandler already connected to the logger will be removed.

    @param logger: The logger to configure
    @type logger: A logging.Logger instance
    @param toAddrs: The addresses to send the email to.
    @type toAddrs: A list of email addresses that will be passed on to the
        SMTPHandler.
    """
    if smtpServer and fromAddr and toAddrs and emailSubject:
        if username and password:
            mailHandler = CustomSMTPHandler(smtpServer, fromAddr, toAddrs, emailSubject, (username, password))
        else:
            mailHandler = CustomSMTPHandler(smtpServer, fromAddr, toAddrs, emailSubject)

        mailHandler.setLevel(logging.ERROR)
        mailFormatter = logging.Formatter(EMAIL_FORMAT_STRING)
        mailHandler.setFormatter(mailFormatter)

        logger.addHandler(mailHandler)

