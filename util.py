import math, logging
from functools import reduce

logger = logging.getLogger()

def lcm(a):
	lcm = a[0]
	for i in a[1:]:
		lcm = lcm * i // math.gcd(lcm, i)
	return lcm

def is_whole(n):
	error = abs(n - round(n))
	return error < 1e-6
