import argparse
import ntlib.imp as ntimp
from __init__ import *

ntimp.config_log()

def int_or_str(s):
	try:
		return int(s)
	except ValueError:
		return s
def int_set(s):
	return {int(val) for val in s.split(',') if val is not None}

parser = argparse.ArgumentParser()
parser.add_argument('filename', help='audio file to be played', nargs='?')
parser.add_argument('-l', '--list-devices', action='store_true', help='show available devices')
parser.add_argument('-d', '--device', type=int_or_str,
	help='output device (numeric ID or substring)')
parser.add_argument('-n', '--channels', type=int, help='number of output channels')
parser.add_argument('-o', '--outputs', type=int_set,
	help="channels on which the sound should be played, "
	"e.g. '-o 1,0' plays right channel on left speaker and the other way round")
parser.add_argument('-v', '--volume', type=float, help='volume in percent', default=100.0)
parser.add_argument('--mono', action='store_true', help='downmix input to mono')
args = parser.parse_args()

if not args.filename:
	if args.list_devices:
		print('\n'.join(list_devices()))
	else:
		parser.print_help()
	exit()

device = device_index(args.device) if args.device else None
pb = new_playback(args.filename, device=device, channels=args.channels,
	outputs=args.outputs, mono=args.mono, vol=args.volume/100.0)
pb.play()
print(pb.info())
try:
	while pb.is_alive():
		pb.join(1.0)
except KeyboardInterrupt:
	pb.stop()
	logging.info('stopped by user')
pb.close()
