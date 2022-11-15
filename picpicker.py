import datetime, sys, glob, re, shutil, os.path, time, yaml

###########################
## Globals
config = {}

###########################
## Internal functions

def log(msg, *others):
    if len(others) > 0:
        print(datetime.datetime.now(), msg, " ".join(others))
    else:
        print(datetime.datetime.now(), msg)

# Parse and validate configuration
def parseConfig():
    with open("picpicker.yaml", "r") as configfile:
        try:
            config = yaml.safe_load(configfile)
            log('Config file loaded.')
            yaml.dump(config)
        except yaml.YAMLError as exc:
            log('Error loading picpicker.yaml', exc)
            exit(1)
    
def ensureDestPathExists(path):
    pathElems = path.split("\\")[1:]
    currPath = ""
    for pathElem in pathElems:
        currPath += "\\" + pathElem
        if os.path.isdir(currPath) == False:
            log('Destination path does not exist; creating ', currPath)
            os.mkdir(currPath)
    
# Get files and archive them in their respective year-month\day path
def processFiles(path, selector, dest):
    files = glob.iglob(path + selector)
    for fileItem in files:
        fileName = fileItem[len(path) + 1:] # Strip path from filename
        destPath = dest + "\\" + getYearMonth(fileName) + "\\" + getDay(fileName)
        ensureDestPathExists(destPath)
        try:
            shutil.move(fileItem, destPath)
        except:
            log("Error moving", fileName)
        log(fileName, "archived.")

################################################################################
################################################################################
################################################################################

parseConfig()