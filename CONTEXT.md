# Split-screen

Two F1 recordings combined into one side-by-side video, aligned on a moment the driver picks by hand.

## Language

**Sync timestamp**:
The time, in one recording, of the shared moment. One per file. Found by narrowing down in a search window.
_Avoid_: start time, matching frame, lights-out time

**Search window**:
One running copy of `f1_search_frame.py` on one recording.
_Avoid_: player, preview

**Split-screen**:
The 1920×1080 side-by-side output of `f1_create_split_screen_video.py`.
_Avoid_: combined video, composite

**Left** and **right**:
The two inputs. Left starts at 0 seconds. Right starts at `right sync timestamp − left sync timestamp`.
_Avoid_: video 1, video 2, primary, secondary
