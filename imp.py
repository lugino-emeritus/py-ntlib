"""Provide import tools and can set a basic logging format."""

import importlib as _il
import logging
import os.path as _osp
import sys
from types import ModuleType
from typing import Any

__version__ = '0.2.14'

_confpath = None
_aliases = None

#-------------------------------------------------------

def config_log(level: int|str = 'INFO', fmt: str = '', *,
		force: bool = True, rotfile: str|None = None, addstd: bool = False) -> None:
	"""Configurate logging format to 'Level(time): [fmt] message'.

	Args:
	- level: known from logging, can be int or levelname
	- fmt: additional %-formatter
	- force: set root logger even if it already has a handler
	- rotfile: rotating log file (1MB, 2MB with DEBUG, 5 backups)
	- addstd: if rotfile is defined also log to stdout

	If more options are needed, use dictConfig or fileConfig from logging.config.
	"""
	level = logging._checkLevel(level)
	fmt = ' '.join(x for x in ('%(levelname).1s[%(asctime)s]', fmt, '%(message)s') if x)
	if rotfile:
		from logging.handlers import RotatingFileHandler
		h = RotatingFileHandler(rotfile, maxBytes=2**20 if level>10 else 2**21, backupCount=5)
		if _osp.getsize(h.baseFilename) > 1023:
			h.doRollover()
		handlers = (h, logging.StreamHandler()) if addstd else (h,)
	else:
		handlers = (logging.StreamHandler(),)
	logging.basicConfig(format=fmt, level=level, force=force, handlers=handlers)


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
	global _confpath
	if _confpath is None:
		init_confpath()
	with open(_confpath) as f:
		return _confload(f)[name]

#-------------------------------------------------------

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
