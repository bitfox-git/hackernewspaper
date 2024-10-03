import sys

#read the first argument from the command line and use it as the issue number, second argument is the latest git tag
if len(sys.argv) > 1:
    ISSUE = sys.argv[1]
    LATEST_GIT_TAG = int(sys.argv[2])
else:
    ISSUE = "675" 



#Some weird url workarounds....
if ISSUE == "675":
    ISSUE= "674-2563024"
    
asset_dir = f"dist/{ISSUE}/"