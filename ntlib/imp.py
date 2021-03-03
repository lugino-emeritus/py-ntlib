"""Handle module reloads and imports from specific paths."""

import importlib as _il
import logging
import sys

__version__ = '0.1.3'

try:
	from ._imp_paths import alias_paths as _aliases
except ImportError:
	_aliases = {}

#-------------------------------------------------------

class _EnsureSysPath:
	def __init__(self):
		self.org_path = []
	def __enter__(self):
		self.org_path[:] = sys.path[:]
		return self
	def __exit__(self, *exc_args):
		sys.path[:] = self.org_path[:]
	def add(self, path):
		sys.path.insert(0, path)


def reload(module):
	_il.reload(module)

def import_path(modulename, path=''):
	with _EnsureSysPath() as syspath:
		if path:
			syspath.add(path)
		return _il.import_module(modulename)

def import_alias(alias, modulename):
	if alias not in _aliases:
		raise KeyError('unknown alias')
	path, pre = _aliases[alias]
	if pre:
		modulename = '.'.join((pre, modulename))
	return import_path(modulename, path)


def set_log_config(level=logging.INFO, fmt='', **kwargs):
	"""Sets log config to 'level(asctime): {fmt} message'."""
	fmt = ' '.join(x for x in ('%(levelname).1s(%(asctime)s):', fmt, '%(message)s') if x)
	logging.basicConfig(format=fmt, level=level, **kwargs)
