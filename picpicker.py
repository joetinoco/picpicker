import datetime, sys, glob, re, os.path, yaml, re, random, traceback
from PIL import Image, ImageOps, ImageFont, ImageDraw, ImageEnhance

###########################
## Globals
sources = []
target = {}
crlfMissing = False # Used as a flag for logging
portraitBuffer = None # Used by the `twoPortraits` flag
labelFontSize = 16 # Default, can be overriden from the yaml config
byteCount = 0
fileCount = 0

###########################
## Functions

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
    try:
        fillSize = os.get_terminal_size().columns - 28 - len(str(msg))
    except OSError:
        # Print normally and return.
        # This happens when you're debugging on VScode's debug console, which it's not a terminal so .get_terminal_size() fails
        crlfMissing = False
        print(datetime.datetime.now(), str(msg))
        return
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
    return '/' + str(random.randint(0,99999999)).zfill(8) + extension.lower()

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
        normalizedPath = path.replace('\\', '/')
        if normalizedPath[-1] != '/':
            normalizedPath += '/'
        dirname = (
            dirname.replace(normalizedPath, '')
            .replace('//', ' - ')
            .replace('/', ' - ')
            .replace('\\', ' - '))
    return dirname

# Parse and validate configuration
def parseConfig(configFilePath):
    global sources
    global target
    with open(configFilePath, "r", encoding="utf-8-sig") as configfile:
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
        rule['pattern'] = ruleParts.group(2)
    else:
        # No count on the rule
        rule['pattern'] = ruleString
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
        pickedFiles += pickByRule(eligibleFiles, rule)
        log('Ensuring at least ', rule['count'], ' files that match pattern "', rule['pattern'], '" - ', len(pickedFiles), ' files selected.')
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
# and with other user options applied (labels, e-ink optimization, etc).
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

    if optionalConfigSet('eInkOptimize'):
        grayscaleImg = ImageOps.grayscale(image)
        contrastImg = ImageEnhance.Contrast(grayscaleImg).enhance(1.5)
        image = ImageEnhance.Brightness(contrastImg).enhance(1.2)

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
            _, newHeight = image.size
            drawText(image, getLabelText(sourceFile), 3, newHeight - 14 - labelFontSize)
    
    return image

# Draw text over an image
def drawText(image, text, x, y):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(script_dir, "fonts/roboto-mono.ttf")
    labelFont = ImageFont.truetype(font_path, labelFontSize)
    draw = ImageDraw.Draw(image)

    (colorBlack, colorWhite) = ((0,0,0), (255,255,255))
    if optionalConfigSet('eInkOptimize'):
        (colorBlack, colorWhite) = (0, 255)
    
    # Draw a 1px black shading around the text location
    draw.text((x+1, y), text,colorBlack,font=labelFont)
    draw.text((x-1, y), text,colorBlack,font=labelFont)
    draw.text((x, y+1), text,colorBlack,font=labelFont)
    draw.text((x, y-1), text,colorBlack,font=labelFont)
    draw.text((x+1, y+1), text,colorBlack,font=labelFont)
    draw.text((x-1, y-1), text,colorBlack,font=labelFont)
    draw.text((x+1, y-1), text,colorBlack,font=labelFont)
    draw.text((x-1, y+1), text,colorBlack,font=labelFont)
    # Draw the actual text
    draw.text((x, y), text,colorWhite,font=labelFont)

