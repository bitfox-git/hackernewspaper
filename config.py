from os import environ

# optional, without a key YouTube links are handled like any other link (screenshot)
YOUTUBE_API_KEY = environ.get("YOUTUBE_API_KEY", "")

# set by configure(), the edition being built and where its downloads are cached
ISSUE = None
asset_dir = None


def configure(issue):
    global ISSUE, asset_dir
    ISSUE = str(issue)
    asset_dir = f"dist/{ISSUE}/"
