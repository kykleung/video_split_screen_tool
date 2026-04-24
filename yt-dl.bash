#!/bin/bash

# Check for link
if [ -z "$1" ]; then
    echo "Usage: $0 <YouTube_Link> [Custom_Filename]"
    exit 1
fi

YOUTUBE_LINK="$1"
CUSTOM_NAME="$2"

# logic for the -o flag
OUTPUT_ARG=""
if [ -n "$CUSTOM_NAME" ]; then
    # We add .mp4 extension automatically if it's not provided
    OUTPUT_ARG="-o ${CUSTOM_NAME%.*}.mp4 "
fi

echo "Checking available formats for: $YOUTUBE_LINK"
FORMATS_OUTPUT=$(yt-dlp --color never --no-progress --list-formats "$YOUTUBE_LINK")

if echo "$FORMATS_OUTPUT" | grep -q "^\s*299\s"; then
    echo "Format ID 299 found. Downloading video (299) and audio (251)..."
    yt-dlp $OUTPUT_ARG --no-skip-unavailable-fragments --abort-on-unavailable-fragments -f "299+251" --merge-output-format mp4 "$YOUTUBE_LINK"
elif echo "$FORMATS_OUTPUT" | grep -q "^\s*232\s"; then
    echo "Format ID 232 found. Downloading video (232) and audio (234)..."
    yt-dlp $OUTPUT_ARG --no-skip-unavailable-fragments --abort-on-unavailable-fragments -f "232+234" --merge-output-format mp4 "$YOUTUBE_LINK"
elif echo "$FORMATS_OUTPUT" | grep -q "^\s*136\s"; then
    echo "Format ID 136 found. Downloading video (136) and audio (251)..."
    yt-dlp $OUTPUT_ARG --no-skip-unavailable-fragments --abort-on-unavailable-fragments -f "136+251" --merge-output-format mp4 "$YOUTUBE_LINK"

else
    echo "No suitable video format (ID 299 or 232 or 136) found for $YOUTUBE_LINK."
    echo "Available formats:"
    echo "$FORMATS_OUTPUT"
    exit 1
fi

