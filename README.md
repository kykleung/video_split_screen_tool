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
python f1_23_search_frame.py jackey.mp4 &
python f1_23_search_frame.py keith.mp4 &
```

2. Encode with the left file at 0 and the right file at `right_sync - left_sync`. Typical flags are `--stereo-pan` and `--auto-balance`.

```bash
python f1_create_split_screen_video.py jackey.mp4 $((0)) keith.mp4 $((205.4052-141.5581)) \
  --stereo-pan --auto-balance \
  --output_path F1_25_2-player_career_season_1_R07_Imola_race_side-by-side.mp4
```

Run that in zsh. `$(( ))` there accepts the decimal subtraction. Each side keeps the centre 75% of the frame, scales to 960×1080, and the pair stacks to 1920×1080.

Optional download: `./yt-dl.bash <YouTube link> [filename]` (yt-dlp formats `299+251`, then `232+234`, then `136+251`).

The other `f1_23_*.py` files are older and not part of this workflow.
