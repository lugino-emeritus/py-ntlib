"""Provide import tools and can set a basic logging format."""

import importlib as _il
import logging
import os.path as _osp
import sys

__version__ = '0.2.10'

_confpath = None
_aliases = None

#-------------------------------------------------------

def config_log(level='INFO', fmt='', *, force=True, rotfile=None, addstd=False):
	"""Configurate logging format to 'Level(time): [fmt] message'.

	Args:
	- level: known from logging, can be int or levelname
	- fmt: additional %-formatter
	- force: sets the root logger even if it already has a handler
	- rotfile: rotating log file (1MB, 2MB with DEBUG, 3 backups)
	- addstd: if rotfile is defined also log to stdout

	If more options are needed, use dictConfig or fileConfig from logging.config.
	"""
	level = logging._checkLevel(level)
	fmt = ' '.join(x for x in ('%(levelname).1s[%(asctime)s]', fmt, '%(message)s') if x)
	if rotfile:
		from logging.handlers import RotatingFileHandler
		h = RotatingFileHandler(rotfile, maxBytes=2**20 if level>10 else 2**21, backupCount=3)
		if _osp.getsize(h.baseFilename) > 2047:
			h.doRollover()
		handlers = (h, logging.StreamHandler()) if addstd else (h,)
	else:
		handlers = (logging.StreamHandler(),)
	logging.basicConfig(format=fmt, level=level, force=force, handlers=handlers)


def init_confpath(p=None, *, force=False):
	global _confpath, _confload
	if _confpath:
		if not (p and force):
			raise RuntimeError(f'confpath ({_confpath}) already defined')
	else:
		from json import load as _confload
		if p is None:
			from ._confpath import confpath as p
	_confpath = _osp.abspath(p)

def load_config(name):
	if _confpath is None:
		init_confpath()
	with open(_confpath) as f:
		return _confload(f)[name]

#-------------------------------------------------------

class _EnsureSysPath:
	def __init__(self, path):
		self.path = _osp.abspath(path)
	def __enter__(self):
		sys.path.insert(0, self.path)
	def __exit__(self, *exc_args):
		sys.path.remove(self.path)


def import_path(modulename, path='.'):
	"""Import module from a given path, defaults to CWD."""
	with _EnsureSysPath(path):
		return _il.import_module(modulename)

def import_alias(alias, modulename):
	"""Import module from an alias path defined in the config.json file."""
	global _aliases
	if _aliases is None:
		_aliases = load_config('imp')
	path, tail = _aliases[alias]
	if tail:
		modulename = '.'.join((tail, modulename))
	return import_path(modulename, path)

def reload(module):
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
