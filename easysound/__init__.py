"""Playback sounds or check input volume."""
__version__ = '0.3.3'

import logging
import numpy as np
import os
import queue
import sounddevice as sd
import soundfile as sf
import threading
from collections.abc import Callable, Sequence
from typing import Any

_DTYPE = 'float32'  # float32 is highly recommended
_BLOCKTIMEFRAC = 20  # 48000 / 20 = 2400 -> results in blocksize = 4096
_MAX_BLOCKSIZE = 8192
_BUFFERSIZE = 16
_BUFFERFILL = 4
assert _BUFFERFILL <= _BUFFERSIZE

DeviceType = str|None

logger = logging.getLogger(__name__)

#-------------------------------------------------------

def _alt_file(filename: str) -> str:
	if os.path.isfile(filename):
		return filename
	if os.path.basename(filename) == filename:
		alt = os.path.join(os.path.dirname(__file__), 'sounds', filename)
		if not os.path.splitext(alt)[1]:
			alt += '.wav'
		if os.path.isfile(alt):
			return alt
	raise FileNotFoundError(f'no such sound file: {filename}')

def _check_output(device: DeviceType, channels: int|None, samplerate: int) -> Exception|None:
	try:
		sd.check_output_settings(device=device, channels=channels, dtype=_DTYPE, samplerate=samplerate)
		return None
	except sd.PortAudioError as e:
		return e


