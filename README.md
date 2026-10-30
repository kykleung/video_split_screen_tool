# Video Split Screen Tool Collection

Scripts that line up two F1 race recordings and combine them into one 1920×1080 side-by-side video.

Agents start at [AGENTS.md](AGENTS.md). Coding practices live in [.cursor/rules/coding-practices.mdc](.cursor/rules/coding-practices.mdc).

# Setup

[pyenv](https://github.com/pyenv/pyenv) is recommended. The interpreter pin is `.python-version`.

Install Python packages with `pip install -r requirements.txt`.

ffmpeg, ffprobe, and yt-dlp need to be on `PATH`.

# Workflow

1. Open one search window per recording and narrow down the shared moment in each:

```bash
python f1_search_frame.py jackey.mp4 &
python f1_search_frame.py keith.mp4 &
```

### Lap starts

In each search window, **Index laps** finds the flying-lap starts. **Prev lap start** and **Next lap start** jump to them. `--index-laps` prints the same times, one per line, and does not open the window:

```bash
python f1_search_frame.py jackey.mp4 --index-laps
```

A lap start is the frame where the top-left `LAP` number goes up by one and holds. `0` is the out-lap (a slashed zero). `0` to `1` is the first flying lap. On the Imola qualifying recording the top-right timer restarts at 452.5 s while the tower stays on `LAP 3`, because the car is returning to the pits. That time is not a lap start. The terminal also prints each finished out lap, hot lap, and in lap, plus how many times the car left the garage.

Indexing reads keyframes of that label, then decodes only the few seconds around each change. A full qualifying file finishes in a few seconds.

2. Encode with the left file at 0 and the right file at `right_sync - left_sync`. Typical flags are `--stereo-pan` and `--auto-balance`.

```bash
python f1_create_split_screen_video.py jackey.mp4 $((0)) keith.mp4 $((205.4052-141.5581)) \
  --stereo-pan --auto-balance \
  --output_path F1_25_2-player_career_season_1_R07_Imola_race_side-by-side.mp4
```

Run that in zsh. `$(( ))` there accepts the decimal subtraction. Each side keeps the centre 75% of the frame, scales to 960×1080, and the pair stacks to 1920×1080.

Optional download: `./yt-dl.bash <YouTube link> [filename]` (yt-dlp formats `299+251`, then `232+234`, then `136+251`).

The other `f1_23_*.py` files are older and not part of this workflow.
