# PicPicker

Got one of those digital picture frames, but don't want to go through all your gigabytes of pictures to make a selection for it? Let PicPicker do it for you automagically.

PicPicker generates a randomized selection of your pictures, resized for your picture frame resolution, and ready for copying to a USB drive or SD card. Your originals are left untouched.

Features:
- Resized images preserve the original aspect ratio
- Display more than one image at once by joining portrait images side-by-side
- Limit selection size and/or amount of files to fit your storage limits.
- Images can be optimized for monochrome e-ink displays (like old e-readers)
- Specify files/directories to ignore or always include
- Limit the amount of files picked from specific directories (if you have baby pictures you know how important this is)
- Embed (optional, adjustable) text onto pictures from the file location e.g. files from `/vacation/paris 2022` will be labeled "vacation - paris 2022".

## Pre-requisites

- Instal Python 3
- Install required packages via `pip`. 

On WSL/bash:
```
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

## Configuration file

PicPicker expects a configuration file in yaml format, with at least one source directory to pick pictures and a target to put the result. Refer to [picpicker.yaml](picpicker.yaml) for a documented example of all possible options and create your own.

## Running the script

Simply run it with `python3 picpicker.py <your_config.yml>`

## Limitations, TODOs

- The script assumes you'll always see your pictures in landscape mode and scales them for this use case only