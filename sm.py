import math
import copy
import util
from util import lcm, gcd

CHART_TYPE_STRINGS = {
	4: ["dance-single"],
	5: ["pump-single"],
	6: ["dance-solo"],
	7: ["kb7-single"],
	8: ["dance-double", "bm-single7"],
	9: ["pnm-nine"],
	10: ["pump-double"],
}

# Replace colons and semicolons with spaces
def escape(string):
	return string.replace(":", " ").replace(";", " ")

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
########### (no trailing newline)
def sm_note_data(notes, columns):
	if len(notes) == 0: return "" # Some Malody charts are weird
	
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
			# The following generates e.g. for 6k
			# "000000\n000000\n000000\n000000"
			bar_texts.append("\n".join(["0" * columns] * 4))
			continue
		
		snaps = [note.row.snap for note in bar_notes]
		beats = [note.row.beat for note in bar_notes]
		snap = lcm(snaps)
		snap = snap // gcd([snap, *beats]) # Snap is unneccesarily big sometimes
		snap = min(192, snap) # Limit snap to 192nds
		
		rows = [[0] * columns for _ in range(snap)]
		
		for note in bar_notes:
			row_pos = round(note.row.beat / note.row.snap * snap)
			try:
				rows[row_pos][note.column] = note.note_type.to_sm()
			except Exception as e:
				print(row_pos, note.column)
				print("Columns", columns, "Snap", snap)
				raise e
		
		bar_texts.append("\n".join("".join(map(str, row)) for row in rows))
	
	return "\n,\n".join(bar_texts)

def sm_bpm_string(song):
	# Make copy of bpm changes cuz they'll be modified
	# Also turn RowTime's into numbers
	rows = [row.absolute_bar() for row, bpm in song.bpm_changes]
	bpms = [bpm for row, bpm in song.bpm_changes]
	
	# This loop snaps all bpm changes to the 192nds grid and adjusts
	# the bpm values to preserve sync. This is required because SM
	# can't handle bpm changes lying besides the 192nds grid.
	for i, (row, bpm) in enumerate(zip(rows, bpms)):
		# If bpm change lies on 192nd grid already, skip
		if util.is_whole(row * 192): continue
		
		# New row is snapped to the 192nd grid to satisfy SM
		new_row = round(row * 192) / 192
		
		time_mul_a = (new_row - rows[i-1]) / (row - rows[i-1])
		time_mul_b = (rows[i+1] - new_row) / (rows[i+1] - row)
		
		rows[i] = new_row
		bpms[i-1] *= time_mul_a
		bpms[i] *= time_mul_b
	
	bpm_strings = []
	for row, bpm in zip(rows, bpms):
		bpm_strings.append(f"{row*4}={bpm:.10}")
	return ",\n".join(bpm_strings)

def gen_sm(song):
	o = ""
	
	background = song.charts[0].background # Bluntly discard every background but the first
	meta_mapping = {
		"TITLE": song.title,
		"TITLETRANSLIT": song.title_translit,
		"ARTIST": song.artist,
		"ARTISTTRANSLIT": song.artist_translit,
		"MUSIC": song.audio,
		"OFFSET": song.offset,
		"CREDIT": ", ".join(song.get_creator_list()),
		"BACKGROUND": background,
		"BANNER": background,
		"BPMS": sm_bpm_string(song),
		# TODO: implement background video via BGCHANGES
	}
	
	for field, value in meta_mapping.items():
		if value is None:
			continue
		o += f"#{field}:{escape(str(value))};\n"
	
	for chart in song.charts:
		note_section = sm_note_data(chart.notes, chart.num_columns)
		difficulty = chart.difficulty or 1
		chart_string_escaped = escape(chart.chart_string)
		for type_string in CHART_TYPE_STRINGS[chart.num_columns]:
			o += f"\n// Credit for this chart goes to Malody mapper \"{chart.creator}\"\n"
			o += f"//---------------{type_string} - {chart.chart_string}----------------\n" \
					+ f"#NOTES:\n" \
					+ f"     {type_string}:\n" \
					+ f"     {chart_string_escaped}:\n" \
					+ f"     Edit:\n" \
					+ f"     {difficulty}:\n" \
					+ f"     0,0,0,0,0:\n" \
					+ f"{note_section}\n;\n"
	
	return o

