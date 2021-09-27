"""Provide import tools and can set a basic logging format."""

import sys
from importlib import import_module, reload

__version__ = '0.2.4'

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


def import_path(modulename, path=''):
	org = sys.path[:]
	try:
		if path:
			sys.path.insert(0, path)
		return import_module(modulename)
	finally:
		sys.path[:] = org

def import_alias(alias, modulename):
	"""import module from an alias path defined in the config.json file."""
	global _aliases
	if _aliases is None:
		_aliases = load_config('imp')
	path, tail = _aliases[alias]
	if tail:
		modulename = '.'.join((tail, modulename))
	return import_path(modulename, path)
