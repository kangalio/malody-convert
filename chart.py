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

class DiffType(Enum):
	NOVICE = 0
	EASY = 1
	MEDIUM = 2
	HARD = 3
	EXPERT = 4
	EDIT = 5

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
		self.diff_type = None
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
		self.creator = None
		self.creator_img = None
		self.bpm_changes = None # List of tuples (RowTime, bpm int)
		self.malody_id = None
		self.may_be_keysounded = None
	
	def get_creator_list(self):
		creators = [chart.creator for chart in self.charts if chart.creator]
		creators.append(self.creator)
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
	
	# Removes empty songs
	def clean_empty_songs(self):
		self.songs = [s for s in self.songs if len(s.charts) != 0]
