from chart import Song, Chart, DiffType, RowTime

# All possible section names:
# [Song]
# [SyncTrack]
# [Events]
# [EasyDoubleBass]
# [EasyEnhancedGuitar]
# [EasySingle]
# [ExpertDoubleBass]
# [ExpertEnhancedGuitar]
# [ExpertSingle]
# [HardDoubleBass]
# [HardEnhancedGuitar]
# [HardSingle]
# [MediumDoubleBass]
# [MediumEnhancedGuitar]
# [MediumSingle]

# Returns {section name: [(key, value)]}
def parse_sections(lines):
	section_name = None
	sections = {}
	
	for line in lines:
		line = line[:-1]
		
		if line.startswith("["):
			section_name = line[1:-1]
			sections[section_name] = []
		elif line == "{" or line == "}":
			pass
		else:
			kv_pair = line.strip().split(" = ", 1)
			sections[section_name].append(kv_pair)
	
	return sections

def parse_meta(song, tags, settings):
	meta = {}
	for key, value in tags:
		if value.startswith('"') and value.endswith('"'):
			value = value[1:-1]
		else:
			try:
				value = int(value)
			except ValueError:
				try:
					value = float(value)
				except:
					pass
		
		meta[key] = value
	
	if not "Name" in meta or meta["Name"] == "":
		print(f"Warning: no song title in chart")
	
	song.title = meta.get("Name", None)
	song.offset = meta.get("Offset", 0)
	# TODO: PreviewStart and PreviewEnd
	# TODO: Genre
	if "forcecreator" in settings:
		song.creator = settings["forcecreator"]
	else:
		song.creator = meta.get("Charter", None)
	song.creator_img = settings.get("cdtitle", None)
	song.audio = settings.get("audio", None)

def parse_sync(song, tags):
	bpm_changes = []
	
	for key, value in tags:
		time = int(key)
		event_type, event_value = value.split(" ")
		
		if event_type == "B": # Bpm
			bar = time / (192 * 4)
			beat = time % (192 * 4)
			rowtime = RowTime(bar, beat, 192 * 4)
			
			bpm = float(event_value) / 1000
			bpm_changes.append((rowtime, bpm))
		elif event_type == "TS": # Time signature
			pass # Not sure what to do with time signature
		else:
			raise Exception(f"Unknown sync event {key} = {value}")
	
	song.bpm_changes = bpm_changes

def parse_chart_lines(song, tags, diff_str, settings):
	chart = Chart()
	chart.num_columns = 5 # TODO: idk if GH can have non-5key charts too
	
	# Split e.g. "EasyEnhancedGuitar" into "Easy" and "EnhancedGuitar"
	diff_type = None
	chart_type = None
	for i in range(1, len(diff_str)):
		if diff_str[i].isupper():
			diff_type = diff_str[:i]
			chart_type = diff_str[i:]
			break
	else: raise Exception(f"Unknown diff string '{diff_str}'")
	
	# Set diff type and, in case of Edit, also set chart string to best
	# represent the GH diff
	if chart_type == "Single":
		# In case of the basic chart type just use the standard .sm diff
		# types. Map diff_type to .sm diff types and write into Chart
		diff_type = {
			"Easy": DiffType.EASY,
			"Medium": DiffType.MEDIUM,
			"Hard": DiffType.HARD,
			"Expert": DiffType.EXPERT,
		}.get(diff_type, None)
		if diff_type is None:
			raise Exception(f"Unknown diff type '{diff_str}'")
		chart.diff_type = diff_type
	else:
		# If we have DoubleBass or EnhancedGuitar we have to get fancy
		# with Edit diff
		chart.diff_type = DiffType.EDIT
		
		if settings.get("jolemode", False):
			# jole wanted to discard everything except ExpertDoubleBass
			# which should be saved as "EXPERT+" Edit
			if diff_type == "Expert" and chart_type == "DoubleBass":
				chart.chart_string = "EXPERT+"
			else:
				return # Discard everything else
		else:
			# In the general case I think it#s sensible to add a "+" to
			# DoubleBass and add " G" to EnhancedGuitar charts
			if chart_type == "DoubleBass":
				chart.chart_string = diff_type + "+"
			elif chart_type == "EnhancedGuitar":
				chart.chart_string = diff_type + " G"
			else:
				raise Exception(f"Unknown chart type '{chart_type}'")
	
	# STUB: parse the actual notes
	chart.notes = []
	
	song.charts.append(chart)

# `settings` is a dict controlling some aspects of the parsing:
# 	"forcecreator": Forces a specific value for the creators
# 	"jolemode": Changes the behavior on diff type parsing
#	"cdtitle": Value for cdtitle (wow)
#	"audio": Value for audio
def parse(lib, path, settings):
	with open(path) as f: lines = f.readlines()
	
	song = Song()
	
	sections = parse_sections(lines)
	for section_name, tags in sections.items():
		difficulty = None
		if any(section_name.startswith(diff_type) for diff_type in ["Easy", "Medium", "Hard", "Expert"]):
			chart = parse_chart_lines(song, tags, section_name, settings)
		elif section_name == "Song":
			parse_meta(song, tags, settings)
		elif section_name == "SyncTrack":
			parse_sync(song, tags)
		elif section_name == "Events":
			# The Events section holds annotations to specific regions
			# inside the chart, like build-up, verse and so on.
			# TODO: Implement this
			pass
		else:
			raise Exception(f"Unknown section name '{section_name}'")
	
	lib.songs.append(song)
