import json, os
from util import lcm
from tqdm import tqdm
from enum import Enum

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
	
	# Goes through all charts and tries to find a background picture.
	# If there's different pictures used in each chart, it picks one
	def find_common_bg(self):
		bg = self.charts[0].background
		# If any chart has a different background, warn
		if any(other.background != bg for other in self.charts[1:]):
			print(f"Warning: Different backgrounds")
		return bg

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
	
	background = song.find_common_bg()
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

# ~ path = "../download-malody-charts/output/_song_9738/43703/1562241155.mc"
path = "/home/kangalioo/misc/small-programs/Malody-4.3.7/beatmap/_temp_1575194910/1575194910.mc"
library = Library()
import glob, random
mc_paths = glob.glob("charts/*/*.mc")
for path in mc_paths:
	# ~ with open(path) as f: print(json.dumps(json.load(f), indent=4))
	try:
		library.parse_mc(path)
	except Exception as e:
		print(f"Error in {path}")
		raise e
library.print_stats()
for song in library.songs:
	source_path = song.charts[0].source_path
	target_path = os.path.join(os.path.dirname(source_path), "chart.sm")
	with open(target_path, "w") as f:
		print(f"Writing chart from {source_path} into {target_path}")
		f.write(write_sm(song))
