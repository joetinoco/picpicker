import datetime, sys, glob, re, shutil, os.path, yaml, re, random, ffmpeg, PIL
from PIL import Image, ImageOps

# Fix for Unicode strings in yaml - https://stackoverflow.com/a/2967461
from yaml import Loader, SafeLoader

def construct_yaml_str(self, node):
    # Override the default string handling function 
    # to always return unicode objects
    return self.construct_scalar(node)
Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)

###########################
## Globals
sources = []
target = {}

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

# Convert a byte number into a nicely formated MB string
def toMbString(bytes):
    return str(int(bytes / (1024*1024))) + " MB"

# Return a random file name with the given extension
def randomFileName(extension):
    return '/' + str(random.randint(0,999999999)).zfill(9) + extension

# Matches a string against several patterns, returns True if it contains any of them
def anyMatches(string, patterns):
    for pattern in patterns:
        if pattern in string:
            return True
    return False    

# Parse and validate configuration
def parseConfig(configFilePath):
    global sources
    global target
    with open(configFilePath, "r") as configfile:
        try:
            config = yaml.safe_load(configfile)
            log('Using config file - ', configFilePath)
        except yaml.YAMLError as exc:
            abort('Error loading config file.', exc)

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
# Returns -1 if the amount cannot be calculated.
def parsePickCountString(amountString, available):
    if available == 0:
        return -1
    if '%' in amountString:
        pickCount = int((int(amountString.replace('%','')) / 100 ) * available)
    else:
        pickCount = int(amountString)
    return pickCount

# Parse "ensure" rules. They have the format: <number> '<pattern>',
# where <number> can be an absolute amount (2, 7, etc.) or a percentage
def parseRule(ruleString):
    rule = {}
    ruleParts = re.search('^([0-9]+%?)\s\'(.+)\'$', ruleString)
    rule['count'] = ruleParts.group(1)
    rule['pattern'] = ruleParts.group(2)
    return rule

# Pick a random item from a list and remove it from the list
def randomPickFrom(list):
    pick = random.choice(list)
    list.remove(pick)
    return pick

# Pick files from the eligible files list according to a pick rule
def pickByRule(eligibleFiles, rule):
    pickedFiles = []
    matchIndexes = []
    for i in range(len(eligibleFiles)):
        if anyMatches(eligibleFiles[i], [rule['pattern']]):
            matchIndexes.append(i)

    pickCount = parsePickCountString(rule['count'], len(matchIndexes))
    if pickCount > len(matchIndexes):
        log('Warning - not enough matches available for pattern "', rule['pattern'], '", will pick as much as possible')
        pickCount = len(matchIndexes)

    if pickCount < 0:
        log('Warning - cannot pick ', rule['count'], ' files matching pattern "', rule['pattern'], '", check if the files/directories really exist.')
    else:
        while pickCount > 0:
            pickIndex = randomPickFrom(matchIndexes)
            pickedFiles.append(eligibleFiles[pickIndex])
            pickCount -= 1
        for pickedFile in pickedFiles:
            eligibleFiles.remove(pickedFile)
  
    return pickedFiles

# Return all files matching the "ensure" rules
def pickRequired(eligibleFiles, ensureRules):
    pickedFiles = []
    for ruleString in ensureRules:
        rule = parseRule(ruleString)
        log('Ensuring at least ', rule['count'], ' files that match pattern "', rule['pattern'], '"')
        pickedFiles += pickByRule(eligibleFiles, rule)
    return pickedFiles    
    
# Get all eligible files from a path
def collectAvailableFiles(path, selector):
    log('Scanning source path: ', path + selector)
    availableFilesIterator = glob.iglob(path + selector, recursive=True)
    availableFiles = list(availableFilesIterator)
    return availableFiles

# Apply exclusion rules to available files
def applyExcludes(fileList, pathsToExclude):
    excludedFiles = [file for file in fileList if anyMatches(file, pathsToExclude)]
    for exclusion in excludedFiles:
        fileList.remove(exclusion)

# Apply limit rules to eligibleFiles and returns the list with them filtered out
def applyLimits(fileList, limitRules):
    for ruleString in limitRules:
        rule = parseRule(ruleString)
        limitedPicks = pickByRule(fileList, rule)
        # Remove all files with the rule pattern
        applyExcludes(fileList, [rule['pattern']])
        # Re-add just the limited subset
        fileList += limitedPicks
        log('Limiting to a maximum of ', len(limitedPicks), ' files matching pattern "', rule['pattern'], '"')

# Copy all files from the list to the target folder.
# The destination file names are randomized, and
# the files are resized to the desired resolution.
# Returns the total bytes copied.
def resizeAndCopyFiles(fileList):
    maxWidth = int(target['maxWidth'])
    maxHeight = int(target['maxHeight'])
    bytes = 0
    for sourceFile in fileList:
        try:
            fileName, fileExt = os.path.splitext(sourceFile)
            targetFile = target['path'] + randomFileName(fileExt)
            image = ImageOps.exif_transpose(Image.open(sourceFile)) # Apply EXIF orientation
            image.thumbnail((maxWidth, maxHeight)) # Resizes preserving aspect ratio
            image.save(targetFile)
            bytes += os.stat(targetFile).st_size
        except Exception as ex:
            log('Error copying ', sourceFile,' - ', str(ex))
    return bytes

################################################################################
################################################################################
################################################################################

if len(sys.argv) < 2:
    abort("Missing config file path. Usage: picpicker <config.yaml>")

parseConfig(sys.argv[1])
byteCount = 0

# Process sources
for sourceName in sources:
    log('Processing source: ', sourceName)
    source = sources[sourceName]

    availableFiles = collectAvailableFiles(source['path'], source['filePattern'])
    log('Potential file count: ', len(availableFiles))

    applyExcludes(availableFiles, source['exclude'])
    log('Excluded files via exclusion patterns.')
    log('Potential file count: ', len(availableFiles))

    applyLimits(availableFiles, source['limit'])
    log('Potential file count: ', len(availableFiles))

    requiredFiles = pickRequired(availableFiles, source['ensure'])
    log('Potential file count: ', len(availableFiles))

    fileCount = len(requiredFiles)
    requiredByteCount = resizeAndCopyFiles(requiredFiles)
    byteCount += requiredByteCount
    log('Picked a total of ', fileCount, ' required files (', toMbString(requiredByteCount),').')

byteCountCap = target['maxSize'] * (1024*1024)
if (byteCount > byteCountCap):
    log('Warning: required files exceed the maximum size for the target directory.')
else:
    log('Filling the rest of the target folder with random picks (up to ', target['maxSize'], ' MB)')
    while byteCount < byteCountCap:
        if len(availableFiles) == 0:
            log('Warning - not enough files to fill out target folder.')
            break
        byteCount += resizeAndCopyFiles([randomPickFrom(availableFiles)])
        fileCount += 1
    
log('Finished: copied a total of ', fileCount, ' files (', toMbString(byteCount), ')')