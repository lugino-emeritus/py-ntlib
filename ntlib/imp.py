import importlib as _il
import logging
import os
import sys

__version__ = '0.1.0'

try:
	from ._imp_paths import alias_paths as _aliases
except ImportError:
	_aliases = {}

#-------------------------------------------------------

def set_log_config(level=logging.INFO):
	_il.reload(logging)
	logging.basicConfig(format='%(levelname)-8s %(asctime)s; %(message)s', level=level)

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
	with _EnsureSysPath() as syspath:
		syspath.add(os.path.dirname(module.__file__))
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
		modulename = pre + '.' + modulename
	return import_path(modulename, path)
