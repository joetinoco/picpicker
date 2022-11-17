# PicPicker

Got one of those digital picture frames, but don't want to go through all your gigabytes of pictures to make a selection for it? Let PicPicker do it for you automagically.

Features:
- Automatically resize pictures to your picture frame resolution,preserving the original aspect ratio
- Auto-picks as many pictures as your target USB drive/SD card can fit
- Randomize file names (and display order)
- Specify files/directories to ignore
- Specify files/directories to always include
- Limit the amount of files picked from specific directories - if you have baby pictures you know how important this is

## Pre-requisites

- Instal Python 3
- Install required packages via `pip`
- Download the [ffmpeg](https://ffmpeg.org/download.html) executable for your platform and put it in the `ffmpeg` directory

## Configuration file

PicPicker expects a configuration file in yaml format, with at least one source directory to pick pictures and a target to put the result. Refer to [picpicker.yaml] for a documented example of all possible options and create your own.

## Running the script

Simply run it with `python picpicker.py <your_config.yml>`