import math, logging
from functools import reduce

logger = logging.getLogger()

def lcm(a):
	lcm = a[0]
	for i in a[1:]:
		lcm = lcm * i // math.gcd(lcm, i)
	return lcm

def gcd(a):
	return reduce(math.gcd, a)

def is_whole(n):
	error = abs(n - round(n))
	return error < 1e-6

PATH_ESCAPE_MAPPING = str.maketrans("", "", r'\/*?:"<>|')
def escape_filename(filename):
	return filename.translate(PATH_ESCAPE_MAPPING)

def get_seconds_at(bpm_changes, row):
	row = row.absolute_bar()
	rows = [row.absolute_bar() for row, bpm in bpm_changes]
	bpms = [bpm for row, bpm in bpm_changes]
	
	time = 0
	i = 0
	while rows[i] < row:
		if i + 1 < len(rows):
			next_row = min(rows[i+1], row)
		else:
			next_row = row
		
		beats = 4 * (next_row - rows[i])
		section_length = beats * 60 / bpms[i]
		time += section_length
		i += 1
		
		if i == len(rows): break
	
	return time
