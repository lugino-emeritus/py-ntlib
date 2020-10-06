import logging
import os
import subprocess as _subp
import sys
import threading

__version__ = '0.1.4'

logger = logging.getLogger(__name__)

#-------------------------------------------------------

def _popen_ext(cmd, shell=False):
	_subp.Popen(cmd, shell=shell, start_new_session=True,
		stdin=_subp.DEVNULL, stdout=_subp.DEVNULL, stderr=_subp.DEVNULL)

if sys.platform.startswith('win'):
	def _start_file(cmd):
		os.startfile(cmd)
elif sys.platform.startswith('linux'):
	def _start_file(cmd):
		_popen_ext(['xdg-open', cmd])
else:
	raise ImportError('platform {} not available'.format(sys.platform))


(CMD_AUTO, CMD_EXT, CMD_SYS, CMD_FILE) = range(4)

def start_app(cmd, *, cmd_type=CMD_AUTO):
	"""Starts application or file."""
	if cmd_type == CMD_AUTO:
		if isinstance(cmd, str):
			cmd_type = CMD_FILE if os.path.isfile(cmd) else CMD_SYS
		else:
			cmd_type = CMD_EXT
	try:
		if cmd_type == CMD_EXT:
			_popen_ext(cmd)
		elif cmd_type == CMD_SYS:
			_popen_ext(cmd, shell=True)
		elif cmd_type == CMD_FILE:
			_start_file(cmd)
		else:
			raise ValueError('unknown cmd_type')
		return True
	except Exception:
		logger.exception('not possible to start program (type={}) with command {}'.format(cmd_type, cmd))
		return False

def shell_cmd(cmd):
	"""Processes a shell command and returns the output."""
	return _subp.run(cmd, shell=True, stdin=_subp.DEVNULL,
		stdout=_subp.PIPE, stderr=_subp.STDOUT).stdout.decode(errors='replace')


def start_internal_thread(target, args=(), kwargs={}):
	"""Starts and returns a daemon thread."""
	t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
	t.start()
	return t

#-------------------------------------------------------

class ThreadLoop:
	"""Class to control function in separate thread.

	Loops over target(cont_task, req_stop) until calling stop or the target calls req_stop.
	Example:

	def target(cont_task, req_stop):
		i = 0
		while cont_task():
			i += 1
			print(i)
			time.sleep(1)
			if i >= 5:
				req_stop()
		print('done')
	thread_loop = ThreadLoop(target)
	"""

	def __init__(self, target):
		self._t = None
		self._target = target

		self._lock = threading.Lock()
		self._should_run = False
		self._start_flag = False
		self._stop_error = None

	@property
	def stop_error(self):
		return self._stop_error

	def join(self, timeout=None, *, check=True):
		if self._t:
			self._t.join(timeout)
		if check and self._stop_error is not None:
			raise self._stop_error

	def is_alive(self):
		return self._t.is_alive() if self._t else False

	def is_healthy(self):
		return self._stop_error is None and self.is_alive() == self._should_run


	def _cont_task(self):
		if self._start_flag:
			self._start_flag = False
		return self._should_run

	def _req_stop(self):
		with self._lock:
			if not self._start_flag:
				self._should_run = False
			return not self._should_run

	def _handle(self):
		self._should_run = True
		self._stop_error = None
		try:
			self._target(self._cont_task, self._req_stop)
		except Exception as e:
			logger.exception('thread stopped unexpected')
			self._stop_error = e


	def start(self):
		if self.is_alive():
			if self._start_flag:
				return
			with self._lock:
				self._start_flag = True
				if self._should_run:
					return
			self._t.join(1)
		with self._lock:
			if not self.is_alive():
				self._t = start_internal_thread(self._handle)

	def stop(self, timeout=None):
		if self._req_stop():
			self._t.join(timeout)
		return not self.is_alive()
