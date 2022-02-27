"""Basic path for configuration file for ntlib modules."""

import os
from sys import platform

root = os.path.dirname(__file__)
# if the confpath is platform independent:
# confpath = os.path.join(root, 'config.json')

if platform.startswith('linux'):
	confpath = os.path.join(root, 'config', 'linux.json')
elif platform.startswith('win'):
	confpath = os.path.join(root, 'config', 'windows.json')
else:
	raise ImportError(f'confpath not available for platform {platform}')
