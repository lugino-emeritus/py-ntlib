"""Scheduler to call methods repeatedly."""
import logging
import threading
import time
from heapq import heappop, heappush
from .fctthread import ThreadLoop

__version__ = '0.1.3'

logger = logging.getLogger(__name__)

#-------------------------------------------------------

class _HeapKey:
	# tuples does not work since timestamps may be identical and keys not sortable
	def __init__(self, ts, key):
		self.ts = ts
		self.key = key
	def __lt__(self, other):
		return self.ts < other.ts


class RptSched:
	"""Class to call a function after given delays.

	The scheduler thread is started when jobs are added,
	and stopped if there is nothing left to do.

	RptSched.jobs is a dictionary of all job keys and their options.
	"""
	def __init__(self, target):
		"""Callback function dt = target(key, opt).

		key, opt: params defined in add_job
		dt: delay when it should be called again, if zero the job will be disabled
		"""
		self._target = target
		self.jobs = {}
		self._heap = []
		self._lock = threading.Lock()
		self._job_update = threading.Condition(self._lock)
		self.loop_ctl = ThreadLoop(self._loop)

	def _loop(self):
		with self._lock:
			if not (self.jobs and self._heap):
				logger.debug('RptSched stop loop, jobsize: %d, heapsize: %d', len(self.jobs), len(self._heap))
				self._heap.clear()
				return True  # stop thread loop
			hk = heappop(self._heap)
			ts = hk.ts
			key = hk.key
			if (dt := ts - time.monotonic()) > 0.0:
				if self._job_update.wait(dt if dt < 150.0 else 150.0) or dt > 150.0:
					if key in self.jobs:
						heappush(self._heap, hk)
					return
			try:
				opt = self.jobs[key]
			except KeyError:
				return
		try:
			dt = self._target(key, opt)
			if dt is not None and dt < 0.0:
				raise ValueError(f'call returned negative dt: {dt}')
		except:
			logger.exception('RptSched error calling target with key: %s, opt: %s', key, opt)
			dt = None
		with self._lock:
			if not dt:
				logger.debug('RptSched remove job %s', key)
				self.jobs.pop(key, None)
				return
			now = time.monotonic()
			hk.ts = now + dt
			heappush(self._heap, hk)
		if (delay := now - (ts + dt)) >= 1.0:
			logger.critical('RptSched loop %.3fs too slow, job: %s, heapsize: %d', delay, key, len(self._heap))

	def add_job(self, key=None, opt=None, *, delay=10.0):
		if key is None:
			if opt is None:
				raise TypeError("missing 'key' or 'opt' argument")
			key = format(int(time.monotonic() * 1000.0) & (2**32-1), '08X')
		if delay < 0.0:
			raise ValueError("delay must be nonnegative")
		with self._lock:
			if key in self.jobs:
				raise KeyError(f'job with key {key} already exists')
			self.jobs[key] = opt
			heappush(self._heap, _HeapKey(time.monotonic() + delay, key))
			self._job_update.notify()
		self.loop_ctl.start()
		return key

	def remove_job(self, key):
		with self._lock:
			del self.jobs[key]
			self._job_update.notify()

	def clear_jobs(self):
		"""Remove all jobs and stop scheduler."""
		with self._lock:
			self.jobs.clear()
			self._job_update.notify()

#-------------------------------------------------------

glob_sched = None

def _call_dt(key, opt):
	r = key()
	return r if opt is None else opt

def add_job(cb, dt=None, *, delay=None):
	"""Add callback job to global scheduler.
	If dt is None the returned value of cb is used as dt.
	"""
	global glob_sched
	if delay is None:
		if dt is None:
			raise TypeError("argument 'dt' or 'delay' must be a positive number")
		delay = dt
	if glob_sched is None:
		glob_sched = RptSched(_call_dt)
		logger.info('global scheduler initialized')
	return glob_sched.add_job(cb, dt, delay=delay)

def remove_job(cb):
	"""Remove a global callback job."""
	glob_sched.remove_job(cb)
