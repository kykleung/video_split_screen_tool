---
name: align-videos
description: >-
  Open f1_search_frame.py so a person can narrow down a sync timestamp.
  Use when finding lights-out, editing mask.png, or changing that script.
---

# Align videos

The user finds the sync time by hand in two GUI windows. Leave `f1_23_search_start_frame.py` and `f1_23_search_matching_frame.py` alone unless the user names them. Do not open the video files in the editor.

## Two windows

When asked to open the footage, background one process per file:

```bash
python f1_search_frame.py jackey.mp4 &
python f1_search_frame.py keith.mp4 &
```

Use the paths the user gave. Stop after the windows are up. The timestamp comes from the user narrowing down inside each window, not from the agent.

## Lap index

**Index laps** reads the top-left counter from keyframes, then decodes only the short span around each change.

Qualifying is a single `LAP` digit. `0` is the out-lap. A step that holds is a flying-lap start. The top-right clock separates the out-lap, the hot laps, and the in-lap.

A race counter reads `LAP current / total`. The formation lap is the banner `FORMATION LAP`. The banner becomes lap 1 on the grid. Lap 1 in the index is the last frame where the five red lights are still lit. Later steps are the start/finish crossings. The same button handles both. The status line names the step in progress: keyframes, lap changes, the red lights, then lap times. Race-counter crops and digit templates live next to the qualifying ones in `f1_search_frame.py`.

## Lights-out scoring

`mask.png` sits at the repo root. The script scores red inside the mask (closeness to pure red blended with red dominance, minus a nearby-pixel penalty) and can walk forward to the last stable frame before the drop. The drop is 70% of the peak and at least 0.07, held for two frames. Change these thresholds only when editing this script, and update this skill in the same change.

While indexing a race, lap 1 is the last frame with the five red lights still lit. The lap clock start is already known, so the score only reads the few seconds just before that.

## Done

Each recording has a search window open, or the user has supplied one sync timestamp per file. Pass those timestamps to the split-screen skill. Do not invent them.