# Crop an image, preserving the aspect ratio.
# Returns a crop of the image that fills maxWidth and maxHeight
def cropToFill(image, maxWidth, maxHeight):
    resizedImg = image.copy()
    resizedImg.thumbnail((maxWidth, maxHeight)) # Resizes preserving aspect ratio
    (_, _, boxWidth, boxHeight) = resizedImg.getbbox()
    
    if (boxWidth < maxWidth) and (boxHeight < maxHeight):
        # Image is smaller than the box size, so expand it
        # without messing up the aspect ratio
        if boxWidth > boxHeight:
            aspectRatio = boxWidth/boxHeight
            landscape = True
        elif boxHeight > boxWidth:
            aspectRatio = boxHeight/boxWidth
            landscape = False
        else:
            aspectRatio = 1 # Square image 
            landscape = True # not really but yeah

        (largerWidth, largerHeight) = (maxWidth, maxHeight)
        if landscape:
            largerHeight = int(largerWidth / aspectRatio)
        else:
            largerWidth = int(largerHeight / aspectRatio)
        newImage = image.resize((largerWidth, largerHeight))
        resizedImg = newImage
        (_, _, boxWidth, boxHeight) = resizedImg.getbbox()


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
    else:
        return resizedImg

# Merge two portrait images into a single image, side by side
def twoPortraits(image1, image2, label1, label2):
    dividerWidth = 10
    maxWidth = int(target['maxWidth'])
    maxHeight = int(target['maxHeight'])

    img1crop = cropToFill(image1, int((maxWidth/2) - (dividerWidth/2)), maxHeight)
    img2crop = cropToFill(image2, int((maxWidth/2) - (dividerWidth/2)), maxHeight)

    if optionalConfigSet('applyLabel'):
        drawText(img1crop, label1, 3, maxHeight - 14 - labelFontSize)
        drawText(img2crop, label2, 3, maxHeight - 14 - labelFontSize)

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
    files = 0
    for sourceFile in fileList:
        try:
            _, fileExt = os.path.splitext(sourceFile)
            targetFile = target['path'] + randomFileName(fileExt)
            sourceFile = f"""{sourceFile}""" # Wrap in quotes in case the path has spaces
            try:
                image = getPreparedImage(sourceFile)
            except Exception:
                log('Error preparing image ', sourceFile)
                print(traceback.format_exc())
                continue

            if image == None: # This can happen if an image was stacked to be merged later, see code
                continue

            if optionalConfigSet('printFileName'):
                drawText(image, targetFile.replace(target['path'], '')[1:], 3, 3)
            
            targetFile = f"""{targetFile}""" # Wrap in quotes in case the path has spaces
            image.save(targetFile)
            bytes += os.stat(targetFile).st_size
            files += 1
            logProgress('Copied ' + sourceFile + ' to ' + targetFile)
        except Exception as ex:
            log('Error copying ', sourceFile,' - ', str(ex))
            traceback.print_exc()
            exit(1)
    return (files, bytes)

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

if optionalConfigSet('labelFontSize'):
    labelFontSize = int(target['labelFontSize'])

if optionalConfigSet('wipeTarget'):
    log('Wiping target directory "', target['path'], '" before starting.')
    for file in glob.glob(target['path'] + '/*'):
        os.remove(file)

# Process sources
for sourceName in sources:
    byteCount = 0
    fileCount = 0
    log('Processing source: ', sourceName)
    source = sources[sourceName]

    availableFiles = collectAvailableFiles(source['path'], source['filePattern'])
    log('Potential file count: ', len(availableFiles))

    excludedCount = applyExcludes(availableFiles, source['exclude'])
    log('Excluded ', excludedCount, ' files via exclusion patterns.')

    applyLimits(availableFiles, source['limit'])

    requiredFiles = pickRequired(availableFiles, source['ensure'])
    log('Remaining files available to be picked: ', len(availableFiles))

    while len(requiredFiles) > 0:
        (addedFiles, addedBytes) = resizeAndCopyFiles([randomPickFrom(requiredFiles)])
        fileCount += addedFiles
        byteCount += addedBytes
        if (isUnderByteSizeCap(byteCount) == False) or (isUnderFileCountCap(fileCount) == False):
            log('Warning: required files already exceed the limits set for the target directory.')
            break

    log('Included a total of ', fileCount, ' required files (', toMbString(byteCount),').')

    if (isUnderByteSizeCap(byteCount) == True) and (isUnderFileCountCap(fileCount) == True):
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