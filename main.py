from glob import iglob
import os
import util, sm, chart, mc, gh_chart

def main():
	library = chart.Library()
	
	# ~ paths = iglob("source/**/*.chart", recursive=True)
	# ~ path = next(paths)
	path = "source/rb3/rammstein - du hast/Rammstein - Du Hast.chart"
	
	settings = {
		"jolemode": True,
		"forcecreator": "Harmonix", # STUB: make this dynamic
		"cdtitle": "cdtitle.png",
		"audio": "audio.ogg",
	}
	gh_chart.parse(library, path, settings)
	
	print(sm.gen_sm(library.songs[0]))

if __name__ == "__main__":
	main()
