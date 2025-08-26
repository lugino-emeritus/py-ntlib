# NTLIB

Collection of python (3.8+) modules developed for various projects.

To make it available in `sys.path` the cloned folder must have the name ntlib. Then the script `_add_path.py` can be called to add a link of this namespace package to the file mylibs.pth in site-packages or dist-packages.
Thus, it is possible that the same installation can be used on different systems of a dual-boot computer. Furthermore, this allows the development of libraries without naming issues:

```
FOLDER STRUCTURE:
+ path_defined_in_pth_file
  + ntlib
    - imp.py
    - ...
  + extern
  	- imp.py
  	- ...
```

```py
import ntlib.imp as ntimp
import extern.imp as extimp
```

Below is a list with a brief description of the available modules.
Feel free to modify the source code for your own purposes.


## `imp`

Provides the following methods:

- `config_log(level='INFO')`: set a basic config for logging, it is possible to set an additional formatter or a rotating log file
- `options = load_config(name)`: import `_confpath.py` which defines a path to a json dictionary (*config.json*) containing `options` for ntlib module `name`

- `reload(module)`: reload module, extends function from `importlib`
- `module = import_path(modulename, path='')`: import from specific folder
- `module = import_alias(alias, modulename)`: load module from an alias path (section `imp` in config.json)

In order for the following modules to operate correctly copy the `config_sample` folder to `config` and customize it or edit `_confpath.py`.

#### Version Info
- `v0.3.0` Input params of config_log modified


## `fctthread`

Allows system commands (`shell_cmd`, `start_app`), and provides different classes to work with threads:
- `ThreadLoop`: execute a method repeatedly
- `QueueWorker`: parallel element processing
- `CmpEvent`: receive data from another thread after a successful comparison


## `scheduler`

Module to call methods repeatedly. Also provides a global `RptSched` (`scheduler.glob_sched`) to add e.g. purge jobs.


## `tsocket`

Wrapper over the python socket to use a timeout by default and simplify initialization of udp and ipv6 sockets.


## `mediactl`

Modules to control [vlc](https://www.videolan.org) and [foobar2000](https://www.foobar2000.org) from python.
The paths to the applications are defined in the config.


## `easysound`

Using modules sounddevice and soundfile to playback audio files on a specific output:

```py
import ntlib.easysound as esound
fp = esound.new_playback('beeps.wav', device=None, channels=2, outputs=(1,), mono=True, vol=0.5)
# outputs = (1,): playback only on right channel
# outputs = (1, 0): swap right and left channel
fp.play()
#fp.stop()
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

When using pulseaudio on linux, the device option should be avoided.

## `sofficectl`

Helps connecting python with an open LibreOffice or OpenOffice file using `uno`. Especially useful for calc.
The config contains the connection parameters.

```py
import ntlib.sofficectl.calctools as ctools

model = calctools.connect('path.ods or name of opened file')
sheet = calctools.MiniSheet(model.Sheets[0])

sheet.set_data('A3', 'Hello World')
sheet[0,1] = 42.5  # set cell B1
print(sheet.get_data('B1'))
print(sheet[2,0])  # prints 'Hello World'
print(sheet.get_array('A1', 'B3'))
```

`to_dtime` and `from_dtime` converts office time values to `datetime`.
