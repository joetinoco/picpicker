import datetime, sys, glob, re, shutil, os.path, time, yaml

###########################
## Globals
sources = []
target = {}
files = []

###########################
## Internal functions

def log(msg, *others):
    if len(others) > 0:
        print(datetime.datetime.now(), msg, " ".join(others))
    else:
        print(datetime.datetime.now(), msg)

def abort(msg, *others):
    log(msg, others)
    log('Error is fatal, aborting.')
    exit(1)

# Parse and validate configuration
def parseConfig():
    global sources
    global target
    with open("picpicker.yaml", "r") as configfile:
        try:
            config = yaml.safe_load(configfile)
            log('Config file loaded.')
        except yaml.YAMLError as exc:
            abort('Error loading picpicker.yaml', exc)

    # Validate target    
    if 'target' not in config.keys():
        abort("Config file has no 'target' specified.")
    
    target = config['target']
    if 'path' not in target.keys():
        abort('Target configs are missing a destination path.')
    if not os.path.isdir(target['path']):
        log('Destination path does not exist; creating ', target['path'])
        os.mkdir(target['path'])        

    if 'sources' not in config.keys():
        abort("Config file has no 'sources' specified.")

    sources = config['sources']
    
# Get all eligible files from a path
def collectEligibleFiles(path, selector):
    eligibleFiles = glob.iglob(path + selector)
    for fileItem in eligibleFiles:
        log('Found eligible file -', fileItem)

################################################################################
################################################################################
################################################################################

parseConfig()

# Collect all eligible files from sources
for sourceName in sources:
    log('Processing source:', sourceName)
    source = sources[sourceName]
    log('Path for source: ', source['path'])
    collectEligibleFiles(source['path'], source['filePattern'])


# Process 'excludes'

# Process 'ensures'

# Make a selection to fill the maxSize

# Copy the selection to the target folder