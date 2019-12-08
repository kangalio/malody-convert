import json, re
from enum import Enum
from collections import Counter
import util

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
	
	def __repr__(self):
		return f"{self.bar}:{self.beat}/{self.snap}"
	
	def absolute_bar(self):
		return round(self.bar + self.beat / self.snap, 10)

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
		self.difficulty = None # Can be None
		self.notes = None
		
		self.source_path = None
	
	def __eq__(self, other):
		return self.creator == other.creator \
			and self.chart_string == other.chart_string \
			and self.num_columns == other.num_columns

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
		self.is_keysounded = None
	
	def get_creator_list(self):
		creators = [chart.creator for chart in self.charts]
		return list(set(creators)) # Filter out duplicates

class Library:
	def __init__(self, songs=[]):
		self.songs = songs
	
	def print_stats(self):
		charts = [chart for song in self.songs for chart in song.charts]
		print(f"{len(self.songs)} songs, {len(charts)} charts")
		keys_counter = Counter(c.num_columns for c in charts)
		keys = sorted(keys_counter.keys())
		print(", ".join(f"{k}k: {keys_counter[k]}" for k in keys))
	
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
		
		# Malody - the fun game where subbeats and snaps can be negative
		if subbeat_snap < 0:
			# The following code can't handle negative snap, it _can_
			# handle negative subbeat though. So we negate both to have
			# a postive snap and a negative subbeat (that's effectively
			# the same)
			subbeat_snap = -subbeat_snap
			subbeat = -subbeat
		
		bar = beats // 4
		beat = (beats % 4) + subbeat / subbeat_snap
		snap = subbeat_snap * 4
		beat = round(beat / 4 * snap) # Float should be whole number now. Round to make int
		
		# Some charts have their beats "overflowing" to the next
		# bar, e.g. (13, 4, 4) effectively being (14, 0, 4)
		bar += beat // snap
		beat = beat % snap
		
		return RowTime(bar, beat, snap)
	
	def add_note_event(self, chart, notes, event):
		is_hold = "endbeat" in event
		
		column = event["column"]
		if column >= chart.num_columns:
			# Some charts have notes on non-existing lanes.
			# Malody ignores those notes, so we do too
			return
		
		row = self.parse_mc_rowtime(event["beat"])
		note_type = NoteType.HOLD_HEAD if is_hold else NoteType.TAP
		notes.append(Note(column, row, note_type))
		
		if is_hold:
			end_row = self.parse_mc_rowtime(event["endbeat"])
			notes.append(Note(column, end_row, NoteType.TAIL))
		
		return notes
	
	def parse_mc(self, path, verify=True, keymode_filter=None):
		with open(path) as f:
			mc = json.load(f)
		if mc["meta"]["mode"] != 0:
			return # If not key mode, ignore
		if verify: self.verify_mc(mc)
		if keymode_filter and keymode_filter != mc["meta"]["mode_ext"]["column"]:
			return # Chart with wrong keymode is filtered
		
		song = self.get_song_by_malody_id(mc["meta"]["song"]["id"])
		chart = Chart() # Chart output object
		chart.source_path = path
		
		chart.creator = mc["meta"]["creator"]
		chart.chart_string = mc["meta"]["version"]
		chart.background = mc["meta"].get("background", None)
		chart.num_columns = mc["meta"]["mode_ext"]["column"]
		chart.is_keysounded = False
		
		if chart in song.charts: return # Duplicate chart
		
		# Try to smartly find difficulty from the chart string
		numbers = map(int, re.findall(r"\d+", chart.chart_string))
		numbers = [n for n in numbers if n != chart.num_columns and n < 100]
		if len(numbers) == 1: # Only use when found unambigous match
			chart.difficulty = numbers[0]
		
		song.title = mc["meta"]["song"]["title"]
		song.artist = mc["meta"]["song"]["artist"]
		
		if "titleorg" in mc["meta"]["song"]:
			song.title_translit = song.title
			song.title = mc["meta"]["song"]["titleorg"]
		
		if "artistorg" in mc["meta"]["song"]:
			song.artist_translit = song.artist
			song.artist = mc["meta"]["song"]["artistorg"]
		
		if "org" in mc["meta"]["song"]:
			org = mc["meta"]["song"]["org"]
			if "title" in org and org["title"] != "":
				song.title_translit = song.title
				song.title = org["title"]
			if "artist" in org and org["artist"] != "":
				song.artist_translit = song.artist
				song.artist = org["artist"]
		
		chart.video = mc["meta"].get("video", None)
		
		bpm_changes = []
		for bpm_change in mc["time"]:
			row = self.parse_mc_rowtime(bpm_change["beat"])
			bpm = bpm_change["bpm"]
			bpm_changes.append((row, bpm))
		song.bpm_changes = bpm_changes
		
		has_warned_about_keysounds = False
		
		notes = []
		for event in sorted(mc["note"], key=lambda e: e["beat"][0]):
			if "column" in event: # Note event
				self.add_note_event(chart, notes, event)
			
			if "sound" in event: # Audio event (may be keysounded)
				# If song already has audio, ignore
				if song.audio is not None: continue
				
				if "column" in event and event["column"] < chart.num_columns: # If keysounded
					print("Warning: Using keysound on first beat as song audio")
				
				# Audio can start at for example the second bar. We have
				# to add this into the .sm offset calculation.
				audio_start_row = self.parse_mc_rowtime(event["beat"])
				audio_start_time = util.get_seconds_at(song.bpm_changes, audio_start_row)
				print(f"Audio starts at {audio_start_time} seconds")
				
				song.audio = event["sound"]
				offset_ms = event.get("offset", 0)
				song.offset = audio_start_time + offset_ms / 1000
				# There is also the 'vol' tag which sets the song's
				# volume. I see absolutely no reason to have that tag
				# and it's not supported in SM anyway so we won't do
				# anything about it here
		
		# Sort notes chronologically and assign to chart
		chart.notes = sorted(notes, key=lambda note: note.row.absolute_bar())
		
		if song.audio is None:
			print("Warning: no audio file detected")
		
		song.charts.append(chart)
	
	# Removes empty songs
	def clean_empty_songs(self):
		self.songs = [s for s in self.songs if len(s.charts) != 0]
