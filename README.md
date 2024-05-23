# Video Split Screen Tool Collection

# Setup

The use of [pyenv](https://github.com/pyenv/pyenv) is recommended. The scripts in this repo have been run with Python 3.12.2

## Requirements
Run `pip install -r requirements.txt`

# One-Time Tools

## f1\_23\_find\_mask\_frame.py
Use  this to load a video and step through each frame to select and save a frame to be used for mask creation. This frame can also be used as the reference image for finding a similar frame from a video. This image file (`reference_image.jpg`) is also already included in the repo. 

## f1\_23\_create\_mask\_image.py
Load an image (i.e., output of `f1\_23\_find\_mask\_frame.py`)
Click on the image to add a similar-coloured blob to the mask. Hit q to finish and save the mask image. A mask image (`mask.png`) is included in this repo.

# Worfklow

## f1\_23\_search\_start\_frame.py 
Loads a video file and finds the frame most similar to the masked portion of the `reference_image.jpg` image. Run with `-h` option for further details. The output is the time (and frame number) of the most similar frame. This frame will also be displayed. Run this script of the two videos that will be combined together as a split-screen video. Useful for aligning race starts where cars start in different positions

## f1\_23\_search\_matching\_frame.py
Loads two videos and finds the earliest mutually matching frames. Optionally set duration and the starting time of both videos.

###Usage
`f1_23_search_matching_frame.py [-h] [--duration DURATION] [--video1_start VIDEO1_START] [--video2_start VIDEO2_START] video1_path video2_path`

## f1\_23\_create\_split\_screen\_video.py
Process and combine two videos side by side to achieve a standard 1080p resolution output video.

###Usage
`f1_23_create_split_screen_video.py [-h] [--output_path OUTPUT_PATH] left_video_path left_start_time right_video_path right_start_time`

# Misc
## YouTube video download
`youtube-dl` is a convenient command line tool to use for pulling YouTube videos given a link. 