# A Quick & Dirty Python Script:
# - to copy Heroku Configuration Variables from one Application...
# ...to one or more other Heroku Applications.
# Execute:
# 'heroku login' first, before executing the script.
# Execute:
# 'python3 loadHerokuConfigVars.py <Heroku App Name to Copy From> <Heroku App Name 1 to copy to> <Heroku App Name 'n' to copy to>'

import subprocess
import sys


# Save Heroku Application Configuration Variables to a local file.
# Add this filename to '.gitignore' or there will be trouble as it can contain SECRET_KEY and PASSWORDS.
with open("HerokuConfigVars.txt", "w") as writeFile:
    herokuFromConfig = subprocess.run(["heroku", "config", "--app", f"{sys.argv[1]}"], capture_output=True, text=True)
    writeFile.write(herokuFromConfig.stdout)


# Set Heroku Application(s) Configuration Variables
for argCounter, arg in enumerate(sys.argv):
    if argCounter > 1:
        print(argCounter, arg)
        with open("HerokuConfigVars.txt", "r") as readFile:
            for counter, line in enumerate(readFile):
                if counter > 0:
                    newLine = line.replace(": ", "=").replace(" ", "").replace("\n", "")
                    subprocess.run(["heroku", "config:set", "--app", f"{arg}", f"{newLine}"])


if __name__ == "__main__":
    print("\n --- * --- Heroku Application Configuration Variable Copier --- * ---")
