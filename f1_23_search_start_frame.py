import cv2
import numpy as np
import argparse
import tkinter as tk
from tkinter import filedialog

# Set up argument parser
parser = argparse.ArgumentParser(description="Find the best matching frame in a video.")
parser.add_argument("--video_path", type=str, help="Path to the video file.")
parser.add_argument("--limit_seconds", type=int, default=None, help="Limit search to the first n seconds of the video.")
args = parser.parse_args()

# Initialize Tkinter root if needed
if not args.video_path:
    root = tk.Tk()
    root.withdraw()  # Use to hide the tiny Tkinter window

    # Open file dialog to select the video
    args.video_path = filedialog.askopenfilename(title="Select video file", filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")])

    # Ensure a file was selected
    if not args.video_path:
        print("No file selected.")
        exit()

# Load the input image and the mask
input_image = cv2.imread('reference_image.jpg')
mask = cv2.imread('mask.png', 0)  # Load mask in grayscale

# Load the selected video
video = cv2.VideoCapture(args.video_path)
if not video.isOpened():
    print("Error: Couldn't open video.")
    exit()

# Get the first frame to determine its resolution
ret, first_frame = video.read()
if not ret:
    print("Error: Couldn't read the first frame of the video.")
    exit()

# Resize mask and input_image to match the video frame's resolution
frame_height, frame_width = first_frame.shape[:2]
mask = cv2.resize(mask, (frame_width, frame_height))
input_image = cv2.resize(input_image, (frame_width, frame_height))

# Reset video to start
video.set(cv2.CAP_PROP_POS_FRAMES, 0)

# Initialize variables for the best match
best_frame = None
best_frame_time = 0
lowest_score = float('inf')  # Initialize with infinity

# Get the FPS and total number of frames in the video
fps = video.get(cv2.CAP_PROP_FPS)
total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
limit_frames = args.limit_seconds * fps if args.limit_seconds else total_frames

# Processing loop
while video.isOpened():
    ret, frame = video.read()
    current_frame_index = int(video.get(cv2.CAP_PROP_POS_FRAMES)) - 1  # Get current frame index (0-based)
    
    if not ret or current_frame_index >= limit_frames:
        break

    # Apply mask
    masked_input = cv2.bitwise_and(input_image, input_image, mask=mask)
    masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

    # Compute the absolute difference
    diff = cv2.absdiff(masked_input, masked_frame)
    
    # Calculate the Sum of Absolute Differences (SAD)
    score = np.sum(diff)

    # Update best match if the current frame is a better match
    if score < lowest_score:
        lowest_score = score
        best_frame = frame
        best_frame_time = current_frame_index / fps  # Calculate time in seconds

    # Print progress
    completion_percentage = (current_frame_index / limit_frames) * 100
    print(f"\rProcessing video: {completion_percentage:.2f}% - Current Lowest Score: {lowest_score}", end="")

# After processing all frames up to the limit
print("\nProcessing complete.")

# Display the best matching frame, its time, and frame number
if best_frame is not None:
    best_frame_number = int(best_frame_time * fps)  # Calculate the frame number from the time
    print(f"Best frame time: {best_frame_time} seconds (Frame number: {best_frame_number})")
    cv2.imshow('Best Match', best_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print("No best frame found.")
