import util
from convert import *

"""
TODO:
- Maybe render keysounds
- Look at data.zip not being extracted
- More escaping! Especially # escaping in .sm meta tags

Done:
- Limit snap to 192nd
- Offsync problems! E.g. in Accelerator and that other chart I played
- Better folder naming scheme
"""

def main():
	malody_source_dir = "malody-dump/"
	# ~ malody_source_dir = "../download-malody-charts/output"
	
	for keymode in [4]:
	
		output_dir = f"output/Malody {keymode}k Converts"
		
		# ~ print("Parsing charts...")
		# ~ library = build_library(malody_source_dir, limit=None, keymode_filter=keymode)
		# ~ library.print_stats()
		
		# ~ print("Writing charts as .sm...")
		# ~ assemble_sm_pack(library, output_dir, separate_charts=True)
		
		analyze_msd(output_dir, "output")

if __name__ == "__main__":
	main()
