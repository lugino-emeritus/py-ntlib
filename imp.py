"""Provide import tools and can set a basic logging format."""
__version__ = '0.3.0'

import importlib as _il
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from types import ModuleType
from typing import Any, cast

_osp = os.path

_confpath = cast(str, None)
_aliases = cast(dict[str, tuple[str, str]], None)

# -----------------------------------------------------------------------------

def _prepare_log_path(filepath: str = '') -> str:
	"""Create full pathname to a log file, appends the caller name if only a path is given'."""
	path, filename = _osp.split(filepath)
	if not filename.strip('.'):
		path = filepath
		filename = ''
	path = _osp.abspath(path)
	try:
		os.makedirs(path, exist_ok=True)
		if not filename:
			filename = _osp.splitext(_osp.basename(sys.argv[0]))[0] + '.log'
		return _osp.join(path, filename)
	except Exception as e:
		print(f'failed to create log path {filepath}: {e!r}')
		return ''

def config_log(level: int|str = 'INFO', addfmt: str = '', *, rotpath: str|None = None,
		rotsize: tuple[int, int]|None = None, addstd: bool = False) -> None:
	"""Configure logging format to 'Level(time): [fmt] message'.

	Args:
	- level: known from logging, can be int or levelname
	- addfmt: additional %-formatter
	- rotpath: rotating log file (1MB, 2MB with DEBUG, 5 backups)
	- rotsize: tuple of (size in kB, number of backups)
	- addstd: if rotpath is defined also log to stdout

	If rotpath endswith '/' or '/.' log to 'rotpath/<name_of_start_script>.log'.
	"""
	level = cast(int, logging._checkLevel(level))  # type:ignore
	fmt = ' '.join(x for x in ('%(levelname).1s[%(asctime)s]', addfmt, '%(message)s') if x)
	if rotpath:
		if rotsize:
			maxsize = rotsize[0] * 2**10
			backups = rotsize[1]
		else:
			maxsize = 2**20 if level > 10 else 2**21
			backups = 5
		h = RotatingFileHandler(_prepare_log_path(rotpath), maxBytes=maxsize, backupCount=backups)
		if _osp.getsize(h.baseFilename) > 1023:
			h.doRollover()
		handlers = (h, logging.StreamHandler()) if addstd else (h,)
	else:
		handlers = (logging.StreamHandler(),)
	logging.basicConfig(format=fmt, level=level, handlers=handlers, force=True)


def init_confpath(p: str|None = None, *, force: bool = False) -> None:
	global _confpath, _confload
	if _confpath is None:
		from json import load as _confload
		if p is None:
			from ._confpath import confpath as p
	elif p is None or not force:
		raise RuntimeError(f'confpath ({_confpath}) already defined')
	_confpath = _osp.abspath(p)

def load_config(name: str) -> Any:
	if _confpath is None:
		init_confpath()
	with open(_confpath) as f:
		return _confload(f)[name]

# -----------------------------------------------------------------------------

class _EnsureSysPath:
	def __init__(self, path: str):
		self.path = _osp.abspath(path)
	def __enter__(self):
		sys.path.insert(0, self.path)
	def __exit__(self, *exc_args):
		sys.path.remove(self.path)


def import_path(modulename: str, path: str = '.') -> ModuleType:
	"""Import module from a given path, defaults to CWD."""
	path = _osp.abspath(path)
	if not _osp.isdir(path):
		raise ImportError(f'no directory: {path}')
	with _EnsureSysPath(_osp.abspath(path)):
		return _il.import_module(modulename)

def import_alias(alias: str, modulename: str) -> ModuleType:
	"""Import module from an alias path defined in the config.json file."""
	global _aliases
	if _aliases is None:
		_aliases = load_config('imp')
	path, tail = _aliases[alias]
	if tail:
		modulename = '.'.join((tail, modulename))
	return import_path(modulename, path)

def reload(module: ModuleType) -> ModuleType:
	"""Reload the given module, but not its submodules."""
	if module.__file__ is None:
		raise ImportError(f"module '{module.__name__}' has no __file__ path")
	path, ext = _osp.splitext(module.__file__)
	if ext != '.py':
		raise ImportError(f"module '{module.__name__}' is no '.py' file: {module.__file__}")
	if _osp.basename(path) == '__init__':
		path = _osp.dirname(path)
	names = module.__name__.split('.')
	while names:
		path, tail = _osp.split(path)
		if names.pop() != tail:
			raise ImportError(f"module '{module.__name__}' not match source: {module.__file__}")
	with _EnsureSysPath(path):
		return _il.reload(module)
