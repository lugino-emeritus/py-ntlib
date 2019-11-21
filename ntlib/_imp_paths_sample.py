'''File to handle alias imports
This example configuration allows e.g. the following imports:
- imp.import_alias('mypy', 'abcde') will import abcde from DEFAULT_PATH + 'python'
- imp.import_alias('foo_project', 'bar') imports foo.bar from DEFAULT_PATH + 'Projects'
'''
from sys import platform

if platform.startswith('win'):
	DEFAULT_PATH = 'D:/myfolder'
elif platform.startswith('linux'):
	DEFAULT_PATH = '/media/user/data/myfolder'
else:
	raise ImportError('DEFAULT_PATH not available for platform {}'.format(sys.platform))

alias_paths = {}
alias_paths['mypy'] = (DEFAULT_PATH + 'python', None)
alias_paths['foo_project'] = (DEFAULT_PATH + 'Projects', 'foo')