class FilePlayer:
	def __init__(self, filename: str, *, device: DeviceType = None, channels: int|None = None, prepare: bool = True):
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

		self._should_run = False
		self._q = queue.Queue(maxsize=_BUFFERSIZE)
		self._stopped = threading.Event()
		self._blocksize = 1 << (self._file.samplerate // _BLOCKTIMEFRAC).bit_length()
		if self._blocksize > _MAX_BLOCKSIZE:
			self._blocksize = _MAX_BLOCKSIZE
		self._timeout = 0.1 + self._blocksize / self._file.samplerate

		self._init_stream(device, ch)
		self._device = self._stream.device
		self._outchannels = self._stream.channels
		self._vol_array = np.eye(self._file.channels, self._outchannels, dtype=_DTYPE)

		if channels and channels != self._outchannels:
			logger.warning('use %d output channels instead of %d', self._outchannels, channels)
		if prepare:
			self._init_buffer()
		logger.debug('FilePlayer initialized: %s', self.info())

	def __del__(self):
		logger.debug('del FilePlayer')
		try:
			self._file.close()
			if self._stream.active:
				logger.critical('FilePlayer stream active in __del__')
				self._should_run = False
			else:
				self._stream.close()
		except Exception as e:
			if isinstance(e, sd.PortAudioError):
				if e.args and e.args[-1] == -10000:
					# port audio not initialized
					logger.debug('FilePlayer.__del__: %r', e)
					return
			logger.exception('FilePlayer.__del__ failed')

	def _init_stream(self, device: DeviceType, channels: int|None) -> None:
		self._t = threading.Thread(target=self._play, daemon=True)
		self._stream = sd.OutputStream(
			samplerate=self._file.samplerate, blocksize=self._blocksize,
			device=device, channels=channels, dtype=_DTYPE,
			callback=self._callback, finished_callback=self._stopped.set)
		logger.debug('stream initialized')

	def _init_buffer(self) -> None:
		self._file.seek(0)
		with self._q.mutex:
			self._q.queue.clear()
		for _ in range(_BUFFERFILL):
			data = self._read_sound_data()
			self._q.put(data, block=False)
			if data is None:
				break
		logger.debug('buffer initialized')

	@property
	def closed(self) -> bool:
		return self._file.closed
	@property
	def channel_shape(self) -> tuple[int, int]:
		return (self._file.channels, self._outchannels)
	@property
	def vol_array(self) -> np.ndarray:
		return self._vol_array

	def prepare(self) -> None:
		self._init_stream(self._device, self._outchannels)
		self._init_buffer()

	def _callback(self, outdata: np.ndarray, frames: Any, time: Any, status: Any) -> None:
		if status:
			logger.error('FilePlayer callback status: %s', status)
			raise sd.CallbackAbort
		if not self._should_run:
			outdata[:] = 0
			raise sd.CallbackStop
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


	def set_vol_array(self, vol_array: np.ndarray) -> None:
		"""numpy array from input channels to output channels."""
		if vol_array.shape != self.channel_shape:
			raise ValueError(f'vol_array (shape {vol_array.shape}) must have shape {self.channel_shape}')
		self._vol_array = vol_array
		if not self._t.is_alive():
			self._init_buffer()

	def _read_sound_data(self) -> np.ndarray|None:
		try:
			in_array = self._file.read(self._blocksize, dtype=_DTYPE, always_2d=True)
			if not in_array.shape[0]:
				return None
			if in_array.shape[0] != self._blocksize:
				in_array.resize(self._blocksize, in_array.shape[1])
			return np.matmul(in_array, self._vol_array)
		except Exception as e:
			logger.warning('reading data failed: %r', e)
			return None

	def _play(self) -> None:
		self._should_run = True
		self._stopped.clear()
		try:
			self._stream.start()
			while self._should_run:
				data = self._read_sound_data()
				if data is None:
					self._q.put(0, timeout=self._timeout)
					logging.debug('end of soundfile')
					break
				self._q.put(data, timeout=self._timeout)
			else:
				logging.info('should_run set to false')
			self._q.put(None, timeout=self._timeout)
			self._stopped.wait(_BUFFERSIZE * self._timeout)
			self._should_run = False
		except Exception as e:
			if not self._should_run and isinstance(e, queue.Full):
				logger.debug('should_run is false with error %r', e)
				return
			logger.exception('exception occured in FilePlayer._play')
			self._file.close()
		finally:
			if self._stream.active:
				logger.warning('stream still active, but reached end')
			self._stream.close()

	def play(self) -> bool:
		"""Play the sound."""
		if self._t.is_alive() or self.closed:
			return False
		if self._file.tell() != self._q.qsize() * self._blocksize:
			self.prepare()
		self._t.start()
		return True

	def stop(self, timeout: float|None = None) -> bool:
		self._should_run = False
		if self._t.is_alive():
			self._t.join(timeout)
		return not self._t.is_alive()

	def close(self) -> None:
		self._should_run = False
		self._file.close()

	def join(self, timeout: float|None = None) -> None:
		self._t.join(timeout)

	def is_alive(self) -> bool:
		return self._t.is_alive()

	def info(self) -> dict[str, Any]:
		return {'initialized': not self._stream.closed, 'closed': self._file.closed,
			'is_alive': self._t.is_alive(),  'file': self._file.name,
			'in_channels': self._file.channels, 'out_channels': self._outchannels,
			'samplerate': self._file.samplerate, 'blocksize': self._blocksize,
			'buffersize': _BUFFERSIZE, 'buffer_filled': self._q.qsize()}

#-------------------------------------------------------

class InputVolume:
	def __init__(self, vol_cb: Callable[[float], None], *, device: DeviceType = None,
			channels: int = 1, inputs: int|Sequence[int] = (0,), delay: float = 0.5):
		"""Call vol_cb(volume) periodically (approx. delay sec.), an input can be selected."""
		self.vol = 0.0
		self._vol_cb = vol_cb
		self._stream = sd.InputStream(device=device, channels=channels,
			callback=self._callback, blocksize=2048, dtype=_DTYPE)
		self._device = self._stream.device
		self._samplerate = self._stream.samplerate
		self._blocksize = self._stream.blocksize
		self._channels = self._stream.channels
		self._inputs = (inputs,) if isinstance(inputs, int) else tuple(sorted(inputs))
		if self._inputs[-1] >= self._channels:
			raise ValueError(f'Inputs {inputs} not available, device has only {self._channels} channels')
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

	def _callback(self, indata: np.ndarray, frames: Any, time: Any, status: Any) -> None:
		if status:
			logger.error('InputVolume callback status: %s', status)
			raise sd.CallbackAbort
		vol = np.average(np.abs(indata[:,self._inputs]))
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

	def start(self) -> None:
		if self._stream is None:
			self._stream = sd.InputStream(device=self._device, channels=self._channels,
				callback=self._callback, blocksize=self._blocksize, dtype=_DTYPE)
		elif self._stream.active == self._stream.stopped:
			raise RuntimeError('InputVolume not healthy')
		elif self._stream.active:
			return
		self._stream.start()

	def stop(self) -> None:
		if self._stream is not None:
			self._stream.stop()
			self._stream.close()
			self._stream = None
			self.vol = 0.0

	def is_alive(self) -> bool:
		return self._stream.active if self._stream else False

	def info(self) -> dict[str, Any]:
		return {'initialized': bool(self._stream), 'is_alive': self.is_alive(),
			'samplerate': self._samplerate, 'blocksize': self._blocksize,
			'inputs': self._inputs, 'channels': self._channels,
			'delay': self._cb_repeat * self._blocksize / self._samplerate}

#-------------------------------------------------------

def list_devices() -> dict[str, Any]:
	"""Show output devices.

	Probably not useful with pulseaudio.
	"""
	return [d['name'] for d in sd.query_devices()]

def create_vol_array(channel_shape: tuple[int, int], mono: bool = False,
		outputs: Sequence|None = None, vol: float = 1.0) -> np.ndarray:
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

def new_playback(filename: str, *, device: DeviceType = None, channels: int|None = None,
		outputs: Sequence|None = None, mono: bool = False, vol: float = 1.0):
	"""Return FilePlayer configured to use a given device and channels.

	The device setting could not work as expected when using pulseaudio.
	"""
	fp = FilePlayer(_alt_file(filename), device=device, channels=channels, prepare=False)
	vol_array = create_vol_array(fp.channel_shape, mono, outputs, vol)
	fp.set_vol_array(vol_array)
	return fp
