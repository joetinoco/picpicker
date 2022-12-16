import datetime, sys, glob, re, os.path, yaml, re, random
from PIL import Image, ImageOps, ImageFont, ImageDraw

###########################
## Globals
sources = []
target = {}
crlfMissing = False # Used as a flag for logging
portraitBuffer = None # Used by the `twoPortraits` flag

###########################
## Internal functions

# Simple logger
def log(msg, *others):
    global crlfMissing
    if crlfMissing:
        print('')
        crlfMissing = False
    if len(others) == 0:
        print(datetime.datetime.now(), str(msg))
    else:
        strOthers = ""
        for other in others:
            strOthers = strOthers + str(other)
        print(datetime.datetime.now(), str(msg) + strOthers)

# Logs without adding a newline. Used for progress messages.
def logProgress(msg):
    global crlfMissing
    crlfMissing = True
    fillSize = os.get_terminal_size().columns - 28 - len(str(msg))
    filler = ' ' * fillSize
    print(datetime.datetime.now(), str(msg), end=filler + '\r')
        
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
    return '/' + str(random.randint(0,99999999)).zfill(8) + extension

# Matches a string against several patterns, returns True if it contains any of them
def anyMatches(string, patterns):
    for pattern in patterns:
        if pattern in string:
            return True
    return False    

# Derives a label text from a file path
def getLabelText(file):
    sourcePaths = []
    for source in sources:
        sourcePaths.append(sources[source]['path'])
    dirname = os.path.dirname(file)
    for path in sourcePaths:
        dirname = (
            dirname.replace(path, '')
            .replace('//', ' - ')
            .replace('/', ' - ')
            .replace('\\', ' - '))
    return dirname[3:]

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

# Returns a target config value if it's set, and 'False' otherwise.
# Used for optional boolean flags.
def optionalConfigSet(name):
    if (name in target.keys()):
        return target[name]
    else:
        return False

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
    if ruleParts:
        rule['count'] = ruleParts.group(1)
        rule['pattern'] = ruleParts.group(2).encode('cp1252').decode('utf8') # Fix encoding
    else:
        # No count on the rule - just fix the encoding on the string
        rule['pattern'] = ruleString.encode('cp1252').decode('utf8')
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
    availableFiles = []
    for filePath in availableFilesIterator:
        availableFiles.append(filePath.replace('\\', '/'))
    return availableFiles

# Apply exclusion rules to available files.
# Return the number of excluded files.
def applyExcludes(fileList, exclusionPatterns):
    exclusionRules = []
    for exclusionPattern in exclusionPatterns:
        exclusionRules.append(parseRule(exclusionPattern)['pattern'])
    excludedFiles = [file for file in fileList if anyMatches(file, exclusionRules)]
    for exclusion in excludedFiles:
        fileList.remove(exclusion)
    return len(excludedFiles)

# Apply limit rules to eligibleFiles and returns the list with them filtered out
def applyLimits(fileList, limitRules):
    for ruleString in limitRules:
        rule = parseRule(ruleString)
        limitedPicks = pickByRule(fileList, rule)
        # Remove all files with the rule pattern
        applyExcludes(fileList, [ruleString])
        # Re-add just the limited subset
        fileList += limitedPicks
        log('Limiting to a maximum of ', len(limitedPicks), ' files matching pattern "', rule['pattern'], '"')

# Get the source image with the size according to any aspect ratio/sizing constraints
# and with label text applied, if the user wants any.
# Returns an image, or "None" if the `twoPortraits` flag is selected and an image was instead stacked inside (see code).
def getPreparedImage(sourceFile):
    maxWidth = int(target['maxWidth'])
    maxHeight = int(target['maxHeight'])
    global portraitBuffer
    image = ImageOps.exif_transpose(Image.open(sourceFile))

    # Get current image size and orientation
    currWidth, currHeight = image.size
    portrait = (currWidth < currHeight)
    landscape = not portrait

    if landscape & optionalConfigSet('cropToFill'):
        image = cropToFill(image.copy(), maxWidth, maxHeight)
    else:
        resizedImg = image.copy()
        resizedImg.thumbnail((maxWidth, maxHeight)) # Preserves aspect ratio
        image = resizedImg # Defaults to "naive" resizing (assumes same aspect ratio of the picture frame)



    # The 'two portraits' functionality works like this:
    # First, a portrait image and its label is stored in the portraitBuffer, and
    # then, when a second one comes by, it's merged with the one previously
    # stored.
    if portrait & optionalConfigSet('twoPortraits'):
        if portraitBuffer == None:
            portraitBuffer = (image, getLabelText(sourceFile))
            return None
        else:
            (secondImage, secondLabel) = portraitBuffer
            image = twoPortraits(image.copy(), secondImage, getLabelText(sourceFile), secondLabel)
            portraitBuffer = None
    else:
        if optionalConfigSet('applyLabel'):
            newWidth, newHeight = image.size
            drawText(image, getLabelText(sourceFile), 3, newHeight - 30)
    
    return image

# Draw text over an image
def drawText(image, text, x, y):
    labelFont = ImageFont.truetype("fonts/roboto-mono.ttf", 16)
    draw = ImageDraw.Draw(image)
    # Draw a 1px black shading around the text location
    draw.text((x+1, y), text,(0,0,0),font=labelFont)
    draw.text((x-1, y), text,(0,0,0),font=labelFont)
    draw.text((x, y+1), text,(0,0,0),font=labelFont)
    draw.text((x, y-1), text,(0,0,0),font=labelFont)
    draw.text((x+1, y+1), text,(0,0,0),font=labelFont)
    draw.text((x-1, y-1), text,(0,0,0),font=labelFont)
    draw.text((x+1, y-1), text,(0,0,0),font=labelFont)
    draw.text((x-1, y+1), text,(0,0,0),font=labelFont)
    # Draw the actual text
    draw.text((x, y), text,(255,255,255),font=labelFont)

