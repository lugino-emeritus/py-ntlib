"""File to config alias imports.

This example configuration allows e.g. the following imports:
- imp.import_alias('mypy', 'xyz') will import xyz from DEFAULT_PATH + 'python'
- imp.import_alias('project_foo', 'bar') imports foo.bar from DEFAULT_PATH + 'Projects'
"""
from sys import platform

if platform.startswith('win'):
	DEFAULT_PATH = 'D:/myfolder'
elif platform.startswith('linux'):
	DEFAULT_PATH = '/media/user/data/myfolder'
else:
	raise ImportError(f'DEFAULT_PATH not available for platform {sys.platform}')

alias_paths = {
	'mypy': (DEFAULT_PATH + 'python', None),
	'project_foo': (DEFAULT_PATH + 'Projects', 'foo')
}
