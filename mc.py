import json, re
import util
from chart import Song, Chart, RowTime, NoteType, Note

def get_song_by_malody_id(lib, malody_id):
	for song in lib.songs:
		if song.malody_id == malody_id:
			return song
	
	song = Song()
	song.malody_id = malody_id
	lib.songs.append(song)
	return song

def verify_mc(lib, mc):
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

def parse_mc_rowtime(lib, array):
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

def add_note_event(lib, chart, notes, event):
	is_hold = "endbeat" in event
	
	column = event["column"]
	if column >= chart.num_columns:
		# Some charts have notes on non-existing lanes.
		# Malody ignores those notes, so we do too
		return
	
	row = parse_mc_rowtime(lib, event["beat"])
	note_type = NoteType.HOLD_HEAD if is_hold else NoteType.TAP
	notes.append(Note(column, row, note_type))
	
	if is_hold:
		end_row = parse_mc_rowtime(lib, event["endbeat"])
		notes.append(Note(column, end_row, NoteType.TAIL))
	
	return notes

def parse(lib, path, verify=True, keymode_filter=None):
	with open(path) as f:
		mc = json.load(f)
	if mc["meta"]["mode"] != 0:
		return # If not key mode, ignore
	if verify: verify_mc(lib, mc)
	if keymode_filter and keymode_filter != mc["meta"]["mode_ext"]["column"]:
		return # Chart with wrong keymode is filtered
	
	song = get_song_by_malody_id(lib, mc["meta"]["song"]["id"])
	chart = Chart() # Chart output object
	chart.source_path = path
	
	chart.creator = mc["meta"]["creator"]
	chart.chart_string = mc["meta"]["version"]
	chart.background = mc["meta"].get("background", None)
	chart.num_columns = mc["meta"]["mode_ext"]["column"]
	chart.may_be_keysounded = False
	
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
		row = parse_mc_rowtime(lib, bpm_change["beat"])
		bpm = bpm_change["bpm"]
		bpm_changes.append((row, bpm))
	song.bpm_changes = bpm_changes
	
	has_found_audio = False
	
	notes = []
	for event in sorted(mc["note"], key=lambda e: e["beat"][0]):
		if "column" in event: # Note event
			add_note_event(lib, chart, notes, event)
		
		if "sound" in event: # Audio event (may be keysounded)
			# If song already has audio, ignore
			if has_found_audio:
				chart.may_be_keysounded = True
				continue
			has_found_audio = True
			
			if "column" in event and event["column"] < chart.num_columns: # If keysounded
				print("Warning: Using keysound on first beat as song audio")
			
			# Audio can start at for example the second bar. We have
			# to add this into the .sm offset calculation.
			audio_start_row = parse_mc_rowtime(lib, event["beat"])
			audio_start_time = util.get_seconds_at(song.bpm_changes, audio_start_row)
			
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
