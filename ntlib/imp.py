"""Provide import tools and can set a basic logging format."""

import importlib as _il
import os
import sys

__version__ = '0.2.6'

_confpath = None
_aliases = None

#-------------------------------------------------------

def config_log(level='INFO', fmt='', **kwargs):
	"""Configurate logging format to 'Level(asctime): [fmt] message'."""
	import logging
	fmt = ' '.join(x for x in ('%(levelname).1s(%(asctime)s):', fmt, '%(message)s') if x)
	logging.basicConfig(format=fmt, level=level, **kwargs)


def init_confpath(p=None):
	global _confpath, _confread
	if _confpath is None:
		from json import load as _confread
		if p is None:
			from ._confpath import confpath as _confpath
		else:
			_confpath = p
	else:
		raise RuntimeError(f'confpath ({_confpath}) already defined')

def load_config(name):
	if _confpath is None:
		init_confpath()
	with open(_confpath) as f:
		return _confread(f)[name]

#-------------------------------------------------------

class _EnsureSysPath:
	def __init__(self, path):
		self.path = os.path.abspath(path)
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
	if not module.__file__.endswith('.py'):
		raise ImportError(f"module '{module.__name__}' is no '.py' file: {module.__file__}")
	path, tail = os.path.split(module.__file__[:-3])
	if tail == '__init__':
		path, tail = os.path.split(path)
	names = module.__name__.split('.')
	while names.pop() == tail:
		if not names:
			break
		path, tail = os.path.split(path)
	else:
		raise ImportError(f"module '{module.__name__}' not match source: {module.__file__}")
	with _EnsureSysPath(path):
		return _il.reload(module)
