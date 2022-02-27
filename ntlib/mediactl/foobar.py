"""Module to control foobar2000.

Available commands are:
play, pause, next, prev, stop
volup, voldown, volreset, mute
start, exit
"""
import sys
from .. import imp as ntimp
from ..fctthread import start_app as _start_app

__version__ = '0.1.0'

_START_CMD = ntimp.load_config('mediactl')['foobar']

if sys.platform.startswith('linux'):
	_ROOT = ('wine', _START_CMD)
elif sys.platform.startswith('win'):
	_ROOT = (_START_CMD,)
else:
	raise ImportError('platform not supported')

#-------------------------------------------------------

def cmd(cmd, *, root=_ROOT):
	if cmd.isalpha():
		if cmd in {'play', 'pause', 'next', 'prev', 'stop', 'exit'}:
			cmd = '/' + cmd
		elif cmd.startswith('vol'):
			c = cmd[3:]
			if c == 'up':
				cmd = '/command:Up'
			elif c == 'down':
				cmd = '/command:Down'
			elif c == 'reset':
				cmd = '/command:Set to -0 dB'
		elif cmd == 'mute':
			cmd = '/command:Mute'
		elif cmd == 'start':
			_start_app(root)
			return
		else:
			raise ValueError(f'cmd {cmd} unknown')
	_start_app(root + (cmd,))
