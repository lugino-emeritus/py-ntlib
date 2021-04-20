"""Control methods in separate threads."""

import logging
import os
import queue
import subprocess as _subp
import sys
import threading

__version__ = '0.2.4'

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
	raise ImportError(f'platform {sys.platform} not available')


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

def start_internal_thread(target, args=(), kwargs=None):
	"""Starts and returns a daemon thread."""
	t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
	t.start()
	return t

#-------------------------------------------------------

class ThreadLoop:
	"""Class to control function in a daemon thread.

	Loops over target() until calling stop or the target returns True.
	"""
	def __init__(self, target):
		self._t = None
		self._target = target
		self._lock = threading.Lock()

		self._start_flag = False
		self._should_run = False
		self._stop_flag = False

	@property
	def target(self):
		return self._target

	def _handle(self):
		while True:
			try:
				while self._should_run and not self._start_flag:
					if self._target():
						logger.debug('ThreadLoop stop request')
						break
			except Exception:
				logger.exception('ThreadLoop callback error')
			with self._lock:
				if self._start_flag:
					self._start_flag = False
					self._should_run = True
				else:
					self._should_run = False
					self._stop_flag = True
					return

	def is_alive(self):
		return self._t.is_alive() if self._t else False

	def join(self, timeout=None):
		if self._t:
			self._t.join(timeout)

	def start(self):
		with self._lock:
			self._start_flag = True
			if self._stop_flag:
				self.join()
			if not self.is_alive():
				self._stop_flag = False
				self._t = start_internal_thread(self._handle)

	def stop(self, timeout=None):
		with self._lock:
			self._start_flag = False
			self._should_run = False
		self.join(timeout)
		return not self.is_alive()

#-------------------------------------------------------

class CmpEvent:
	"""Class to receive data from another thread after a successful comparison.

	This data is accessible with obj.result.
	An optional answer can be sent to the compare thread.
	"""
	def __init__(self):
		self._cond = threading.Condition(threading.Lock())
		self._waiting = False
		self._answer = None
		self._cmpval = None
		self.result = None

	def init(self, cmpval, answer=True):
		with self._cond:
			self.result = None
			self._answer = answer
			self._cmpval = cmpval
			self._waiting = True

	def wait(self, timeout=None):
		"""Returns False while waiting for a match, True otherwise."""
		with self._cond:
			if self._waiting:
				return self._cond.wait(timeout)
			return True

	def compare(self, cmpval, result):
		if self._waiting:
			with self._cond:
				if cmpval == self._cmpval:
					self.result = result
					self._cond.notify_all()
					self._waiting = False
					return self._answer
		return None

#-------------------------------------------------------

class QueueWorker:
	"""Class to process elements from a queue in separate threads.

	If a thread is not called within timeout seconds it will be stopped.
	"""
	def __init__(self, target, maxthreads=2, *, timeout=30):
		self._target = target
		if maxthreads <= 0:
			raise ValueError('number of threads needs to be at least 1')
		self._maxthreads = maxthreads
		if timeout < 0:
			raise ValueError('timeout must be a nonnegative number')
		self._timeout = timeout

		self._enabled = False
		self._active_loops = 0
		self._q = queue.Queue(maxthreads)
		self._lock = threading.Lock()
		self._all_done = threading.Condition(self._lock)

	@property
	def target(self):
		return self._target

	def _start_thread(self):
		assert self._lock.locked()
		threading.Thread(target=self._handle, daemon=True).start()
		self._active_loops += 1

	def _handle(self):
		while True:
			sick = True
			try:
				while self._enabled:
					x = self._q.get(timeout=self._timeout)
					try:
						self._target(x)
					except Exception as e:
						logger.warning('QueueWorker callback error: %r', e)
					finally:
						self._q.task_done()
				sick = False
			except queue.Empty:
				sick = False
			finally:
				with self._lock:
					if sick or not self._enabled or self._active_loops > self._q.unfinished_tasks:
						self._active_loops -= 1
						self._all_done.notify_all()
						return

	def put(self, x, timeout=None):
		self._q.put(x, timeout=timeout)
		if self._enabled:
			with self._lock:
				if self._active_loops < self._maxthreads and self._active_loops < self._q.unfinished_tasks:
					self._start_thread()

	def join(self, timeout=None):
		with self._all_done:
			self._all_done.wait_for(lambda:self._active_loops<=0, timeout)

	def is_alive(self):
		return self._enabled

	def start(self):
		with self._lock:
			if self._enabled:
				return
			qsize = self._q.qsize()
			if self._active_loops < 0 or (qsize and self._active_loops > 0):
				logger.critical('QueueWorker start: %d active loops, %d waiting', self._active_loops, qsize)
				self._active_loops = 0
			self._enabled = True
			for _ in range(qsize):
				self._start_thread()

	def stop(self, timeout=None):
		with self._lock:
			self._enabled = False
		self.join(timeout)
		return self._active_loops == 0

	def info(self):
		return {'enabled': self._enabled, 'loops': self._active_loops,
			'unfinished': self._q.unfinished_tasks, 'waiting': self._q.qsize()}
