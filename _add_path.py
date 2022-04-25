"""Add ntlib directory to mylibs.pth in site-packages."""

if __name__ != '__main__':
	raise ImportError('this file must be executed directly')

import os
import sys

try:
	import ntlib
	raise SystemExit('ntlib already accessible')
except ImportError:
	pass

pth = os.path.dirname(os.path.abspath(__file__))
pth, tail = os.path.split(pth)
if tail != 'ntlib':
	raise SystemExit('ntlib not found')
print('ntlib location:', pth)

if pth in sys.path:
	raise SystemExit('location available in sys.path')

def update_pth(filename):
	newline = False
	if os.path.exists(filename):
		with open(filename, 'r') as f:
			s = f.read()
		if s:
			for i in s.split('\n'):
				if i and os.path.abspath(i) == pth:
					raise SystemExit(f'location already in {filename}')
			if s[-1] != '\n':
				newline = True
	with open(filename, 'a') as f:
		if newline:
			f.write('\n')
		f.write(pth + '\n')
	raise SystemExit(f'successfully added location to {filename}')

package_paths = [p for p in sys.path if os.path.basename(p) == 'site-packages']
package_paths.extend(p for p in sys.path if os.path.basename(p) == 'dist-packages')
for p in package_paths:
	filename = os.path.join(p, 'mylibs.pth')
	try:
		update_pth(filename)
	except PermissionError:
		print(f'no permission to add location to {filename}')

raise SystemExit('failed to add ntlib to sys.path')
