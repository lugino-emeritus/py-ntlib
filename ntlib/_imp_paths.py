"""File to config alias imports.

This example configuration allows e.g. the following imports:
- imp.import_alias('mypy', 'xyz') will import xyz from DEFAULT_PATH + 'python'
- imp.import_alias('project_foo', 'bar') imports foo.bar from DEFAULT_PATH + 'Projects'
"""
from sys import platform

if platform.startswith('win'):
	DEFAULT_PATH = 'D:/000/'
elif platform.startswith('linux'):
	DEFAULT_PATH = '/media/nti/Data/000/'
else:
	raise ImportError('DEFAULT_PATH not available for platform {}'.format(sys.platform))

alias_paths = {
	'mypy': (DEFAULT_PATH + 'Projects/python', None),
	'sotrep': (DEFAULT_PATH + 'Projects', 'SOTREP')
}
