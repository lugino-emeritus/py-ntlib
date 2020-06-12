# ntlib

This is a set of small python3 modules I developed for some projects.

It can be used e.g. by adding a \*.pth file to a python package path (e.g. site-packages) containing the path name which includes ntlib. This has the advantage of using the same modules on different systems of a dual-boot computer. Moreover it is possible to develop own libraries without naming issues:
```
FOLDER-STRUCTURE:
- this_is_a_path/defined_in_a_pth_file
  - ntlib
    - imp
    - ...
  - otherlib
  	- imp
  	- ...

import ntlib.imp as ntimp
import otherlib.imp as other
```

Feel free to change the code for your own purposes.

It follows a short description of the modules, have a look at the source for details:

## imp

Developed to handle some imports:

- `reload(module)` to reload a module, useful while testing a module
- `module = import_path(modulename, path='')` to import from specific folder, returns module
- `module = import_alias(alias, modulename)` it is possible to set an alias name for a folder, rename `_imp_paths_sample.py` to `_imp_paths.py` and define the `alias_path` in the file to use it.

Moreover the module has a function `set_log_config(level=logging.INFO)` to set a basic config for logging.


## fctthread

Allows system commands (`shell_cmd`, `start_app`) and helps to handle separate threads (`ThreadLoop`)
More details in the file.


## tsocket

Wrapper over the python socket to use a timeout by default and simplify initialization of udp and ipv6 sockets.
More details in the file.


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

sheet.set_data('A3', 'hallo')
sheet.get_data('A3')  # returns 'hallo'
sheet.get_array('A1', 'B3')  # returns all data within that range
sheet[2,0] = 8  # set cell A3
sheet[2,0]  # returns 8
```

`to_dtime` and `from_dtime` converts LibreOffice time values to datetime in python.
