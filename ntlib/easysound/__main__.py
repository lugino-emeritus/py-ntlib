from __init__ import *

import argparse
import ntlib.imp

ntlib.imp.config_log(logging.DEBUG)

def int_or_str(s):
	try:
		return int(s)
	except ValueError:
		return s
def int_set(s):
	return {int(val) for val in s.split(',') if val is not None}

parser = argparse.ArgumentParser()
parser.add_argument('filename', help='audio file to be played back')
parser.add_argument('-d', '--device', type=int_or_str,
	help='output device (numeric ID or substring)')
parser.add_argument('-n', '--ch_num', type=int, help='number of output channels')
parser.add_argument('-o', '--outputs', type=int_set,
	help='channels on which the sound should be played, \
	e.g. -o 1,0 to play right channel on left speaker and the other way round')
parser.add_argument('-v', '--volume', type=int, help='volume in percent', default=100)
parser.add_argument('--mono', action='store_true')
args = parser.parse_args()

pb = new_playback(args.filename, device=args.device, ch_num=args.ch_num,
	outputs=args.outputs, mono=args.mono, vol=args.volume/100)
pb.play()
try:
	while pb.is_alive():
		pb.join(1)
except KeyboardInterrupt:
	pb.stop()
	logging.info('stopped by user')
pb.close()
