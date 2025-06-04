#!/bin/bash

# Check if a YouTube link is provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <YouTube_Link>"
    exit 1
fi

YOUTUBE_LINK="$1"

echo "Checking available formats for: $YOUTUBE_LINK"

# Get available formats and store them in a variable
FORMATS_OUTPUT=$(yt-dlp --list-formats "$YOUTUBE_LINK")

# Check if format ID 312 is available (allowing for leading whitespace)
if echo "$FORMATS_OUTPUT" | grep -q "^\s*312\s"; then
    echo "Format ID 312 found. Downloading video (312) and audio (234)..."
    yt-dlp --no-skip-unavailable-fragments --abort-on-unavailable-fragments -f "312+234" --merge-output-format mp4 "$YOUTUBE_LINK"
# Check if format ID 232 is available (allowing for leading whitespace)
elif echo "$FORMATS_OUTPUT" | grep -q "^\s*232\s"; then
    echo "Format ID 232 found. Downloading video (232) and audio (234)..."
    yt-dlp --no-skip-unavailable-fragments --abort-on-unavailable-fragments -f "232+234" --merge-output-format mp4 "$YOUTUBE_LINK"
else
    echo "No suitable video format (ID 312 or 232) found for $YOUTUBE_LINK."
    echo "Available formats:"
    echo "$FORMATS_OUTPUT"
    exit 1
fi

echo "Script finished."
