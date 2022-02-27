"""Provide import tools and can set a basic logging format."""

import importlib as _il
import os.path as _osp
import sys

__version__ = '0.2.8'

_confpath = None
_aliases = None

#-------------------------------------------------------

def config_log(level='INFO', fmt='', *, force=True, **kwargs):
	"""Configurate logging format to 'Level(asctime): [fmt] message'."""
	import logging
	fmt = ' '.join(x for x in ('%(levelname).1s[%(asctime)s]', fmt, '%(message)s') if x)
	logging.basicConfig(format=fmt, level=level, force=force, **kwargs)


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
	with _EnsureSysPath(path):
		return _il.import_module(modulename)

def import_alias(alias, modulename):
	"""import module from an alias path defined in the config.json file."""
	global _aliases
	if _aliases is None:
		_aliases = load_config('imp')
	path, tail = _aliases[alias]
	if tail:
		modulename = '.'.join((tail, modulename))
	return import_path(modulename, path)

def reload(module):
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
