"""Control methods in separate threads."""
__version__ = '0.2.24'

import logging
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------

_ENCODING = 'utf-8'

def _popen_ext(cmd: str|Sequence[str], shell: bool = False):
	subprocess.Popen(cmd, shell=shell, start_new_session=True,
		stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if sys.platform.startswith('linux'):
	def _start_file(cmd: str) -> None:
		_popen_ext(('xdg-open', cmd))
elif sys.platform.startswith('win'):
	_ENCODING = 'cp850'
	def _start_file(cmd: str) -> None:
		os.startfile(cmd)
else:
	logger.warning('fctthread not fully supported on %s', sys.platform)
	def _start_file(cmd: str) -> None:
		raise NotImplementedError(f'_start_file not implemented on {sys.platform}')


def shell_cmd(cmd: str|Sequence[str]) -> str:
	"""Execute command and return stdout.

	- cmd can be a string or a iterable containing args: (exe, arg1, ...)
	- stderr is redirected to stdout
	"""
	return subprocess.run(cmd, shell=isinstance(cmd, str), encoding=_ENCODING, errors='replace',
		stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout

def start_app(cmd: str|Sequence[str]) -> bool:
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

def start_daemon(target: Callable, args: Iterable[Any] = (),
		kwargs: dict[str|Any]|None = None) -> threading.Thread:
	"""Start and return daemon thread."""
	t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
	t.start()
	return t

# -----------------------------------------------------------------------------

class _FakeThread:
	def __init__(self, target: Callable[[], Any], *, daemon: bool = True, activate: bool = False):
		self._target = target
		if not daemon:
			raise ValueError('FakeThread must be a daemon')
		self._state = threading.Event()
		if not activate:
			self._state.set()

	def run(self) -> None:
		self._state.clear()
		try:
			self._target()
		finally:
			self._state.set()

	def join(self, timeout: float|None = None) -> None:
		self._state.wait(timeout)

	def is_alive(self) -> bool:
		return not self._state.is_set()

class ThreadLoop:
	"""Class to control function in a daemon thread.

	Loops over target() until calling stop or the target returns True.
	"""
	def __init__(self, target: Callable[[], bool|None]):
		self._target = target
		self._start_flag = False
		self._should_run = False
		self._stop_flag = False
		self._t = _FakeThread(self._handle)
		self._lock = threading.Lock()

	def _handle(self) -> None:
		logger.debug('ThreadLoop start handle of %s', self._target)
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
					logger.debug('ThreadLoop stop handle of %s', self._target)
					self._should_run = False
					# stop flag is used for the rare case when this handle stops
					# but the thread is still alive and start is called
					self._stop_flag = True
					return

	def run(self) -> None:
		"""Run target as loop in the thread of the caller.

		Raise a RuntimeError if loop is already alive.
		Can be stopped by a KeyboardInterrupt or calling stop() from an other thread.
		"""
		with self._lock:
			if self._t.is_alive():
				raise RuntimeError('ThreadLoop already active')
			self._start_flag = True
			self._stop_flag = False
			self._t = _FakeThread(self._handle, activate=True)
		self._t.run()

	def start(self) -> None:
		with self._lock:
			self._start_flag = True
			if self._stop_flag:
				self._t.join()
			elif self._t.is_alive():
				return
			self._stop_flag = False
			self._t = threading.Thread(target=self._handle, daemon=True)
			self._t.start()

	def stop(self, timeout: float|None = None) -> bool:
		with self._lock:
			self._start_flag = False
			self._should_run = False
		self._t.join(timeout)
		return not self._t.is_alive()

	def join(self, timeout: float|None = None) -> None:
		self._t.join(timeout)

	def is_alive(self) -> bool:
		return self._t.is_alive()

# -----------------------------------------------------------------------------

class QueueWorker:
	"""Class to process elements from a queue in separate threads.

	If a thread is not called within timeout seconds it will be stopped.
	"""
	def __init__(self, target: Callable[[Any], None],
			maxthreads: int = 2, *, timeout: float = 10.0, qsize: int|None = None):
		if maxthreads <= 0:
			raise ValueError('number of threads must be at least 1')
		if timeout < 0.0:
			raise ValueError('timeout must be nonnegative')
		self._target = target
		self._maxthreads = maxthreads
		self.timeout = timeout

		self._enabled = False
		self._active_loops = 0
		self._q = queue.Queue(qsize or maxthreads)
		self._lock = threading.Lock()
		self._all_done = threading.Condition(self._lock)

	def _handle(self) -> None:
		while True:
			try:
				while self._enabled:
					arg = self._q.get(timeout=self.timeout)
					try:
						self._target(arg)
					except Exception:
						logger.exception('QueueWorker error calling target with %s', arg)
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

	def _start_thread(self) -> None:
		assert self._lock.locked()
		if self._enabled and self._active_loops < self._maxthreads:
			threading.Thread(target=self._handle, daemon=True).start()
			self._active_loops += 1

	def put(self, arg: Any, timeout: float|None = None) -> None:
		self._q.put(arg, timeout=timeout)
		with self._lock:
			if self._active_loops < self._q.unfinished_tasks:
				self._start_thread()

	def start(self) -> None:
		with self._lock:
			if self._enabled:
				return
			self._enabled = True
			for _ in range(self._q.qsize()):
				self._start_thread()

	def stop(self, timeout: float|None = None) -> bool:
		with self._lock:
			self._enabled = False
		self.join(timeout)
		return not self._active_loops

	def join(self, timeout: float|None = None) -> None:
		with self._all_done:
			self._all_done.wait_for(lambda: self._active_loops<=0, timeout)

	def is_alive(self) -> bool:
		return self._enabled or self._active_loops > 0

	def info(self) -> dict[str, Any]:
		return {'enabled': self._enabled, 'loops': self._active_loops,
			'unfinished': self._q.unfinished_tasks, 'waiting': self._q.qsize()}


class CmpEvent:
	"""Class to receive data from another thread after a successful comparison.

	This data is accessible in the variable result.
	An optional answer can be sent to the compare thread.
	"""
	def __init__(self, cmpfct: Callable[[Any, Any], bool] = lambda x, y: x==y):
		"""Init method accepts an alternative boolean compare function:
		cmpfct(init_value, compare_value), equality check (==) by default.
		"""
		self._cmpfct = cmpfct
		self.result: Any = None
		self._cmpval = None
		self._answer = None
		self._waiting = False
		self._cond = threading.Condition(threading.Lock())

	def init(self, cmpval: Any, answer: Any = True) -> None:
		with self._cond:
			self.result = None
			self._cmpval = cmpval
			self._answer = answer
			self._waiting = True

	def wait(self, timeout: float|None = None) -> bool:
		"""Return False while waiting for a match, True otherwise."""
		with self._cond:
			return self._cond.wait(timeout) if self._waiting else True

	def compare(self, cmpval: Any, result: Any) -> Any:
		if self._waiting:
			with self._cond:
				if self._cmpfct(self._cmpval, cmpval):
					self.result = result
					self._waiting = False
					self._cond.notify_all()
					return self._answer
		return None
