# Video split-screen tool

Scripts that turn two F1 race recordings into one 1920×1080 side-by-side video.

Coding practices: `.cursor/rules/coding-practices.mdc` (attached when editing Python or shell).

## Scripts in use

Day-to-day work stays in these two files:

- `f1_23_search_frame.py` is the GUI used to narrow down a sync timestamp. The user opens two copies, one per recording.
- `f1_create_split_screen_video.py` encodes the side-by-side video. The user runs it by hand after those timestamps are known.

Other Python files in the repo (`f1_23_search_start_frame.py`, `f1_23_search_matching_frame.py`, `f1_23_create_image_mask.py`, `f1_23_create_split_screen_video.py`) are older. Leave them alone unless the user names one. `yt-dl.bash` downloads a source with yt-dlp (`299+251`, then `232+234`, then `136+251`).

## Workflow

The user finds the sync time. Do not launch the GUIs or invent timestamps.

1. Two search windows, backgrounded, one for each recording:

```bash
python f1_23_search_frame.py jackey.mp4 &
python f1_23_search_frame.py keith.mp4 &
```

2. In each window, narrow down the shared moment (lights out). That yields one timestamp per file.
3. Encode with the left file starting at 0 and the right file starting at `right_sync - left_sync`, so the two moments land on the same output frame. Usual flags are `--stereo-pan` and `--auto-balance`. Name `--output_path` for the session.

```bash
python f1_create_split_screen_video.py jackey.mp4 $((0)) keith.mp4 $((205.4052-141.5581)) \
  --stereo-pan --auto-balance \
  --output_path F1_25_2-player_career_season_1_R07_Imola_race_side-by-side.mp4
```

The right start is the right sync timestamp minus the left one. The user runs this in zsh, where `$(( ))` accepts decimals.

## Picture and sound

Each side keeps the centre 75% of its width, scales to 960 px wide, and pads to 960×1080. The pair stacks to 1920×1080. A session encode hard-pans each car to one ear and loudness-matches both streams to −23 LUFS. Single-pass is the default. `--three-step` encodes each side, then stacks.

## Agent skills

### Issue tracker

GitHub issues in this repo (`gh`). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Engineering skills

Matt Pocock's skills, copied from the One Trimble RT SLAM workspace. Invoke with a slash command: `/wait-what`, `/grill-me`, `/grill-with-docs`, `/grilling`, `/to-questionnaire`, `/to-spec`, `/to-tickets`, `/handoff`, `/wayfinder`, `/research`, `/domain-modeling`, `/writing-for-agents`, `/teach`. `/setup-matt-pocock-skills` reconfigures the tracker and domain layout. Do not install code-loop skills (`tdd`, `implement`, `code-review`).

Repo skills for this codebase: `/split-screen`, `/align-videos`, `/new-script`.

## Files the agent should leave alone

Race videos are local inputs. Do not read them into context and do not commit them. `reference_image.jpg` and `mask.png` are source assets. The interpreter pin is `.python-version`. Runtime packages are `requirements.txt`. System tools are ffmpeg, ffprobe, and yt-dlp.
