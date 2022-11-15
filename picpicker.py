import datetime, sys, glob, re, shutil, os.path, time, yaml

###########################
## Globals
sources = []
target = {}
files = []

###########################
## Internal functions

def log(msg, *others):
    if len(others) == 0:
        print(datetime.datetime.now(), str(msg))
    else:
        strOthers = ""
        for other in others:
            strOthers = strOthers + str(other)
        print(datetime.datetime.now(), str(msg) + strOthers)
        

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
    log('Scanning source path: ', path + selector)
    eligibleFilesIterator = glob.iglob(path + selector)
    eligibleFiles = list(eligibleFilesIterator)
    log('Found ', str(len(eligibleFiles)), ' potential files')
    return eligibleFiles

# Apply exclusion rules to eligibleFiles and returns a new list with them filtered out
def applyExcludes(eligibleFiles, pathsToExclude):
    def isExcluded(file):
        for path in pathsToExclude:
            if path in file:
                return True
        return False

    filteredFiles = [file for file in eligibleFiles if not isExcluded(file)]
    log('Excluded ', len (eligibleFiles) - len(filteredFiles), ' files using the "exclude" patterns')
    return filteredFiles



################################################################################
################################################################################
################################################################################

parseConfig()

# Process sources
for sourceName in sources:
    log('Processing source: ', sourceName)
    source = sources[sourceName]

    eligibleFiles = collectEligibleFiles(source['path'], source['filePattern'])

    eligibleFiles = applyExcludes(eligibleFiles, source['exclude'])

#    files = pickRequred(eligibleFiles, source['ensure'])

#    pickRandoms(files, eligibleFiles)

# Make a selection to fill the maxSize

# Copy the selection to the target folder