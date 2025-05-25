"""Module to control foobar2000.

Available commands are:
play, pause, next, prev, stop
volup, voldown, volreset, mute
start, exit
"""
__version__ = '0.1.2'

import sys
from os import path as _osp
from .. import imp as ntimp
from ..fctthread import start_app

def _load_config() -> None:
	global _ROOT, _QUEUE_PATH
	data = ntimp.load_config('mediactl')['foobar']
	if isinstance(data, str):
		data = (data,)
	_QUEUE_PATH = data[1] if len(data) > 1 else ''
	if sys.platform.startswith('linux'):
		_ROOT = ('wine', data[0])
	elif sys.platform.startswith('win'):
		_ROOT = (data[0],)
	else:
		raise ImportError('platform not supported')

_load_config()

# -----------------------------------------------------------------------------

def add_queue(filepath: str, root: tuple[str, ...] =_ROOT) -> None:
	filepath = filepath.replace('\\', '/')  # to be compatible on linux / windows
	if '/' not in filepath:
		filepath = _osp.normpath(_osp.join(_QUEUE_PATH, filepath))
	start_app(root + ('/context_command:Add to playback queue', filepath))

def cmd(cmd: str, *, root: tuple[str, ...] = _ROOT) -> None:
	if cmd[0] != '/':
		if cmd.startswith('add '):
			return add_queue(cmd[4:], root)
		elif cmd.startswith('vol'):
			c = cmd[3:]
			if c == 'up':
				cmd = '/command:Up'
			elif c == 'down':
				cmd = '/command:Down'
			elif c == 'reset':
				cmd = '/command:Set to -0 dB'
		elif cmd in {'play', 'pause', 'next', 'prev', 'stop', 'exit'}:
			cmd = '/' + cmd
		elif cmd == 'mute':
			cmd = '/command:Mute'
		elif cmd == 'start':
			start_app(root)
			return
		else:
			raise ValueError(f'cmd {cmd} unknown')
	start_app(root + (cmd,))
