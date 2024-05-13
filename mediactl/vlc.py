"""Module to control vlc media player.

Available commands are:
play, pause, next, prev, stop
volup, voldown, volreset, mute
start, exit
jumpf, jumpb: jump 10 seconds forward or back
jump t seconds, t can be negative
"""

import logging
import sys
import time
from typing import Any
from .. import imp as ntimp
from .. import tsocket
from ..fctthread import start_app

__version__ = '0.1.3'

logger = logging.getLogger(__name__)

_START_CMD, _PREF_PORT = ntimp.load_config('mediactl')['vlc']

#-------------------------------------------------------

class VideoLan():
	def __init__(self):
		self.sock = None

	def _init_sock(self, addr: tuple[str, int]) -> None:
		self.sock = tsocket.create_connection(addr, timeout=0.1)
		self.sock.settimeout(0.01)

	def _close_sock(self) -> None:
		if self.sock:
			self.sock.close()
		self.sock = None

	if sys.platform.startswith('win'):
		def _clear_buffer(self) -> None:
			self.sock.clear_buffer(0.01, esc_data=b'\n')
	else:
		def _clear_buffer(self) -> None:
			self.sock.clear_buffer(0.01)

	def recv_lines(self, max_lines: int = 10) -> list[str]:
		lines = []
		try:
			for _ in range(max_lines):
				r = self.sock.recv_until(8192)
				if not r:
					break
				lines.append(r.decode())
		except tsocket.Timeout:
			pass
		return lines

	def _cmd(self, cmd: str) -> None:
		self.sock.send(cmd.encode() + b'\n')

	def cmd(self, cmd: str) -> list[str]:
		self._clear_buffer()
		self._cmd(cmd)
		return self.recv_lines()

	def online_check(self) -> bool:
		if self.sock is None:
			return False
		try:
			if self.cmd('status'):
				return True
		except OSError as e:
			logger.debug('OS Error in vlc online_check: %r', e)
		self._close_sock()
		return False

	def start(self) -> None:
		if self.online_check():
			return
		try:
			self._init_sock(('127.0.0.1', _PREF_PORT))
			if self.online_check():
				logger.info('connected to already started vlc on %s', self.sock.getpeername())
				return
		except (tsocket.Timeout, OSError):
			self._close_sock()

		addr = tsocket.find_free_addr(('127.0.0.1', _PREF_PORT), 0)
		start_app((_START_CMD, '--extraintf', 'rc', '--rc-host', f'{addr[0]}:{addr[1]}'))
		logger.log(logging.INFO if addr[1]==_PREF_PORT else logging.WARNING, 'vlc using addr %s', addr)

		err = None
		for _ in range(10):
			time.sleep(1)
			try:
				self._init_sock(addr)
				return
			except (tsocket.Timeout, OSError) as e:
				self._close_sock()
				err = e
		raise ConnectionError(f'connection to vlc failed: {err!r}')

	def exit(self) -> None:
		if self.sock is None:
			return
		try:
			cmd = 'quit' if sys.platform.startswith('win') else 'shutdown'
			self.cmd(cmd)
		except OSError as e:
			logger.info('OSError in vlc exit: %r', e)
		finally:
			self._close_sock()

	def jump(self, dt: float) -> None:
		self._clear_buffer()
		self._cmd('get_time')
		t = int(self.recv_lines(1)[0])
		self._cmd(f'seek {t+dt}')
		self._clear_buffer()


con = VideoLan()

_DEFAULT_CMDS = {
	'play': 'play',
	'pause': 'pause',
	'next': 'next',
	'prev': 'prev',
	'stop': 'stop',
	'volup': 'volup 1',
	'voldown': 'volup -1',
	'volreset': 'volume 256',
	'mute': 'volume 0'
}

def cmd(cmd: str, param: Any = None) -> None:
	if c := _DEFAULT_CMDS.get(cmd):
		con.cmd(c)
		return
	if cmd.startswith('jump'):
		if param and cmd == 'jump':
			param = int(param)
		else:
			param = {'jumpf': 10, 'jumpb': -10}[cmd]
		con.jump(param)
	elif cmd == 'start':
		con.start()
	elif cmd == 'exit':
		con.exit()
	else:
		raise ValueError(f'cmd {cmd} unknown')