# Crop an image, preserving the aspect ratio.
# Returns a crop of the image that fills maxWidth and maxHeight
def cropToFill(image, maxWidth, maxHeight):
    resizedImg = image.copy()
    resizedImg.thumbnail((maxWidth, maxHeight)) # Resizes preserving aspect ratio
    (top, left, boxWidth, boxHeight) = resizedImg.getbbox()
    if boxWidth < maxWidth:
        # Black bars on the sides, clip vertically
        proportionalHeight = int(maxHeight * (maxWidth / boxWidth))
        heightGap = int((proportionalHeight - maxHeight) / 2)
        if heightGap % 2 == 1:
            heightGap -= 1
        newImage = image.resize((maxWidth, proportionalHeight))
        return newImage.crop((0, heightGap, maxWidth, maxHeight + heightGap))
    elif boxHeight < maxHeight: 
        # Black bars on the top/bottom, clip horizontally
        proportionalWidth = int(maxWidth * (maxHeight / boxHeight))
        widthGap = int((proportionalWidth - maxWidth) / 2)
        if widthGap % 2 == 1:
            widthGap -= 1
        newImage = image.resize((proportionalWidth, maxHeight))
        return newImage.crop((widthGap, 0, maxWidth + widthGap, maxHeight))

# Merge two portrait images into a single image, side by side
def twoPortraits(image1, image2, label1, label2):
    dividerWidth = 10
    maxWidth = int(target['maxWidth'])
    maxHeight = int(target['maxHeight'])

    img1crop = cropToFill(image1, int((maxWidth/2) - (dividerWidth/2)), maxHeight)
    img2crop = cropToFill(image2, int((maxWidth/2) - (dividerWidth/2)), maxHeight)

    if optionalConfigSet('applyLabel'):
        drawText(img1crop, label1, 3, maxHeight - 30)
        drawText(img2crop, label2, 3, maxHeight - 30)

    twoPortraits = Image.new('RGB', (maxWidth, maxHeight))
    twoPortraits.paste(img1crop, (0, 0))
    twoPortraits.paste(img2crop, (int((maxWidth/2) + (dividerWidth/2)), 0))
    return twoPortraits

# Copy all files from the list to the target folder.
# The destination file names are randomized, and
# the files are resized to the desired resolution.
# Returns a tuple with the file count and the total bytes copied.
def resizeAndCopyFiles(fileList):
    bytes = 0
    for sourceFile in fileList:
        try:
            fileName, fileExt = os.path.splitext(sourceFile)
            targetFile = target['path'] + randomFileName(fileExt)

            image = getPreparedImage(sourceFile)

            if image == None: # This can happen if an image was stacked to be merged later, see code
                return (0, 0)
            
            image.save(targetFile)
            bytes += os.stat(targetFile).st_size
            logProgress('Copied ' + sourceFile + ' to ' + targetFile)
        except Exception as ex:
            log('Error copying ', sourceFile,' - ', str(ex))
    return (1, bytes)

# Check if the amount of bytes is under the byte size cap for the target directory.
# Always returns True if there's no cap.
def isUnderByteSizeCap(bytes):
    if 'maxMegabytes' not in target.keys():
        return True
    byteCountCap = target['maxMegabytes'] * (1024*1024)
    return bytes < byteCountCap

# Check if the amount of files is under the file count cap for the target directory.
# Always returns True if there's no cap.
def isUnderFileCountCap(fileCount):
    if 'maxFiles' not in target.keys():
        return True
    return fileCount < target['maxFiles']

################################################################################
################################################################################
################################################################################

if len(sys.argv) < 2:
    abort("Missing config file path. Usage: picpicker <config.yaml>")

parseConfig(sys.argv[1])
byteCount = 0

if optionalConfigSet('wipeTarget'):
    log('Wiping target directory "', target['path'], '" before starting.')
    for file in glob.glob(target['path'] + '/*'):
        os.remove(file)

# Process sources
for sourceName in sources:
    log('Processing source: ', sourceName)
    source = sources[sourceName]

    availableFiles = collectAvailableFiles(source['path'], source['filePattern'])
    log('Potential file count: ', len(availableFiles))

    excludedCount = applyExcludes(availableFiles, source['exclude'])
    log('Excluded ', excludedCount, ' files via exclusion patterns.')

    applyLimits(availableFiles, source['limit'])

    requiredFiles = pickRequired(availableFiles, source['ensure'])
    log('Remaining files available to be picked: ', len(availableFiles))

    (fileCount, byteCount) = resizeAndCopyFiles(requiredFiles)
    log('Included a total of ', fileCount, ' required files (', toMbString(byteCount),').')

if (isUnderByteSizeCap(byteCount) == False) or (isUnderFileCountCap(fileCount) == False):
    log('Warning: required files already exceed the limits set for the target directory.')
else:
    log('Filling the rest of the target folder with random picks.')
    if 'maxMegabytes' in target.keys():
        log('Will copy up to ', target['maxMegabytes'], ' MB.')
    if 'maxFiles' in target.keys():
        log('Will copy up to ', target['maxFiles'], ' files.')        
    while isUnderByteSizeCap(byteCount) and isUnderFileCountCap(fileCount):
        if len(availableFiles) == 0:
            break
        (addedFiles, addedBytes) = resizeAndCopyFiles([randomPickFrom(availableFiles)])
        fileCount += addedFiles
        byteCount += addedBytes
    
log('Finished: copied a total of ', fileCount, ' files (', toMbString(byteCount), ')')