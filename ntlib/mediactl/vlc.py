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

import ntlib.imp as ntimp
import ntlib.tsocket as tsocket
from ntlib.fctthread import start_app as _start_app

__version__ = '0.1.1'

logger = logging.getLogger(__name__)

_START_CMD, _PREF_PORT = ntimp.load_config('mediactl')['vlc']
_TIMEOUT_MIN = 0.01

#-------------------------------------------------------

class VideoLan():
	def __init__(self):
		self.sock = None

	def _init_sock(self, addr):
		self.sock = tsocket.Socket(timeout=_TIMEOUT_MIN)
		self.sock.maxtimeout = 0.1
		self.sock.connect(addr)

	if sys.platform.startswith('win'):
		def _clear_buffer(self):
			self.sock.clear_buffer(_TIMEOUT_MIN, esc_data=b'\n')
	else:
		def _clear_buffer(self):
			self.sock.clear_buffer(_TIMEOUT_MIN)

	def recv_lines(self, max_lines=10):
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

	def cmd(self, cmd):
		self._clear_buffer()
		self.sock.send(cmd.encode() + b'\n')
		return self.recv_lines()

	def online_check(self):
		if self.sock is None:
			return False
		try:
			if self.cmd('status'):
				return True
		except OSError as e:
			logger.debug('OS Error in vlc online_check: %r', e)
		self.sock = None
		return False

	def start(self):
		if self.online_check():
			return
		try:
			self._init_sock(('127.0.0.1', _PREF_PORT))
			if self.online_check():
				logger.info('connected to already started vlc on %s', self.sock.getpeername())
				return
		except (tsocket.Timeout, OSError):
			self.sock.close()

		addr = tsocket.find_free_addr(('127.0.0.1', _PREF_PORT), 0)
		_start_app((_START_CMD, '--extraintf', 'rc', '--rc-host', f'{addr[0]}:{addr[1]}'))
		logger.log(logging.INFO if addr[1]==_PREF_PORT else logging.WARNING, 'vlc using addr %s', addr)

		err = None
		for i in range(10):
			time.sleep(1)
			try:
				self._init_sock(addr)
				return
			except (tsocket.Timeout, OSError) as e:
				err = e
		self.sock = None
		if err:
			raise ConnectionError(f'connection to vlc failed: {err!r}')

	def exit(self):
		if self.sock is None:
			return
		try:
			cmd = 'quit' if sys.platform.startswith('win') else 'shutdown'
			self.cmd(cmd)
		except OSError as e:
			logger.info('OSError in vlc exit: %r', e)
		finally:
			self.sock = None

	def jump(self, dt):
		t = int(self.cmd('get_time')[0])
		return self.cmd('seek {}'.format(t + dt))


con = VideoLan()

def cmd(cmd, param=None):
	if cmd[0].isalpha():
		if cmd in {'play', 'pause', 'next', 'prev', 'stop'}:
			pass
		elif cmd.startswith('vol'):
			c = cmd[3:]
			if c == 'up':
				cmd = 'volup 1'
			elif c == 'down':
				cmd = 'volup -1'
			elif c == 'reset':
				cmd = 'volume 256'
		elif cmd == 'mute':
			cmd = 'volume 0'
		elif cmd.startswith('jump'):
			try:
				if param and cmd == 'jump':
					param = int(param)
				else:
					param = {'jumpf': 10, 'jumpb': -10}[cmd]
			except (ValueError, KeyError):
				raise ValueError(f'cmd {cmd} with param {param} not possible')
			con.jump(param)
		elif cmd == 'start':
			con.start()
			return
		elif cmd == 'exit':
			con.exit()
			return
		else:
			raise ValueError(f'cmd {cmd} unknown')
	con.cmd(cmd)
