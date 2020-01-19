from glob import iglob
import os
import util, sm, chart, mc

def main():
	mc_paths = iglob("malody-dump/*/*/*.mc")
	mc_path = next(mc_paths)
	
	library = chart.Library()
	mc.parse(library, mc_path)
	
	print(sm.gen_sm(library.songs[0]))

if __name__ == "__main__":
	main()
