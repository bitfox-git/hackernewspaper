import sys
from os import environ

#read the first argument from the command line and use it as the issue number
if len(sys.argv) > 1:
    ISSUE = sys.argv[1]
else:
    sys.exit("Usage: python generator.py <issue number>")

# optional, without a key YouTube links are handled like any other link (screenshot)
YOUTUBE_API_KEY = environ.get("YOUTUBE_API_KEY", "")

asset_dir = f"dist/{ISSUE}/"
