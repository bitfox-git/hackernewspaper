import sys

#read the first argument from the command line and use it as the issue number
if len(sys.argv) > 1:
    ISSUE = sys.argv[1]
else:
    ISSUE = "675" 



#Some weird url workarounds....
if ISSUE == "675":
    ISSUE= "674-2563024"
    
asset_dir = f"dist/{ISSUE}/"