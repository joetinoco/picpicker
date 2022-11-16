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

# Calculate an absolute count of files to be picked,
# by parsing/validating a string and then applying 
# the value or percentage to a total amount.
# Also adjusts the amount if it's greater then the available picks.
# Returns -1 if the amount cannot be calculated.
def parsePickCountString(amountString, available):
    if available == 0:
        return -1

    if '%' in amountString:
        pickCount = int((int(amountString.replace('%','')) / 100 ) * available)
    else:
        pickCount = int(amountString)

    if pickCount > available:
        log('Warning - not enough matches available, will pick as much as possible')
        pickCount = available
    
    return pickCount

# Parse "ensure" rules. They have the format: <number> '<pattern>',
# where <number> can be an absolute amount (2, 7, etc.) or a percentage
def parseRule(ruleString):
    rule = {}
    ruleParts = re.search('^([0-9]+%?)\s\'(.+)\'$', ruleString)
    rule['count'] = ruleParts.group(1)
    rule['pattern'] = ruleParts.group(2)
    return rule

# Pick files from the eligible files list according to a pick rule
def pickByRule(eligibleFiles, rule):
    pickedFiles = []
    matchIndexes = []
    for i in range(len(eligibleFiles)):
        if anyMatches(eligibleFiles[i], [rule['pattern']]):
            matchIndexes.append(i)

    pickCount = parsePickCountString(rule['count'], len(matchIndexes))

    if pickCount < 0:
        log('Warning - cannot ensure ', rule['count'], ' files matching pattern "', rule['pattern'], '", check if the files/directories really exist.')
    else:
        log('Ensuring ', pickCount, ' of ', len(matchIndexes),' files that match pattern "', rule['pattern'], '"')
        matchIndexes.sort(reverse=True)
        i = 0
        while i < pickCount:
            pickedFiles.append(eligibleFiles[matchIndexes[i]])
            eligibleFiles.pop(matchIndexes[i])
            i += 1
  
    return pickedFiles
    
# Get all eligible files from a path
def collectAvailableFiles(path, selector):
    log('Scanning source path: ', path + selector)
    availableFilesIterator = glob.iglob(path + selector, recursive=True)
    availableFiles = list(availableFilesIterator)
    log('Found ', str(len(availableFiles)), ' potential files')
    return availableFiles

# Apply exclusion rules to eligibleFiles and returns a new list with them filtered out
def applyExcludes(availableFiles, pathsToExclude):
    eligibleFiles = [file for file in availableFiles if not anyMatches(file, pathsToExclude)]
    log('Excluded ', len(availableFiles) - len(eligibleFiles), ' files using the "exclude" patterns')
    return eligibleFiles

# Return all files matching the "ensure" rules
def pickRequired(eligibleFiles, ensureRules):
    pickedFiles = []
    for ruleString in ensureRules:
        rule = parseRule(ruleString)
        pickedFiles += pickByRule(eligibleFiles, rule)
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

    pickedFiles += pickRequired(eligibleFiles, source['ensure'])

    log('Picked a total of ', len(pickedFiles), ' required files.')

#    pickRandoms(selectedFiles, filteredEligibleFiles)

# Make a selection to fill the maxSize

# Copy the selection to the target folder