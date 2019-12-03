from __init__ import *

import argparse

logging.basicConfig(format='%(levelname)-8s %(asctime)s; %(message)s', level=logging.DEBUG)

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
parser.add_argument('-n', '--num_out_ch', type=int, help='number of output channels')
parser.add_argument('-o', '--out_ch', type=int_set,
					help='channels on which the sound should be played, \
							e.g. -o 1,0 to play right channel on left speaker and the other way round')
parser.add_argument('-v', '--volume', type=int, help='volume in percent', default=100)
parser.add_argument('--mono', action='store_true')
args = parser.parse_args()

ps = config_ps(args.filename, args.device, args.num_out_ch, args.mono, args.out_ch, args.volume / 100)
ps.play()
try:
	while ps.is_alive():
		ps.join(1)
except KeyboardInterrupt:
	ps.stop()
	logging.info('stopped by user')
ps.close()
