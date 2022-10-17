"""Playback sounds or check input volume."""

import logging
import numpy as np
import os
import queue
import sounddevice as sd
import soundfile as sf
import threading

__version__ = '0.2.8'

_DTYPE = 'float32'  # float32 is highly recommended
_BLOCKTIMEFRAC = 20  # 48000 / 20 = 2400 -> results in blocksize = 4096
_MAX_BLOCKSIZE = 8192
_BUFFERSIZE = 16
_BUFFERFILL = 4
assert _BUFFERFILL <= _BUFFERSIZE

logger = logging.getLogger(__name__)

#-------------------------------------------------------

def _alt_file(filename):
	if os.path.isfile(filename):
		return filename
	if os.path.basename(filename) == filename:
		alt = os.path.join(os.path.dirname(__file__), 'sounds', filename)
		if not os.path.splitext(alt)[1]:
			alt += '.wav'
		if os.path.isfile(alt):
			return alt
	raise FileNotFoundError(f'no such sound file: {filename}')

def _check_output(device, channels, samplerate):
	try:
		sd.check_output_settings(device=device, channels=channels, dtype=_DTYPE, samplerate=samplerate)
		return None
	except sd.PortAudioError as e:
		return e


class FilePlayer:
	def __init__(self, filename, *, device=None, channels=None):
		"""Class to handle audio playback on specific device and channels."""
		self._file = sf.SoundFile(filename)
		try:
			if channels and not _check_output(device, channels, self._file.samplerate):
				ch = channels
			elif (self._file.channels != channels
					and not _check_output(device, self._file.channels, self._file.samplerate)):
				ch = self._file.channels
			elif e := _check_output(device, None, self._file.samplerate):
				raise e
			else:
				ch = None
		except:
			self._file.close()
			raise

		self._t = None
		self._should_run = False
		self._blocksize = 1 << (self._file.samplerate // _BLOCKTIMEFRAC).bit_length()
		if self._blocksize > _MAX_BLOCKSIZE:
			self._blocksize = _MAX_BLOCKSIZE
		self._q = queue.Queue(maxsize=_BUFFERSIZE)
		self._timeout = 0.1 +  _BUFFERSIZE * self._blocksize / self._file.samplerate

		self._stopped = threading.Event()
		self._stream = sd.OutputStream(
			samplerate=self._file.samplerate, blocksize=self._blocksize,
			device=device, channels=ch, dtype=_DTYPE,
			callback=self._callback, finished_callback=self._stopped.set)
		if channels and channels != self._stream.channels:
			logger.warning('use %d output channels instead of %d', self._stream.channels, channels)
		self._vol_array = np.eye(self._file.channels, self._stream.channels, dtype=_DTYPE)
		logger.debug('FilePlayer initialized: %s', self.info())


	def __del__(self):
		logger.debug('del FilePlayer')
		try:
			for a in ('_stream', '_file'):
				if obj := getattr(self, a, None):
					obj.close()
		except Exception as e:
			logger.error('FilePlayer __del__ failed: %r', e)


	@property
	def channel_shape(self):
		return (self._file.channels, self._stream.channels)

	@property
	def vol_array(self):
		return self._vol_array

	def set_vol_array(self, vol_array):
		"""numpy array which maps input channels to output channels."""
		if vol_array.shape != self.channel_shape:
			raise ValueError(f'vol_array (shape {vol_array.shape}) must have shape {self.channel_shape}')
		self._vol_array = vol_array

	def init_buffer(self):
		if self._stream.closed:
			raise RuntimeError('FilePlayer closed')
		elif self._stream.active:
			return
		self._seek_buffer()


	def _seek_buffer(self):
		if qsize := self._q.qsize():
			if self._file.tell() == qsize * self._blocksize:
				return
			with self._q.mutex:
				self._q.queue.clear()
		logger.debug('fill buffer from %s', self._file.name)
		self._file.seek(0)
		for _ in range(_BUFFERFILL):
			data = self._read_sound_data()
			self._q.put(data, block=False)
			if data is None:
				break

	def _read_sound_data(self):
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

	def _play(self):
		self._should_run = True
		self._stopped.clear()
		self._seek_buffer()
		try:
			self._stream.start()
			while self._should_run:
				data = self._read_sound_data()
				if data is None:
					self._q.put(0, timeout=self._timeout)
					self._q.put(None, timeout=self._timeout)
					break
				self._q.put(data, timeout=self._timeout)
			else:
				self._stream.stop()
			self._should_run = False
			self._stopped.wait(self._timeout)
			self._stream.stop()
		except Exception as e:
			if self._should_run or not self._stream.closed:
				logger.exception('exception occured in _play: %r', e)
			self.close()

	def _callback(self, outdata, frames, time, status):
		if status:
			logger.error('FilePlayer callback status: %s', status)
			raise sd.CallbackAbort
		try:
			data = self._q.get(block=False)
		except queue.Empty:
			logger.warning('Buffer is empty: increase buffersize?')
			outdata[:] = 0
			return
		if data is None:
			outdata[:] = 0
			raise sd.CallbackStop
		outdata[:] = data


	def is_alive(self):
		return self._t.is_alive() if self._t else False

	def join(self, timeout=None):
		if self._t:
			self._t.join(timeout)

	def play(self):
		if self.is_alive() or self._stream.closed:
			return False
		self._t = threading.Thread(target=self._play, daemon=True)
		self._t.start()
		return True

	def stop(self, timeout=None):
		if not self.is_alive():
			return True
		self._should_run = False
		self.join(timeout)
		return not self.is_alive()

	def close(self):
		self._should_run = False
		self._stream.close()
		self._file.close()

	def info(self):
		return {'initialized': not self._stream.closed and not self._file.closed, 'is_alive': self.is_alive(),
			'in_channels': self._file.channels, 'out_channels': self._stream.channels,
			'samplerate': self._file.samplerate, 'blocksize': self._blocksize,
			'buffersize': _BUFFERSIZE, 'buffer_filled': self._q.qsize(),
			'file': self._file.name}

#-------------------------------------------------------

class InputVolume:
	def __init__(self, vol_cb, *, device=None, delay=0.5):
		"""Call vol_cb(volume) approx. each delay seconds, an input device can be selected."""
		self.vol = 0.0
		self._vol_cb = vol_cb
		self._stream = sd.InputStream(device=device, channels=1,
			callback=self._callback, blocksize=2048, dtype=_DTYPE)
		self._device = self._stream.device
		self._samplerate = self._stream.samplerate
		self._blocksize = self._stream.blocksize
		self._vol_scale = self._blocksize / (self._samplerate * delay)
		if self._vol_scale > 0.5:
			self._stream.close()
			raise ValueError(f'delay is too short for given samplerate and blocksize')
		self._cb_repeat = int(1 / self._vol_scale - 0.5)
		self._cb_cnt = self._cb_repeat

	def __del__(self):
		logger.debug('del InputVolume')
		try:
			if obj := getattr(self, '_stream', None):
				obj.close()
		except Exception as e:
			logger.error('InputVolume __del__ failed: %r', e)


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
			except:
				logger.exception('vol_cb raised error, stop stream')
				raise sd.CallbackStop from None

	def start(self):
		if self._stream is None:
			self._stream = sd.InputStream(device=self._device, channels=1,
				callback=self._callback, blocksize=self._blocksize, dtype=_DTYPE)
		elif self._stream.active == self._stream.stopped:
			raise RuntimeError('InputVolume not healthy')
		elif self._stream.active:
			return
		self._stream.start()

	def stop(self):
		if self._stream is not None:
			self._stream.stop()
			self._stream.close()
			self._stream = None
			self.vol = 0.0

	def is_alive(self):
		return self._stream.active if self._stream else False

	def healthy(self):
		return self._stream is None or self._stream.active != self._stream.stopped

	def info(self):
		return {'initialized': bool(self._stream), 'is_alive': self.is_alive(), 'healthy': self.healthy(),
			'samplerate': self._samplerate, 'blocksize': self._blocksize,
			'delay': self._cb_repeat * self._blocksize / self._samplerate}

#-------------------------------------------------------

def list_devices():
	return [d.strip() for d in str(sd.query_devices()).split('\n')]

def create_vol_array(channel_shape, mono=False, outputs=None, vol=1.0):
	ch_in_num, ch_out_num = channel_shape
	vol_array = np.zeros(channel_shape, dtype=_DTYPE)
	for i in range(ch_out_num):
		if not outputs or i in outputs:
			vol_array[i % ch_in_num, i] = vol
	if mono:
		a = np.ones((ch_in_num, ch_in_num), dtype=_DTYPE) / ch_in_num
		vol_array = a @ vol_array
	logger.debug('vol_array:\n%s', vol_array)
	return vol_array

def new_playback(filename, *, device=None, channels=None, outputs=None, mono=False, vol=1.0):
	"""Return FilePlayer configured to use a given device and channels."""
	fp = FilePlayer(_alt_file(filename), device=device, channels=channels)
	vol_array = create_vol_array(fp.channel_shape, mono, outputs, vol)
	fp.set_vol_array(vol_array)
	fp.init_buffer()
	return fp
