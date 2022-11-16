import datetime, sys, glob, re, shutil, os.path, time, yaml, re

###########################
## Globals
sources = []
target = {}
pickedFiles = []

###########################
## Internal functions

# Simple logger
def log(msg, *others):
    if len(others) == 0:
        print(datetime.datetime.now(), str(msg))
    else:
        strOthers = ""
        for other in others:
            strOthers = strOthers + str(other)
        print(datetime.datetime.now(), str(msg) + strOthers)
        
# Log an error and quit program
def abort(msg, *others):
    log(msg, others)
    log('Error is fatal, aborting.')
    exit(1)

# Matches a string against several patterns, returns True if it contains any of them
def anyMatches(string, patterns):
    for pattern in patterns:
        if pattern in string:
            return True
    return False

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

# Parse "ensure" rules. They have the format: <number> '<pattern>',
# where <number> can be an absolute amount (2, 7, etc.) or a percentage
def parseRule(ruleString):
    rule = {}
    ruleParts = re.search('^([0-9]+%?)\s\'(.+)\'$', ruleString)
    rule['count'] = ruleParts.group(1)
    rule['pattern'] = ruleParts.group(2)
    return rule

def pickByRule(eligibleFiles, rule):
    log('Picking ', rule['count'], ' files that match the pattern "', rule['pattern'], '"')
    
# Get all eligible files from a path
def collectAvailableFiles(path, selector):
    log('Scanning source path: ', path + selector)
    availableFilesIterator = glob.iglob(path + selector)
    availableFiles = list(availableFilesIterator)
    log('Found ', str(len(availableFiles)), ' potential files')
    return availableFiles

# Apply exclusion rules to eligibleFiles and returns a new list with them filtered out
def applyExcludes(availableFiles, pathsToExclude):
    eligibleFiles = [file for file in availableFiles if anyMatches(file, pathsToExclude)]
    log('Excluded ', len (availableFiles) - len(eligibleFiles), ' files using the "exclude" patterns')
    return eligibleFiles

# Return all files matching the "ensure" rules
def pickRequired(eligibleFiles, ensureRules):
    pickedFiles = []
    for ruleString in ensureRules:
        rule = parseRule(ruleString)
        pickedFiles.append(pickByRule(eligibleFiles, rule))
    # TODO remove picked files from the list of eligible files
    return pickedFiles


################################################################################
################################################################################
################################################################################

parseConfig()

# Process sources
for sourceName in sources:
    log('Processing source: ', sourceName)
    source = sources[sourceName]

    availableFiles = collectAvailableFiles(source['path'], source['filePattern'])

    eligibleFiles = applyExcludes(availableFiles, source['exclude'])

    pickedFiles.append(pickRequired(eligibleFiles, source['ensure']))

#    pickRandoms(selectedFiles, filteredEligibleFiles)

# Make a selection to fill the maxSize

# Copy the selection to the target folder