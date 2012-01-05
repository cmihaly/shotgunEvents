import os

import dshell.shell
shell = dshell.shell.create()

shell.prepend('PATH', os.path.join(os.getcwd(), 'bin'))
shell.prepend('PYTHONPATH', os.path.join(os.getcwd(), 'src'))
shell.prepend('PYTHONPATH', os.path.join(os.getcwd(), 'lib'))

