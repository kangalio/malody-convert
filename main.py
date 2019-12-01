import json, os, math, shutil
from enum import Enum
from multiprocessing import Pool
from tqdm import tqdm
from glob import glob
from util import lcm

class NoteType(Enum):
	TAP = 0
	HOLD_HEAD = 1
	ROLL_HEAD = 2
	TAIL = 3
	MINE = 4
	
	def to_sm(self):
		return [1, 2, 4, 3, "M"][self.value]

class RowTime:
	# bpb = beats per bar
	def __init__(self, bar, beat, snap):
		self.bar = bar
		self.beat = beat
		self.snap = snap
	
	def absolute_bar(self):
		return self.bar + self.beat / self.snap

class Note:
	def __init__(self, column, row, note_type):
		self.column = column
		self.row = row
		self.note_type = note_type

class Chart:
	def __init__(self):
		self.creator = None
		self.chart_string = None
		self.video = None
		self.background = None
		self.num_columns = None
		self.notes = None
		
		self.source_path = None

class Song:
	def __init__(self, charts=None):
		# Don't put this in signature, or the default list will be
		# reference-shared across all songs!
		self.charts = charts or []
		
		self.audio = None
		self.offset = None # Audio offset in seconds
		self.title = None
		self.title_translit = None
		self.artist = None
		self.artist_translit = None
		self.bpm_changes = None # List of tuples (RowTime, bpm int)
		self.malody_id = None

class Library:
	def __init__(self, songs=[]):
		self.songs = songs
	
	def print_stats(self):
		num_charts = sum(len(song.charts) for song in self.songs)
		print(f"{len(self.songs)} songs, {num_charts} charts")
	
	def get_song_by_malody_id(self, malody_id):
		for song in self.songs:
			if song.malody_id == malody_id:
				return song
		
		song = Song()
		song.malody_id = malody_id
		self.songs.append(song)
		return song
	
	def verify_mc(self, mc):
		def assert_known_fields(obj, known_fields):
			unknown_fields = [f for f in obj if f not in known_fields]
			if len(unknown_fields) > 0:
				raise Exception(f"Warning: unknown meta fields: {', '.join(unknown_fields)}")
		
		assert_known_fields(mc["meta"], [
				"preview", # Don't know what this does. Hopefully not important
				"$ver", "creator", "background", "version",
				"id", "mode", "time", "song", "mode_ext", "video"])
		assert_known_fields(mc["meta"]["song"], [
				#"source", "org", # Not sure what those are
				"title", "titleorg", "artist", "artistorg", "id"])
		assert_known_fields(mc["meta"]["mode_ext"], [
				"column", "bar_begin"])
		
		for bpm_event in mc["time"]:
			assert_known_fields(bpm_event, ["beat", "bpm"])
		
		for event in mc["note"]:
			assert_known_fields(event, ["beat", "endbeat", "column",
					"sound", "vol", "type", "offset"])
	
	def parse_mc_rowtime(self, array):
		beats, subbeat, subbeat_snap = array
		
		# Some charts have their subbeats "overflowing" to the next
		# beat, e.g. (13, 4, 4) effectively being (14, 0, 4)
		beats += subbeat // subbeat_snap
		subbeat = subbeat % subbeat_snap
		
		bar = beats // 4
		beat = (beats % 4) + subbeat / subbeat_snap # num quarters, float
		snap = subbeat_snap * 4
		beat = beat / 4 * snap
		
		return RowTime(bar, beat, snap)
	
	def parse_mc(self, path):
		with open(path) as f:
			mc = json.load(f)
		gamemode = mc["meta"]["mode"]
		if gamemode != 0: # If not key mode, ignore
			#print(f"Warning: non-key chart ({gamemode}) will be ignored")
			return
		self.verify_mc(mc)
		
		song = self.get_song_by_malody_id(mc["meta"]["song"]["id"])
		chart = Chart() # Chart output object
		chart.source_path = path
		
		chart.creator = mc["meta"]["creator"]
		chart.chart_string = mc["meta"]["version"]
		chart.background = mc["meta"]["background"]
		chart.num_columns = mc["meta"]["mode_ext"]["column"]
		
		if "titleorg" in mc["meta"]["song"]:
			song.title = mc["meta"]["song"]["titleorg"]
			song.title_translit = mc["meta"]["song"]["title"]
		else:
			song.title = mc["meta"]["song"]["title"]
		
		if "artistorg" in mc["meta"]["song"]:
			song.artist = mc["meta"]["song"]["artistorg"]
			song.artist_translit = mc["meta"]["song"]["artist"]
		else:
			song.artist = mc["meta"]["song"]["artist"]
		
		# TODO: implement original titles in "org" subobject
		
		if "video" in mc["meta"]:
			chart.video = mc["meta"]["video"]
		
		bpm_changes = []
		for bpm_change in mc["time"]:
			row = self.parse_mc_rowtime(bpm_change["beat"])
			bpm = bpm_change["bpm"]
			bpm_changes.append((row, bpm))
		song.bpm_changes = bpm_changes
		
		notes = []
		for event in mc["note"]:
			if "column" in event:
				is_hold = "endbeat" in event
				
				column = event["column"]
				row = self.parse_mc_rowtime(event["beat"])
				note_type = NoteType.HOLD_HEAD if is_hold else NoteType.TAP
				notes.append(Note(column, row, note_type))
				
				if is_hold:
					end_row = self.parse_mc_rowtime(event["endbeat"])
					notes.append(Note(column, end_row, NoteType.TAIL))
			elif event["type"] == 1:
				song.audio = event["sound"]
				offset_ms = event.get("offset", 0)
				song.offset = offset_ms / 1000
				if event["vol"] != 100:
					print(f"Warning: 'vol' is not 100 but {event['vol']}")
			else:
				print(f"Warning: unknown event {json.dumps(event)}")
		# Sort notes chronologically and assign to chart
		chart.notes = sorted(notes, key=lambda note: note.row.absolute_bar())
		
		if song.audio is None:
			print("Warning: no audio file detected")
		
		song.charts.append(chart)

