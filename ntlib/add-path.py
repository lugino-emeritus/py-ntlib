"""Add ntlib dir to mylibs.pth in site-packages."""
import os
import sys

if __name__ != '__main__':
	raise SystemExit('this script must be executed directly')

try:
	import ntlib
	raise SystemExit('ntlib already accessible')
except ImportError:
	pass

path = os.path.dirname(os.path.abspath(__file__))
path, tail = os.path.split(path)
if tail != 'ntlib':
	raise SystemExit('ntlib not found')
print('ntlib dir:', path)

if path in sys.path:
	raise SystemExit('library path already in sys.path')

for p in sys.path:
	if os.path.basename(p) == 'site-packages':
		filename = os.path.join(p, 'mylibs.pth')
		newline = False
		try:
			with open(filename, 'r') as f:
				s = f.read()
			if s:
				if s[-1] != '\n':
					newline = True
				for i in s.split('\n'):
					if i and os.path.abspath(i) == path:
						raise SystemExit(f'library path already in {filename}')
		except FileNotFoundError:
			pass
		try:
			with open(filename, 'a') as f:
				if newline:
					f.write('\n')
				f.write(path + '\n')
			raise SystemExit(f'successfully added library path to {filename}')
		except PermissionError:
			pass

raise SystemExit('failed to add ntlib to sys.path, calling script as root may help')
