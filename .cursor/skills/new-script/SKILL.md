---
name: new-script
description: >-
  Scaffold a new CLI script in this repo. Use when the user asks for a new
  script, tool, or command-line utility.
---

# New script

Add one `snake_case` Python file at the repo root. Do not create a package, a test run, or a video output unless the user asks.

## Constraints

- argparse, then a function that does the work, then `if __name__ == "__main__"`.
- `snake_case` functions and arguments. `UPPER_SNAKE` constants. PascalCase only if there is a class.
- Paths and thresholds are parameters. Name numeric literals as constants.
- ffmpeg and ffprobe use an argument list with `check=True` and `text=True`.
- Side-by-side encoding belongs in `f1_create_split_screen_video.py`, not a new file. Use this skill for a different tool.
- tkinter only if a person must click.
- Replace `{script}` and `{summary}` below. Do not add sections the template does not have.

## File

```python
"""{summary}"""

import argparse

OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080


def run(video_path, start_time):
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="{summary}")
    parser.add_argument("video_path", help="Path to the video file.")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds.")
    args = parser.parse_args()
    run(args.video_path, args.start)


if __name__ == "__main__":
    main()
```

Drop `OUTPUT_WIDTH` and `OUTPUT_HEIGHT` when the script does not touch the picture contract. Mention the script in `AGENTS.md` under "Which script" in the same change.

## Done

The new file matches the template, `AGENTS.md` names it, and the script is not executed on a race video unless the user asked for a run.
