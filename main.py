from convert import *

"""
TODO:
- Offsync problems! E.g. in Accelerator and that other chart I played
- Limit snap to 192nd
- Maybe render keysounds
- Look at issue with unbounded holds
- Look at data.zip not being extracted
- Better folder naming scheme
"""

def main():
	# ~ for keymode_filter in [6,7,8,9,10]:
	for keymode in [4]:
	
		# ~ output_dir = f"output/Malody {keymode}k Converts"
		output_dir = f"output/test"
		
		print("Parsing charts...")
		library = build_library("../download-malody-charts/output", limit=100, keymode_filter=keymode)
		library.print_stats()
		
		print("Writing charts as .sm...")
		assemble_sm_pack(library, output_dir)
		
		# ~ analyze_msd(output_dir, "output")

if __name__ == "__main__":
	main()
