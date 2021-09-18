# NTLIB

Collection of python (3.6+) modules developed for various projects.

It can be used by adding a \*.pth file to a python package path (e.g. site-packages) containing the path to a folder which includes the library. This has the advantage of using the same modules on different systems of a dual-boot computer. Furthermore, this allows the development of libraries without naming issues.

```
FOLDER STRUCTURE:
+ path_defined_in_pth_file
  + ntlib
    - imp.py
    - ...
  + otherlib
  	- imp.py
  	- ...
```

```py
import ntlib.imp as ntimp
import otherlib.imp as other
```

More details can be found in the source code. Feel free to modify it for your own purposes.


## imp

Provides the following methods:

- `config_log(level=INFO)`: set a basic config for logging
- `options = load_config(name)`: import `_confpath.py` which defines a path to a json dictionary (*config.json*) containing `options` for ntlib module `name`

- `import_module`, `reload`: known from `importlib`
- `module = import_path(modulename, path='')`: import from specific folder
- `module = import_alias(alias, modulename)`: load module from an alias path (section `imp` in config.json)


## fctthread

Allows system commands (`shell_cmd`, `start_app`), and provides different classes to work with threads:
- `ThreadLoop`: execute a method repeatedly
- `QueueWorker`: parallel element processing
- `CmpEvent`: receive data from another thread after a successful comparison


## tsocket

Wrapper over the python socket to use a timeout by default and simplify initialization of udp and ipv6 sockets.


## easysound

Using sounddevice and soundfile modules to playback sounds on a specific device and channels:

```py
import ntlib.easysound as esound
fp = esound.new_playback('sound1.wav', device=None, ch_num=2, outputs=(1,), mono=True, vol=0.5)
# outputs = (1,) means playback only on right channel
# outpust = (1, 0) swaps right and left channel
fp.play()
# fp.stop()
fp.join()
fp.close()
```

It is also possible to start it from console: `python3 easysound --help` for more information.

Moreover the module can call a function periodically with the input volume of a given device:
```py
import time
import ntlib.easysound as esound

def vol_cb(vol):
	print(vol)

invol = esound.InputVolume(vol_cb, device=None, delay=0.5)
# calls vol_cb approx. each 0.5 seconds
invol.start()
time.sleep(5)
invol.stop()
invol.close()
```


## sofficectl

Helps connecting python with an OpenOffice or LibreOffice file using `uno`. Especially for Libreoffice calc useful. It uses tcp port 3103 by default.

```py
import ntlib.sofficectl.calctools as calctools

model = calctools.connect_to('path.ods or name of opened file')
sheet = calctools.MiniSheet(model.Sheets[0])

sheet.set_data('A3', 'Hello World')
sheet[0,1] = 42.5  # set cell B1
print(sheet.get_data('B1'))
print(sheet[2,0])  # prints 'Hello World'
print(sheet.get_array('A1', 'B3'))
```

`to_dtime` and `from_dtime` converts LibreOffice time values to `datetime` in python.
