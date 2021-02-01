"""Control function in separate thread."""

import logging
import os
import subprocess as _subp
import sys
import threading

__version__ = '0.1.5'

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


def shell_cmd(cmd):
	"""Processes a shell command and returns the output."""
	return _subp.run(cmd, shell=True, stdin=_subp.DEVNULL,
		stdout=_subp.PIPE, stderr=_subp.STDOUT).stdout.decode(errors='replace')


def start_app(cmd):
	"""Starts application or file."""
	try:
		if not isinstance(cmd, str):
			_popen_ext(cmd)
		elif os.path.isfile(cmd):
			_start_file(cmd)
		else:
			_popen_ext(cmd, shell=True)
		return True
	except Exception:
		logger.exception('not possible to start app with command: %s', cmd)
		return False


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
