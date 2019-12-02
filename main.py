import os, math, shutil, logging
from glob import glob
from sm import *
from chart import *

logger = logging.getLogger()

def copy_maybe(src, dst):
	if not os.path.exists(dst):
		shutil.copyfile(src, dst)

def build_library(malody_songs_dir, limit=None):
	library = Library()
	
	mc_paths = glob(os.path.join(malody_songs_dir, "*/*/*.mc"))
	
	# REMEMBER
	mc_paths = [*glob("../download-malody-charts/output/_song_1400/*/*.mc"), *glob("../download-malody-charts/output/_song_1558/*/*.mc"), *glob("../download-malody-charts/output/_song_1169/*/*.mc")]
	
	if limit: mc_paths = mc_paths[:limit]
	for path in mc_paths:
		try:
			library.parse_mc(path, verify=False)
		except Exception as e:
			logger.exception("Error while parsing {path}")
	
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
	minacalc_output = os.popen(f"./minacalc {sm_path}").readlines()
	
	overalls = []
	for line in minacalc_output:
		if line.startswith("Overall"):
			overalls.append(float(line[9:]))
	
	return overalls

def analyze_msd(basedir):
	from multiprocessing import Pool
	pool = Pool()
	
	song_dirs = glob(os.path.join(basedir, "*"))
	overalls = pool.map(analyze, song_dirs)
	
	max_overall = max(max(o) for o in overalls if len(o) > 0)
	
	# Key=(lower, upper) Value=[songdir...]
	buckets = {}
	bucket_lower = None
	bucket = []
	
	def finish_bucket():
		nonlocal buckets, bucket, bucket_lower
		
		buckets[(bucket_lower, upper)] = bucket
		print(f"{bucket_lower}-{upper}: {len(bucket)} files")
		
		bucket = []
		bucket_lower = None
	
	for lower in range(0, math.ceil(max_overall)):
		if bucket_lower is None: bucket_lower = lower
		upper = lower + 1
		
		for song_dir, overall in zip(song_dirs, overalls):
			if any(o >= lower and o < upper for o in overall):
				bucket.append(song_dir)
		
		if len(bucket) > 30: finish_bucket()
	finish_bucket()
	
	pool.close()

def main():
	output_dir = "output"
	
	# ~ library = build_library("../download-malody-charts/output", limit=None)
	# ~ library.print_stats()
	
	# ~ assemble_sm_pack(library, output_dir)
	
	analyze_msd(output_dir)

if __name__ == "__main__":
	main()
