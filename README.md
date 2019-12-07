# malody-convert
I wrote these Python files to convert rhythm game files from one format to another, specifically from Malody's .mc format to the widely used .sm format.

**chart.py** contains the data classes, and also the .mc parsing as class methods

**sm.py** contains the function to convert a Song class object to a .sm string

**main.py** and **convert.py** are messy, non-reusable scripts that I'm using to bulk convert the Malody charts I scraped (shoutout to [my other project](https://github.com/kangalioo/malody-scrape))
