import os, math, shutil, logging, subprocess
from glob import glob
from sm import *
from chart import *

def copy_maybe(src, dst, force=False, move=False):
	if move:
		exit() # REMEMBER
		shutil.move(src, dst)
	else:
		try:
			shutil.copytree(src, dst, dirs_exist_ok=True)
		except OSError as e:
			if e.errno == 20: # src was not a directory
				if not force and os.path.exists(dst): return
				shutil.copy(src, dst)
			else:
				raise e

def build_library(malody_songs_dir, limit=None, **kwargs):
	library = Library()
	
	mc_paths = glob(os.path.join(malody_songs_dir, "*/*/*.mc"))
	
	if limit: mc_paths = mc_paths[:limit]
	for path in mc_paths:
		# ~ print(f"Parsing chart from {path}")
		try:
			library.parse_mc(path, verify=False, **kwargs)
		except Exception as e:
			util.logger.exception(f"Error while parsing {path}")
	
	library.clean_empty_songs()
	return library

def assemble_sm_pack(library, output_dir):
	for song in library.songs:
		source_path = song.charts[0].source_path
		source_dir = os.path.dirname(source_path)
		target_dir = os.path.join(output_dir, f"{song.title} [{song.malody_id}]")
		os.makedirs(target_dir, exist_ok=True)
		target_path = os.path.join(target_dir, "file.sm")
		
		for src_file in glob(os.path.join(source_dir, "*")):
			target_file = os.path.join(target_dir, os.path.basename(src_file))
			if src_file.endswith(".mc"):
				target_file += ".old"
			# ~ print(f"Copying {src_file} to {target_file}")
			copy_maybe(src_file, target_file)
		
		with open(target_path, "w") as f:
			print(f"Writing chart from {source_path} into {target_path}")
			try:
				f.write(gen_sm(song))
				# ~ gen_sm(song)
			except Exception:
				util.logger.exception(f"Error while writing into {target_path} from {source_path}")

def analyze(song_dir):
	sm_path = os.path.join(song_dir, "file.sm")
	lines = os.popen(f"./minacalc '{sm_path}'").readlines()
	
	overalls = []
	for line in lines:
		if line.startswith("Overall"):
			overalls.append(float(line[9:]))
	
	return overalls

def analyze_msd(basedir, outdir, soft_pack_limit=200, hard_pack_limit=350):
	from multiprocessing import Pool
	pool = Pool()
	
	song_dirs = glob(os.path.join(basedir, "*"))
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
		
		if len(bucket) >= soft_pack_limit: finish_bucket()
		
		# ~ if upper % 1 == 0:
			# ~ if len(bucket) > 60: finish_bucket()
		# ~ else: # If we have an ugly non-whole limit, give a lil more
			# ~ # tolerance, maybe we can get the bucket to a whole limit
			# ~ # before it gets too large
			# ~ if len(bucket) > 150: finish_bucket()
	
	upper = math.ceil(upper)
	if len(bucket) > 0: finish_bucket()
	
	for (lower, upper), song_dirs in buckets.items():
		num_subpacks = math.ceil(len(song_dirs) / hard_pack_limit)
		subpack_size = math.ceil(len(song_dirs) / num_subpacks)
		for i, song_dir in enumerate(song_dirs):
			if i % subpack_size == 0:
				pack_name = f"Malody 4k Megapack ({lower}-{upper})"
				if num_subpacks > 1:
					pack_name = pack_name[:-1] + f" {i//subpack_size+1})"
				dst_parent = os.path.join(outdir, "4k-grouped", pack_name)
				os.makedirs(dst_parent, exist_ok=True)
			
			dst_dir = os.path.join(dst_parent, os.path.basename(song_dir))
			print(f"copy from {song_dir} to {dst_dir}")
			copy_maybe(song_dir, dst_dir)
