# NTLIB

Set of python3 modules developed for different projects.

It can be used by adding a \*.pth file to a python package path (e.g. site-packages) containing the path to a folder which includes the library. This has the advantage of using the same modules on different systems of a dual-boot PC. Furthermore, this allows the development of libraries without naming issues.

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

More details can be found in the source code. Feel free to modify the code for your own purposes.

## imp

Developed to handle path imports:

- `reload(module)`: reloads a module, useful for testing
- `module = import_path(modulename, path='')`: import from specific folder, returns module
- `module = import_alias(alias, modulename)`: it is possible to set an alias name for a folder, rename `_imp_paths_sample.py` to `_imp_paths.py` and define an `alias_path` in this file to use it.

Moreover the function `set_log_config(level=logging.INFO)` is available to set a basic config for logging.


## fctthread

Allows system commands (`shell_cmd`, `start_app`), and provides different classes to work with threads:
- `ThreadLoop`: execute a method repeatedly
- `CmpEvent`: receive data from another thread after a successful comparison
- `QueueWorker`: parallel element processing

*Note:* version 0.2.0 changed ThreadLoop target.


## tsocket

Wrapper over the python socket to use a timeout by default and simplify initialization of udp and ipv6 sockets. \
*Note:* `create_serversock` changed in version 0.2.11: Pass address `('', port)` as parameter to be compatible.


## easysound

Using sounddevice and soundfile modules to playback sounds on a specific device and channels:

```py
import ntlib.easysound as esound
ps = esound.config_ps('sound1.wav', device=None, ch_out_num=2, mono=True, ch_out=(1,), vol=0.5)
# ch_out = (1,) means playback only on right channel
ps.play()
# ps.stop()
ps.join()
ps.close()
```

It is also possible to start it from console: `python3 easysound --help` for more information.

Moreover the module can call a function periodically with the input volume of a given device:
```py
import time
import ntlib.easysound as esound

def vol_cb(vol):
	print(vol)

vol_handler = esound.InputVolume(vol_cb, vol_avg_time=0.5, device=None)
# calls vol_cb approx. each 0.5 seconds
vol_handler.start()
time.sleep(5)
vol_handler.stop()
vol_handler.close()
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
