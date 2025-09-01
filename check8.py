"""Run flake8 with the tox.ini from ntlib."""
__version__ = '0.1.0'

if __name__ == '__main__':
	# flake reloads this module for each analyzed file
	# hence, do all work after the comparison above
	import logging
	import ntlib.imp as ntimp
	import sys
	from flake8.main.cli import main as flake8main
	from os import path as _osp

	ntimp.config_log(logging.WARNING)

	tox_file = _osp.normpath(_osp.join(_osp.dirname(__file__), 'config/tox.ini'))
	if not _osp.exists(tox_file):
		tox_file = _osp.normpath(_osp.join(_osp.dirname(__file__), 'tox.ini'))
	if not _osp.exists(tox_file):
		logging.error("config file '%s' does not exist", tox_file)
		sys.exit(1)

	logging.warning('run flake8 with config %s', tox_file)
	error = flake8main(('--config', tox_file))
	if error:
		logging.error('flake 8 execution failed with error %d', error)
	sys.exit(error)
