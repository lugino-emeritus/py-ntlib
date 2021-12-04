"""Control methods in separate threads."""

import logging
import os
import queue
import subprocess
import sys
import threading

__version__ = '0.2.12'

logger = logging.getLogger(__name__)

#-------------------------------------------------------

def _popen_ext(cmd, shell=False):
	subprocess.Popen(cmd, shell=shell, start_new_session=True,
		stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_ENCODING = 'utf-8'

if sys.platform.startswith('linux'):
	def _start_file(cmd):
		_popen_ext(['xdg-open', cmd])

elif sys.platform.startswith('win'):
	_ENCODING = 'cp850'
	def _start_file(cmd):
		os.startfile(cmd)

else:
	logger.warning('fctthread not fully supported on %s', sys.platform)
	def _start_file(cmd):
		raise NotImplementedError(f'_start_file not implemented on {sys.platform}')


def shell_cmd(cmd):
	"""Process a shell command within python."""
	return subprocess.run(cmd, shell=True, encoding=_ENCODING, errors='replace',
		stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout

def start_app(cmd):
	"""Start application or open file."""
	try:
		if not isinstance(cmd, str):
			_popen_ext(cmd)
		elif os.path.isfile(cmd):
			_start_file(cmd)
		else:
			_popen_ext(cmd, shell=True)
		return True
	except Exception:
		logger.exception('not possible to start app, cmd: %s', cmd)
		return False

def start_daemon(target, args=(), kwargs=None):
	"""Start and return daemon thread."""
	t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
	t.start()
	return t

def start_internal_thread(target, args=(), kwargs=None):
	logger.warning('start_internal_thread deprecated, use start_daemon')
	return start_daemon(target, args, kwargs)

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

	def _handle(self):
		while True:
			try:
				while self._should_run and not self._start_flag:
					if self._target():
						break
			except Exception:
				logger.exception('ThreadLoop error calling target')
			with self._lock:
				if self._start_flag:
					self._start_flag = False
					self._should_run = True
				else:
					self._should_run = False
					self._stop_flag = True
					return

	def start(self):
		with self._lock:
			self._start_flag = True
			if self._stop_flag:
				self._t.join()
			if not self.is_alive():
				self._stop_flag = False
				self._t = threading.Thread(target=self._handle, daemon=True)
				self._t.start()

	def stop(self, timeout=None):
		if not self._t:
			return True
		with self._lock:
			self._start_flag = False
			self._should_run = False
		self._t.join(timeout)
		return not self._t.is_alive()

	def join(self, timeout=None):
		if self._t:
			self._t.join(timeout)

	def is_alive(self):
		return self._t.is_alive() if self._t else False


class QueueWorker:
	"""Class to process elements from a queue in separate threads.

	If a thread is not called within timeout seconds it will be stopped.
	"""
	def __init__(self, target, maxthreads=2, *, timeout=10):
		if maxthreads <= 0:
			raise ValueError('number of threads must be at least 1')
		if timeout < 0:
			raise ValueError('timeout must be a nonnegative number')
		self._target = target
		self._maxthreads = maxthreads
		self._timeout = timeout

		self._enabled = False
		self._active_loops = 0
		self._q = queue.Queue(maxthreads)
		self._lock = threading.Lock()
		self._all_done = threading.Condition(self._lock)


	def _handle(self):
		while True:
			try:
				while self._enabled:
					x = self._q.get(timeout=self._timeout)
					try:
						self._target(x)
					except Exception:
						logger.exception('QueueWorker error calling target')
					finally:
						self._q.task_done()
			except queue.Empty:
				pass
			finally:
				with self._lock:
					if not self._enabled or self._active_loops > self._q.unfinished_tasks:
						self._active_loops -= 1
						self._all_done.notify_all()
						return

	def _start_thread(self):
		# self._lock must be locked
		if self._active_loops < self._maxthreads:
			threading.Thread(target=self._handle, daemon=True).start()
			self._active_loops += 1

	def put(self, x, timeout=None):
		self._q.put(x, timeout=timeout)
		with self._lock:
			if self._active_loops < self._q.unfinished_tasks:
				self._start_thread()

	def start(self):
		with self._lock:
			if self._enabled:
				return
			self._enabled = True
			for _ in range(self._q.qsize()):
				self._start_thread()

	def stop(self, timeout=None):
		with self._lock:
			self._enabled = False
		self.join(timeout)
		return not self._active_loops

	def join(self, timeout=None):
		with self._all_done:
			self._all_done.wait_for(lambda: self._active_loops<=0, timeout)

	def is_alive(self):
		return self._enabled or self._active_loops > 0

	def info(self):
		return {'enabled': self._enabled, 'loops': self._active_loops,
			'unfinished': self._q.unfinished_tasks, 'waiting': self._q.qsize()}


class CmpEvent:
	"""Class to receive data from another thread after a successful comparison.

	This data is accessible with CmpEvent.result.
	An optional answer can be sent to the compare thread.
	"""
	def __init__(self):
		self._cond = threading.Condition(threading.Lock())
		self.result = None
		self._cmpval = None
		self._answer = None
		self._waiting = False

	def init(self, cmpval, answer=True):
		with self._cond:
			self.result = None
			self._cmpval = cmpval
			self._answer = answer
			self._waiting = True

	def wait(self, timeout=None):
		"""Return False while waiting for a match, True otherwise."""
		with self._cond:
			return self._cond.wait(timeout) if self._waiting else True

	def compare(self, cmpval, result):
		if self._waiting:
			with self._cond:
				if cmpval == self._cmpval:
					self.result = result
					self._waiting = False
					self._cond.notify_all()
					return self._answer
		return None
