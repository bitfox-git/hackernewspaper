import sys
from os import environ

#read the first argument from the command line and use it as the issue number
if len(sys.argv) > 1:
    ISSUE = sys.argv[1]
else:
    ISSUE = "675" 

YOUTUBE_API_KEY = environ["YOUTUBE_API_KEY"]

#Some weird url workarounds....
if ISSUE == "675":
    ISSUE= "674-2563024"
    
asset_dir = f"dist/{ISSUE}/"