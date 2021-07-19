"""Playback sounds or check input volume."""

import logging
import numpy as np
import os
import queue
import sounddevice as sd
import soundfile as sf
import threading

__version__ = '0.2.0'

_DTYPE = 'float32'  # float32 is highly recommended

_BLOCKTIMEFRAC = 20  # 48000 / 20 = 2400 -> results in blocksize = 4096
_MAX_BLOCKSIZE = 8192
_BUFFERSIZE = 16
_BUFFERFILL = 4
assert _BUFFERFILL <= _BUFFERSIZE

logger = logging.getLogger(__name__)

#-------------------------------------------------------

def _alt_file(filename):
	return filename if os.path.exists(filename) else os.path.join(os.path.dirname(__file__), filename)


class FilePlayer:
	def __init__(self, filename, *, device=None, ch_num=None):
		"""Class to handle audio playback on specific device and channels."""
		self._filename = _alt_file(filename)
		self._device = device
		self._q = queue.Queue(maxsize=_BUFFERSIZE)
		self._should_run = False
		self._t = None
		self._stopped = threading.Event()
		self.stream = None

		self._file = sf.SoundFile(self._filename)
		self._samplerate = self._file.samplerate
		try:
			self._ch_in_num = self._file.channels
			self._blocksize = min(2 ** (1 + self._file.samplerate // _BLOCKTIMEFRAC).bit_length(), _MAX_BLOCKSIZE)
			self._q_timeout = 0.1 +  _BUFFERSIZE * self._blocksize / self._samplerate
			test_channels = [self._ch_in_num, None]
			if ch_num not in test_channels:
				test_channels.insert(0, ch_num)
			for ch in test_channels:
				try:
					self._init_stream(ch)
					break
				except sd.PortAudioError as e:
					err = e
			else:
				raise err
		except:
			self._file.close()
			raise

		self._ch_out_num = self.stream.channels
		if ch_num and ch_num != self._ch_out_num:
			logger.warning('%d channels not work, using %d channels', ch_num, self._ch_out_num)
		self._vol_array = np.eye(self._ch_in_num, self._ch_out_num, dtype=_DTYPE)
		logger.debug('initialized: %s', self.info())

	def _init_stream(self, ch_num):
		logger.debug('init stream')
		if self.stream is not None:
			self.close()
		self.stream = sd.OutputStream(
			samplerate=self._samplerate, blocksize=self._blocksize,
			device=self._device, channels=ch_num, dtype=_DTYPE,
			callback=self._callback, finished_callback=self._stopped.set)

	def _reinit_file(self):
		if self._file.closed:
			logger.debug('reinit file')
			self._file = sf.SoundFile(self._filename)
		elif not self._q.empty():
			if self._file.tell() == self._q.qsize() * self._blocksize:
				return
		logger.debug('soundfile seek to 0')
		self._file.seek(0)
		self._fill_buffer(force=True)

	def _fill_buffer(self, force=False):
		logger.debug('filling buffer')
		if force:
			with self._q.mutex:
				self._q.queue.clear()
		for _ in range(_BUFFERFILL - self._q.qsize()):
			data = self._get_modified_sound_data()
			self._q.put(data, timeout=0)
			if data is None:
				break

	def _callback(self, outdata, frames, time, status):
		if status:
			logger.error('FilePlayer callback status: %s', status)
			raise sd.CallbackAbort
		try:
			data = self._q.get(timeout=0)
		except queue.Empty:
			logger.warning('Buffer is empty: increase buffersize?')
			outdata[:] = 0
			return
		if data is None:
			outdata[:] = 0
			raise sd.CallbackStop
		outdata[:] = data

	def reinit(self, force=False):
		if force:
			logger.debug('force reinit')
			self.close()
			self.join(self._q_timeout)
		elif self.stream and self.stream.active:
			return
		self._reinit_file()
		if not self.stream:
			self._init_stream(self._ch_out_num)
		elif not self.stream.stopped:
			self.stream.stop()

	def _play(self):
		self._should_run = True
		self._stopped.clear()
		self.reinit()
		try:
			try:
				self.stream.start()
			except Exception as e:
				logger.warning('failed to start stream, try again: %r', e)
				self.reinit(force=True)
				self.stream.start()
			while self._should_run:
				data = self._get_modified_sound_data()
				if data is None:
					self._q.put(0, timeout=self._q_timeout)
					self._q.put(None, timeout=self._q_timeout)
					break
				self._q.put(data, timeout=self._q_timeout)
			else:
				self.stream.stop()
			self._stopped.wait(self._q_timeout)
			self._should_run = False
		except Exception as e:
			if self._should_run or not isinstance(e, queue.Full):
				logger.exception('exception occured in _play: %r', e)
				self.close()

	def is_alive(self):
		return self._t.is_alive() if self._t else False

	def join(self, timeout=None):
		if self._t:
			self._t.join(timeout)

	def play(self):
		if self.is_alive():
			return False
		self._t = threading.Thread(target=self._play, daemon=True)
		self._t.start()
		return self.is_alive()

	def stop(self, timeout=None):
		if not self.is_alive():
			return True
		self._should_run = False
		self.join(timeout)
		return not self.is_alive()

	def close(self):
		self._should_run = False
		if self.stream:
			self.stream.close()
			self.stream = None
		if self._file:
			self._file.close()

	def get_channel_num(self):
		return self._ch_in_num, self._ch_out_num

	def set_vol_array(self, vol_array):
		"""numpy array which maps input channels to output channels."""
		vol_array = np.array(vol_array, dtype=_DTYPE)
		if vol_array.shape != self.get_channel_num():
			raise ValueError(f'vol_array (shape {vol_array.shape}) must have shape {self.get_channel_num()}')
		self._vol_array = vol_array

	def _get_modified_sound_data(self):
		try:
			in_array = self._file.read(self._blocksize, dtype=_DTYPE, always_2d=True)
			if not in_array.shape[0]:
				return None
			if in_array.shape[0] != self._blocksize:
				in_array.resize(self._blocksize, in_array.shape[1])
			return np.matmul(in_array, self._vol_array)
		except Exception as e:
			logger.info('reading data failed: %r', e)
			return None

	def info(self):
		return {'file_init': not self._file.closed, 'stream_init': bool(self.stream), 'is_alive': self.is_alive(),
			'ch_in_num': self._ch_in_num, 'ch_out_num': self._ch_out_num,
			'samplerate': self._samplerate, 'blocksize': self._blocksize,
			'buffersize': _BUFFERSIZE, 'buffer_filled': self._q.qsize()}


def create_vol_array(ch_in_out_num, mono=False, outputs=None, vol=1):
	(ch_in_num, ch_out_num) = ch_in_out_num
	vol_array = np.zeros((ch_in_num, ch_out_num), dtype=_DTYPE)
	for i in range(ch_out_num):
		if not outputs or i in outputs:
			vol_array[i % ch_in_num, i] = vol
	if mono:
		a = np.ones((ch_in_num, ch_in_num), dtype=_DTYPE) / ch_in_num
		vol_array = np.matmul(a, vol_array)
	logging.debug('vol_array:\n%s', vol_array)
	return vol_array


def new_playback(filename, *, device=None, ch_num=None, outputs=None, mono=False, vol=1):
	"""Return FilePlayer configured to use a given device and channels."""
	fp = FilePlayer(filename, device=device, ch_num=ch_num)
	vol_array = create_vol_array(fp.get_channel_num(), mono, outputs, vol)
	fp.set_vol_array(vol_array)
	fp.reinit()
	return fp

def config_ps(filename, device=None, ch_out_num=None, mono=False, ch_out=None, vol=1):
	logger.warning('config_ps deprecated, use new_playback')
	return new_playback(filename, device=device, ch_num=ch_out_num, outputs=ch_out, mono=mono, vol=vol)

#-------------------------------------------------------

class InputVolume:
	def __init__(self, vol_cb, *, device=None, delay=0.5):
		"""Call vol_cb(volume) approx. each delay seconds, an input device can be selected."""
		self.vol = 0
		self._vol_cb = vol_cb
		self._delay = delay
		self._device = device
		self._init_stream()

	def _init_stream(self):
		logger.debug('init stream')
		self.stream = sd.InputStream(device=self._device, channels=1,
			callback=self._callback, blocksize=2048, dtype=_DTYPE)
		self._vol_scale = self.stream.blocksize / (self.stream.samplerate * self._delay)
		if self._vol_scale > 0.5:
			self.close()
			raise ValueError(f'delay is too short for used configuration')
		self._cb_repeat = int(1 / self._vol_scale - 0.5)
		self._cb_cnt = self._cb_repeat

	def _callback(self, indata, frames, time, status):
		if status:
			logger.error('InputVolume callback status: %s', status)
			raise sd.CallbackAbort
		vol = np.average(np.abs(indata))
		self.vol += (vol - self.vol) * self._vol_scale
		if self._cb_cnt > 0:
			self._cb_cnt -= 1
		else:
			self._cb_cnt = self._cb_repeat
			try:
				self._vol_cb(self.vol)
			except Exception:
				logger.exception('vol_cb raised an error, close stream')
				raise sd.CallbackAbort from None

	def start(self):
		if self.stream is None:
			self._init_stream()
		elif self.stream.active:
			return
		self.stream.start()

	def stop(self):
		if self.stream is not None:
			self.stream.stop()

	def close(self):
		if self.stream is not None:
			self.stream.close()
			self.stream = None

	def is_alive(self):
		return self.stream.active if self.stream else False

	def info(self):
		return {'stream_init': bool(self.stream), 'is_alive': self.is_alive(),
			'samplerate': self.stream.samplerate if self.stream else None,
			'blocksize': self.stream.blocksize if self.stream else None}
