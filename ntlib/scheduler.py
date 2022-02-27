"""Scheduler to call methods repeatedly."""
import logging
import threading
import time
from heapq import heappop, heappush
from .fctthread import ThreadLoop

__version__ = '0.1.0'

logger = logging.getLogger(__name__)

#-------------------------------------------------------

class _NOJOB:
	pass

class _HeapKey:
	def __init__(self, ts, key):
		self.ts = ts
		self.key = key
	def __lt__(self, other):
		return self.ts < other.ts


class RptSched:
	"""Class to call functions after given times.

	The scheduler thread is started when jobs are added,
	and stopped if there is nothing left to do.

	RptSched.jobs is a dictionary of all job keys and there options.
	"""
	def __init__(self, cb):
		"""Callback function dt = cb(key, opt).

		key, opt: params defined in add_job
		dt: delay when it should be called again
		"""
		self.call = cb
		self.jobs = {}
		self._heap = []
		self._lock = threading.Lock()
		self._new_job = threading.Condition(self._lock)
		self.loop_ctl = ThreadLoop(self._loop)

	def _loop(self):
		if not self._heap:
			assert not self.jobs
			logger.debug('RptSched has no jobs, stop loop')
			return True
		with self._lock:
			hk = heappop(self._heap)
			ts = hk.ts
			key = hk.key
			if (dt := ts - time.monotonic()) > 0.0:
				if self._new_job.wait(dt if dt < 90.0 else 90.0) or dt > 90.0:
					heappush(self._heap, hk)
					return
			opt = self.jobs.get(key, _NOJOB)
		if opt is _NOJOB:
			return
		try:
			dt = self.call(key, opt)
		except Exception:
			logger.exception('RptSched job %s failed', key)
			dt = None
		with self._lock:
			if not dt:
				self.jobs.pop(key, None)
				return
			now = time.monotonic()
			hk.ts = now + dt
			heappush(self._heap, hk)
		if (delay := now - (ts + dt)) >= 1.0:
			logger.critical('RptSched loop %.3fs too slow, job: %s, heapsize: %d', delay, key, len(self._heap))

	def add_job(self, key=None, opt=None, *, delay=10):
		if key is None and opt is None:
			raise TypeError("at least one of 'key' or 'opt' must be defined")
		with self._lock:
			if key is None:
				key = format(int(time.monotonic() * 1000.0) & (2**32-1), '08X')
			if key in self.jobs:
				raise KeyError(f'job with key {key} already exist')
			self.jobs[key] = opt
			heappush(self._heap, _HeapKey(time.monotonic() + delay, key))
			self._new_job.notify()
		self.loop_ctl.start()
		return key

	def remove_job(self, key):
		with self._lock:
			del self.jobs[key]

	def clear_jobs(self):
		"""Remove all jobs and stop scheduler."""
		with self._lock:
			self.jobs.clear()


def _call_dt(key, opt):
	key()
	return opt

glob_sched = RptSched(_call_dt)

def add_job(cb, dt):
	"""Add callback job to global scheduler."""
	return glob_sched.add_job(cb, dt, delay=dt)
def remove_job(cb):
	"""Remove a global callback job."""
	glob_sched.remove_job(cb)
