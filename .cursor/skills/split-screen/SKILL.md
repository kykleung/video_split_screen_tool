---
name: split-screen
description: >-
  Build or change the 1920×1080 ffmpeg side-by-side encode in
  f1_create_split_screen_video.py. Use when combining two videos, adjusting
  crop, loudness, stereo pan, hardware encoding, or the split-screen script.
---

# Split-screen

Encode with `f1_create_split_screen_video.py`. Leave `f1_23_create_split_screen_video.py` unchanged unless the user names that file.

## Command

The user already has one sync timestamp per file from the two search windows. Left start is `$((0))`. Right start is `$((right_sync-left_sync))`. Include `--stereo-pan` and `--auto-balance` unless the user asks for a different mix. Set `--output_path` to a session name ending in `_side-by-side.mp4`. The user runs this in zsh, where `$(( ))` accepts decimals.

```bash
python f1_create_split_screen_video.py jackey.mp4 $((0)) keith.mp4 $((205.4052-141.5581)) \
  --stereo-pan --auto-balance \
  --output_path F1_25_2-player_career_season_1_R07_Imola_race_side-by-side.mp4
```

## Steps

1. Stop when you can name both paths, both sync timestamps, and the output path. Ask for any timestamp the user has not given. Do not invent one.
2. Print the command above with those values, or change only `f1_create_split_screen_video.py` when the request is a code change. Keep both sides on the same picture chain: centre 75% crop, scale to 960 wide, pad to 960×1080, then `hstack` to 1920×1080.
3. `--stereo-pan` hard-pans. `--auto-balance` targets −23 LUFS. Gains may differ. The filter topology may not.
4. Single-pass is the default. Touch the `--three-step` branch only when the user asks for that path, and then keep it in parity with the single-pass filters.

## Done

The user has a command they can run, or a diff that still writes 1920×1080 with stereo pan and auto-balance. Do not encode a full race unless they asked you to run it.