# Returns a note section in the following format:
###########
# 0101
# 1000
# 0011
# 0100
# ,
# 1010
# 0001
# 1100
# 0010
# 
########### (trailing newline)
def sm_note_data(notes, columns):
	# key = measure number, value = list of notes
	bars = {}
	for note in notes:
		if note.row.bar in bars:
			bars[note.row.bar].append(note)
		else:
			bars[note.row.bar] = [note]
	
	bar_texts = []
	for i in range(max(bars) + 1):
		bar_notes = bars.get(i, None)
		if bar_notes is None:
			bar_texts.append("0000\n0000\n0000\n0000")
			continue
		
		snaps = [note.row.snap for note in bar_notes]
		snap = lcm(snaps)
		rows = [[0] * columns for _ in range(snap)]
		
		for note in bar_notes:
			row_pos = round(note.row.beat / note.row.snap * snap)
			rows[row_pos][note.column] = note.note_type.to_sm()
		
		bar_texts.append("\n".join("".join(map(str, row)) for row in rows))
	
	return "\n,\n".join(bar_texts) + "\n"

def sm_bpm_string(song):
	bpm_strings = []
	for row, bpm in song.bpm_changes:
		absolute_bar = row.bar + row.beat / row.snap
		bpm_strings.append(f"{absolute_bar*4}={bpm}")
	return ",\n".join(bpm_strings)

def write_sm(song):
	o = ""
	
	background = song.charts[0].background # Bluntly discard every background but the first
	meta_mapping = {
		"TITLE": song.title,
		"TITLETRANSLIT": song.title_translit,
		"ARTIST": song.artist,
		"ARTISTTRANSLIT": song.artist_translit,
		"MUSIC": song.audio,
		"OFFSET": song.offset,
		"BACKGROUND": background,
		"BANNER": background, # Not sure if this is a good idea
		"BPMS": sm_bpm_string(song),
		# TODO: implement background video via BGCHANGES
	}
	
	for field, value in meta_mapping.items():
		if value is None:
			continue
		o += f"#{field}:{value};\n"
	
	for chart in song.charts:
		#print("Starting chart")
		note_section = sm_note_data(chart.notes, chart.num_columns)
		s = chart.chart_string or "" # Chart name e.g. "4k Super"
		o += f"\n//---------------dance-single - {s}----------------\n" \
				+ f"#NOTES:\n" \
				+ f"     dance-single:\n" \
				+ f"     :\n" \
				+ f"     Edit:\n" \
				+ f"     1:\n" \
				+ f"     0,0,0,0,0:\n" \
				+ f"{note_section};\n"
	
	return o

def copy_maybe(src, dst):
	if not os.path.exists(dst):
		shutil.copyfile(src, dst)

def build_library(malody_songs_dir):
	library = Library()
	
	mc_paths = glob(os.path.join(malody_songs_dir, "*/*/*.mc"))
	for path in mc_paths:
		try:
			library.parse_mc(path)
		except Exception as e:
			print(f"Error in {path}: {str(e)}")
	
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
				print(f"uh oh error while writing sm {source_path}")

def analyze(song_dir):
	sm_path = os.path.join(song_dir, "file.sm")
	minacalc_output = os.popen(f"./minacalc {sm_path}").readlines()
	
	overalls = []
	for line in minacalc_output:
		if line.startswith("Overall"):
			overalls.append(float(line[9:]))
	
	return overalls

def analyze_msd(basedir):
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
	# ~ library = build_library("../download-malody-charts/output")
	# ~ library.print_stats()
	
	output_dir = "output"
	# ~ assemble_sm_pack(library, output_dir)
	
	analyze_msd(output_dir)
	

if __name__ == "__main__":
	main()
