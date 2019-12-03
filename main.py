import os, math, shutil, logging, subprocess
from glob import glob
from sm import *
from chart import *

logger = logging.getLogger()

def copy_maybe(src, dst):
	if not os.path.exists(dst):
		shutil.copyfile(src, dst)

def build_library(malody_songs_dir, limit=None, **kwargs):
	library = Library()
	
	mc_paths = glob(os.path.join(malody_songs_dir, "*/*/*.mc"))
	
	if limit: mc_paths = mc_paths[:limit]
	for path in mc_paths:
		# ~ print(f"Parsing chart from {path}")
		try:
			library.parse_mc(path, verify=False, **kwargs)
		except Exception as e:
			logger.exception(f"Error while parsing {path}")
	
	library.clean_empty_songs()
	return library

def assemble_sm_pack(library, output_dir):
	for song in library.songs:
		source_path = song.charts[0].source_path
		source_dir = os.path.dirname(source_path)
		target_dir = os.path.join(output_dir, str(song.malody_id))
		os.makedirs(target_dir, exist_ok=True)
		target_path = os.path.join(target_dir, "file.sm")
		
		for src_file in glob(os.path.join(source_dir, "*")):
			target_file = os.path.join(target_dir, os.path.basename(src_file))
			if src_file.endswith(".mc"):
				target_file += ".old"
			#print(f"Copying {src_file} to {target_file}")
			copy_maybe(src_file, target_file)
		
		with open(target_path, "w") as f:
			print(f"Writing chart from {source_path} into {target_path}")
			try:
				f.write(write_sm(song))
			except Exception:
				logger.exception(f"Error while writing into {target_path} from {source_path}")

def analyze(song_dir):
	sm_path = os.path.join(song_dir, "file.sm")
	cmd = ["./minacalc", sm_path]
	try:
		# ~ minacalc_output = subprocess.check_output(cmd, stderr=open(os.devnull, "w")).decode("UTF-8")
		minacalc_output = os.popen(" ".join(cmd)).read()
	except subprocess.CalledProcessError as e:
		raise e
		# ~ print(f"Minacalc died with {sm_path} :(")
		# ~ return None
	
	overalls = []
	for line in minacalc_output.splitlines():
		if line.startswith("Overall"):
			overalls.append(float(line[9:]))
	
	return overalls

def analyze_msd(basedir):
	from multiprocessing import Pool
	pool = Pool()
	
	song_dirs = glob(os.path.join(basedir, "*"))[:500] # REMEMBER
	overalls = pool.map(analyze, song_dirs)
	pool.close()
	
	print("Overalls:", len(overalls))
	print("songdirs:", len(song_dirs))
	max_overall = max(max(o) for o in overalls if len(o) > 0)
	
	# Key=(lower, upper) Value=[songdir...]
	buckets = {}
	bucket_lower = None
	bucket = []
	
	def finish_bucket():
		nonlocal buckets, bucket, bucket_lower
		
		buckets[(bucket_lower, upper)] = bucket
		print(f"{bucket_lower:g}-{upper:g}: {len(bucket)} files")
		
		bucket = []
		bucket_lower = None
	
	# ~ step = 0.5
	step = 1
	lower, upper = -1, 0
	while True:
		# Progress lower and upper MSD limit one step
		lower = upper
		upper = round(lower + step, 5) # Round cuz floating point errors
		if bucket_lower is None: bucket_lower = lower
		if lower > max_overall: break # We're done :)
		
		for song_dir, overall in zip(song_dirs, overalls):
			if any(o >= lower and o < upper for o in overall):
				bucket.append(song_dir)
		
		if upper % 1 == 0:
			if len(bucket) > 60: finish_bucket()
		else: # If we have an ugly non-whole limit, give a lil more
			# tolerance, maybe we can get the bucket to a whole limit
			# before it gets too large
			if len(bucket) > 150: finish_bucket()
	
	upper = math.ceil(upper)
	if len(bucket) > 0: finish_bucket()

def main():
	keymode_filter = 8
	
	output_dir = "output"
	if keymode_filter: output_dir += f"-{keymode_filter}k"
	
	print("Parsing charts...")
	library = build_library("../download-malody-charts/output", limit=None, keymode_filter=keymode_filter)
	library.print_stats()
	
	print("Writing charts as .sm...")
	assemble_sm_pack(library, output_dir)
	
	# ~ analyze_msd(output_dir)

if __name__ == "__main__":
	main()
