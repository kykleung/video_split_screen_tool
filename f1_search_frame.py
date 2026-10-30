import argparse
import concurrent.futures
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, Label, filedialog
import cv2
from PIL import Image, ImageTk
import os
import numpy as np

REFERENCE_FRAME_WIDTH = 1920
REFERENCE_FRAME_HEIGHT = 1080
LAP_CROP_X = 164
LAP_CROP_Y = 128
LAP_CROP_WIDTH = 80
LAP_CROP_HEIGHT = 28
LAP_LETTER_X = 1
LAP_LETTER_Y = 0
LAP_LETTER_WIDTH = 52
LAP_LETTER_HEIGHT = 28
LAP_DIGIT_X = 52
LAP_DIGIT_Y = 0
LAP_DIGIT_WIDTH = 24
LAP_DIGIT_HEIGHT = 28
LAP_INK_GRAY_THRESHOLD = 150
LAP_LETTER_INK_MIN = 80
LAP_LETTER_INK_MAX = 160
LAP_DARK_GRAY_THRESHOLD = 45
LAP_DARK_FRACTION_MIN = 0.70
LAP_DIGIT_TEMPLATE_WIDTH = 8
LAP_DIGIT_TEMPLATE_HEIGHT = 12
LAP_DIGIT_BIT_THRESHOLD = 0.3
LAP_DIGIT_MATCH_MAX_DISTANCE = 4
LAP_DIGIT_HOLD_FRAMES = 5
LAP_DIGIT_MAX_GAP_SECONDS = 12.0
LAP_REFINE_WORKERS = 4
LAP_PTS_ORIGIN_TOLERANCE_SECONDS = 0.1
INDEX_PROGRESS_STRIDE = 50
LAP_INDEX_POLL_MS = 100
WINDOW_CONTROL_HEIGHT = 140
TIMER_CROP_X = 1740
TIMER_CROP_Y = 80
TIMER_CROP_WIDTH = 120
TIMER_CROP_HEIGHT = 18
TIMER_INK_THRESHOLD = 170
TIMER_GLYPH_INK_MIN = 100
TIMER_GLYPH_INK_MAX = 400
TIMER_GLYPH_HEIGHT_MIN = 10
TIMER_GLYPH_HEIGHT_MAX = 14
TIMER_DASH_INK_MIN = 20
TIMER_DASH_INK_MAX = 80
TIMER_DASH_HEIGHT_MAX = 8
TIMER_LONG_LEFT_MAX = 16
TIMER_SHORT_LEFT_MIN = 40
TIMER_REVEAL_SECONDS = 20.0

LAP_DIGIT_TEMPLATE_ROWS = {
    0: (
        "........",
        "........",
        "..####..",
        ".######.",
        ".##..##.",
        ".######.",
        ".###.##.",
        ".##..##.",
        ".######.",
        "..####..",
        "........",
        "........",
    ),
    1: (
        "........",
        "........",
        "..##....",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "..####..",
        "........",
        "........",
    ),
    2: (
        "........",
        "........",
        "..####..",
        "..#####.",
        "....###.",
        "...###..",
        "..###...",
        ".###....",
        ".#####..",
        "..####..",
        "........",
        "........",
    ),
    3: (
        "........",
        "........",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..###...",
        "........",
        "........",
    ),
}

SHOWINFO_PTS_PATTERN = re.compile(r"pts_time:(-?[0-9]*\.?[0-9]+)")


def next_lap_start(starts, current_seconds, half_frame):
    threshold = current_seconds + half_frame
    for start in starts:
        if start > threshold:
            return start
    return None


def previous_lap_start(starts, current_seconds, half_frame):
    threshold = current_seconds - half_frame
    chosen = None
    for start in starts:
        if start >= threshold:
            break
        chosen = start
    return chosen


def scale_reference_px(value, frame_size, reference_size):
    return int(round(value * frame_size / reference_size))


def even_length(value):
    if value % 2:
        return max(value - 1, 0)
    return value


def lap_crop_for_frame(frame_width, frame_height):
    x = scale_reference_px(LAP_CROP_X, frame_width, REFERENCE_FRAME_WIDTH)
    y = scale_reference_px(LAP_CROP_Y, frame_height, REFERENCE_FRAME_HEIGHT)
    width = even_length(scale_reference_px(LAP_CROP_WIDTH, frame_width, REFERENCE_FRAME_WIDTH))
    height = even_length(scale_reference_px(LAP_CROP_HEIGHT, frame_height, REFERENCE_FRAME_HEIGHT))
    return width, height, x, y


def scale_reference_box(x, y, width, height, frame_width, frame_height):
    return (
        scale_reference_px(x, frame_width, REFERENCE_FRAME_WIDTH),
        scale_reference_px(y, frame_height, REFERENCE_FRAME_HEIGHT),
        scale_reference_px(width, frame_width, REFERENCE_FRAME_WIDTH),
        scale_reference_px(height, frame_height, REFERENCE_FRAME_HEIGHT),
    )


def probe_video_geometry(video_path):
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1",
        video_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    fields = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key] = value
    try:
        return int(fields["width"]), int(fields["height"]), float(fields["duration"])
    except (KeyError, ValueError):
        raise ValueError(f"ffprobe returned no frame size for {video_path}") from None


def count_keyframes(video_path):
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=flags",
        "-of", "csv=p=0",
        video_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return sum(1 for line in result.stdout.splitlines() if "K" in line)


def showinfo_pts_times(stderr_text):
    times = []
    for line in stderr_text.splitlines():
        if "showinfo" not in line or "pts_time:" not in line:
            continue
        match = SHOWINFO_PTS_PATTERN.search(line)
        if match is not None:
            times.append(float(match.group(1)))
    return times


def read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def index_progress_message(frame_number, keyframe_count):
    if keyframe_count:
        return f"Indexing laps… {frame_number}/{keyframe_count}"
    return f"Indexing laps… {frame_number}"


def digit_rows_to_mask(rows):
    height = LAP_DIGIT_TEMPLATE_HEIGHT
    width = LAP_DIGIT_TEMPLATE_WIDTH
    if len(rows) != height:
        raise ValueError(f"lap digit template has {len(rows)} rows")
    mask = np.empty((height, width), dtype=bool)
    for row_index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"lap digit template row has {len(row)} columns")
        mask[row_index] = [cell == "#" for cell in row]
    return mask


LAP_DIGIT_TEMPLATES = {
    digit: digit_rows_to_mask(rows) for digit, rows in LAP_DIGIT_TEMPLATE_ROWS.items()
}


def lap_digit_template(digit):
    return LAP_DIGIT_TEMPLATES[digit]


def lap_digit_distance(left, right):
    return int(np.count_nonzero(left != right))


def match_lap_digit(mask):
    best_digit = None
    best_distance = LAP_DIGIT_MATCH_MAX_DISTANCE + 1
    for digit, template in LAP_DIGIT_TEMPLATES.items():
        distance = lap_digit_distance(mask, template)
        if distance < best_distance:
            best_distance = distance
            best_digit = digit
    if best_distance <= LAP_DIGIT_MATCH_MAX_DISTANCE:
        return best_digit
    return None


def is_lap_letter_present(ink_count, dark_fraction):
    has_letter_ink = LAP_LETTER_INK_MIN <= ink_count <= LAP_LETTER_INK_MAX
    has_dark_background = dark_fraction >= LAP_DARK_FRACTION_MIN
    return has_letter_ink and has_dark_background


def gray_region(gray, box):
    x, y, width, height = box
    if width <= 0 or height <= 0 or x < 0 or y < 0:
        return None
    region = gray[y:y + height, x:x + width]
    if region.shape[0] != height or region.shape[1] != width:
        return None
    return region


def lap_digit_mask_from_gray(gray):
    ink = (gray > LAP_INK_GRAY_THRESHOLD).astype(np.float32)
    resized = cv2.resize(
        ink,
        (LAP_DIGIT_TEMPLATE_WIDTH, LAP_DIGIT_TEMPLATE_HEIGHT),
        interpolation=cv2.INTER_AREA,
    )
    return resized > LAP_DIGIT_BIT_THRESHOLD


def classify_lap_image(bgr, letter_box, digit_box):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    letter = gray_region(gray, letter_box)
    if letter is None:
        return None
    ink_count = int(np.count_nonzero(letter > LAP_INK_GRAY_THRESHOLD))
    dark_fraction = float(np.count_nonzero(letter < LAP_DARK_GRAY_THRESHOLD)) / letter.size
    if not is_lap_letter_present(ink_count, dark_fraction):
        return None
    digit = gray_region(gray, digit_box)
    if digit is None:
        return None
    return match_lap_digit(lap_digit_mask_from_gray(digit))


def classify_raw_frames(raw_frames, crop, letter_box, digit_box):
    crop_width, crop_height, _, _ = crop
    digits = []
    for index, data in enumerate(raw_frames):
        image = np.frombuffer(data, dtype=np.uint8).reshape((crop_height, crop_width, 3))
        digits.append(classify_lap_image(image, letter_box, digit_box))
        raw_frames[index] = None
    return digits


def lap_digit_samples(raw_frames, pts_times, crop, letter_box, digit_box):
    digits = classify_raw_frames(raw_frames, crop, letter_box, digit_box)
    return list(zip(pts_times, digits, strict=True))


def lap_brackets_from_digits(samples):
    """Return (previous_time, new_time, new_digit) for each plus-one step.

    Each sample is (time_seconds, digit). `digit` is 0, 1, 2, 3, or None.
    """
    brackets = []
    remembered_digit = None
    remembered_time = None
    for time_seconds, digit in samples:
        if digit is None:
            is_gap_too_long = (
                remembered_time is not None
                and time_seconds - remembered_time > LAP_DIGIT_MAX_GAP_SECONDS
            )
            if is_gap_too_long:
                remembered_digit = None
                remembered_time = None
            continue
        is_next_digit = (
            remembered_digit is not None
            and digit == remembered_digit + 1
            and time_seconds - remembered_time <= LAP_DIGIT_MAX_GAP_SECONDS
        )
        if is_next_digit:
            brackets.append((remembered_time, time_seconds, digit))
        remembered_digit = digit
        remembered_time = time_seconds
    return brackets


def held_lap_start_time(frames, new_digit):
    """Return the first time in a run of the new digit, or None.

    `frames` is a sequence of (time_seconds, digit).
    """
    run_length = 0
    run_start = None
    for time_seconds, digit in frames:
        if digit != new_digit:
            run_length = 0
            continue
        if run_length == 0:
            run_start = time_seconds
        run_length += 1
        if run_length >= LAP_DIGIT_HOLD_FRAMES:
            return run_start
    return None


def first_held_time(frames, predicate, hold_frames):
    run_length = 0
    run_start = None
    for time_seconds, value in frames:
        if not predicate(value):
            run_length = 0
            continue
        if run_length == 0:
            run_start = time_seconds
        run_length += 1
        if run_length >= hold_frames:
            return run_start
    return None


def reference_measure(measured, actual_size, reference_size):
    if actual_size <= 0:
        return 0
    return measured * reference_size / actual_size


def timer_glyph_state(gray):
    """Classify the top-right lap clock as absent, dashes, long, short, mid, or other."""
    if gray.size == 0 or gray.shape[0] == 0 or gray.shape[1] == 0:
        return "absent"
    ink = gray > TIMER_INK_THRESHOLD
    count = reference_measure(
        int(np.count_nonzero(ink)), gray.size, TIMER_CROP_WIDTH * TIMER_CROP_HEIGHT,
    )
    if count < TIMER_DASH_INK_MIN:
        return "absent"
    vertical = np.zeros_like(ink)
    vertical[1:-1] = ink[:-2] & ink[2:]
    vertical_count = int(np.count_nonzero(vertical))
    rows, columns = np.where(ink)
    left = reference_measure(int(columns.min()), gray.shape[1], TIMER_CROP_WIDTH)
    height = reference_measure(int(rows.max() - rows.min() + 1), gray.shape[0], TIMER_CROP_HEIGHT)
    is_dash = (
        vertical_count == 0
        and height <= TIMER_DASH_HEIGHT_MAX
        and count <= TIMER_DASH_INK_MAX
    )
    if is_dash:
        return "dashes"
    is_glyph = (
        TIMER_GLYPH_INK_MIN <= count <= TIMER_GLYPH_INK_MAX
        and TIMER_GLYPH_HEIGHT_MIN <= height <= TIMER_GLYPH_HEIGHT_MAX
    )
    if not is_glyph:
        return "other"
    if left <= TIMER_LONG_LEFT_MAX:
        return "long"
    if left >= TIMER_SHORT_LEFT_MIN:
        return "short"
    return "mid"


def timer_crop_for_frame(frame_width, frame_height):
    x = scale_reference_px(TIMER_CROP_X, frame_width, REFERENCE_FRAME_WIDTH)
    y = scale_reference_px(TIMER_CROP_Y, frame_height, REFERENCE_FRAME_HEIGHT)
    width = even_length(scale_reference_px(TIMER_CROP_WIDTH, frame_width, REFERENCE_FRAME_WIDTH))
    height = even_length(scale_reference_px(TIMER_CROP_HEIGHT, frame_height, REFERENCE_FRAME_HEIGHT))
    return width, height, x, y


def garage_exit_brackets(samples):
    """Return (previous_time, appearance_time) for each out-lap garage exit.

    `samples` are (time_seconds, digit, timer_state). The tower has to return
    with the dashed out-lap clock after the digit has been gone for longer than
    LAP_DIGIT_MAX_GAP_SECONDS.
    """
    brackets = []
    last_digit_time = None
    previous_time = None
    is_armed = True
    for time_seconds, digit, timer_state in samples:
        if digit is None:
            is_long_gap = (
                last_digit_time is not None
                and time_seconds - last_digit_time > LAP_DIGIT_MAX_GAP_SECONDS
            )
            if is_long_gap:
                is_armed = True
                last_digit_time = None
            previous_time = time_seconds
            continue
        if is_armed and previous_time is not None and timer_state == "dashes":
            brackets.append((previous_time, time_seconds))
        is_armed = False
        last_digit_time = time_seconds
        previous_time = time_seconds
    return brackets


def is_flying_timer_reveal(short_time, flying_brackets):
    for _previous_time, new_time, _new_digit in flying_brackets:
        earliest = new_time - TIMER_REVEAL_SECONDS
        latest = new_time + TIMER_REVEAL_SECONDS
        if earliest < short_time <= latest:
            return True
    return False


def in_lap_brackets(timer_samples, flying_brackets):
    """Return spans where the lap clock restarts and the lap digit does not step.

    After a flying lap starts, the clock keeps the finished time for a few
    seconds and then shows the live lap. That hand-off is not an in-lap.
    """
    brackets = []
    previous = None
    for time_seconds, state in timer_samples:
        if previous is not None and previous[1] == "long" and state == "short":
            if not is_flying_timer_reveal(time_seconds, flying_brackets):
                brackets.append((previous[0], time_seconds))
        previous = (time_seconds, state)
    return brackets


def format_clock_milliseconds(total_milliseconds):
    if total_milliseconds <= 0:
        raise ValueError(f"hot lap duration must be positive, got {total_milliseconds} ms")
    minutes, remainder = divmod(total_milliseconds, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    if minutes:
        return f"{minutes}:{seconds:02d}.{milliseconds:03d}"
    return f"{seconds}.{milliseconds:03d}"


def format_hot_lap_time(duration_seconds):
    return format_clock_milliseconds(int(round(duration_seconds * 1000)))


def _next_event_time(events, index, kinds):
    for later_time, later_kind in events[index + 1:]:
        if later_kind in kinds:
            return later_time
        if later_kind == "out":
            return None
    return None


def classify_finished_laps(flying_starts, garage_exits, in_lap_starts):
    """Return (label, start_seconds) for finished out laps, hot laps, and in laps."""
    kind_order = {"out": 0, "hot": 1, "in": 2}
    events = [(start, "out") for start in garage_exits]
    events.extend((start, "hot") for start in flying_starts)
    events.extend((start, "in") for start in in_lap_starts)
    events.sort(key=lambda item: (item[0], kind_order[item[1]]))
    lines = []
    for index, (time_seconds, kind) in enumerate(events):
        if kind == "out":
            if _next_event_time(events, index, {"hot"}) is None:
                continue
            lines.append(("out lap", time_seconds))
            continue
        if kind == "in":
            lines.append(("in lap", time_seconds))
            continue
        end = _next_event_time(events, index, {"hot", "in"})
        if end is None:
            continue
        duration_ms = int(round(end * 1000)) - int(round(time_seconds * 1000))
        if duration_ms <= 0:
            continue
        lines.append((format_clock_milliseconds(duration_ms), time_seconds))
    return lines


LAP_REPORT_COLUMN_GAP = "  "
LAP_TIME_COLUMN_MIN_WIDTH = 8
OUT_LAP_LABEL = "out lap"
HOT_LAP_LABEL = "hot lap"
IN_LAP_LABEL = "in lap"
FASTEST_HOT_LAP_COLOUR = "\033[1;38;5;226m"
ANSI_RESET = "\033[0m"


def _lap_report_row(label, start_seconds):
    if label in (OUT_LAP_LABEL, IN_LAP_LABEL):
        return label, "", start_seconds
    return HOT_LAP_LABEL, label, start_seconds


def _time_index_parts(start_seconds):
    seconds_text = f"{start_seconds:.3f}"
    total_milliseconds = int(seconds_text.replace(".", ""))
    minutes, remainder_milliseconds = divmod(total_milliseconds, 60_000)
    seconds, milliseconds = divmod(remainder_milliseconds, 1000)
    return minutes, seconds, milliseconds, seconds_text


def format_time_index(start_seconds, minute_width, seconds_width):
    minutes, seconds, milliseconds, seconds_text = _time_index_parts(start_seconds)
    return (
        f"{minutes:>{minute_width}}:{seconds:02d}.{milliseconds:03d} "
        f"({seconds_text:>{seconds_width}})"
    )


def lap_time_milliseconds(lap_time):
    if ":" in lap_time:
        minutes_text, seconds_text = lap_time.split(":", 1)
    else:
        minutes_text, seconds_text = "0", lap_time
    seconds_text, milliseconds_text = seconds_text.split(".", 1)
    return int(minutes_text) * 60_000 + int(seconds_text) * 1000 + int(milliseconds_text)


def colour_fastest_hot_lap(line, lap_type, lap_time, fastest_milliseconds):
    if lap_type != HOT_LAP_LABEL or not lap_time:
        return line
    if lap_time_milliseconds(lap_time) != fastest_milliseconds:
        return line
    return f"{FASTEST_HOT_LAP_COLOUR}{line}{ANSI_RESET}"


def format_lap_report(entries):
    rows = [_lap_report_row(label, start_seconds) for label, start_seconds in entries]
    type_width = max(len(OUT_LAP_LABEL), len(HOT_LAP_LABEL), len(IN_LAP_LABEL))
    time_width = LAP_TIME_COLUMN_MIN_WIDTH
    minute_width = 0
    seconds_width = 0
    hot_lap_milliseconds = []
    for lap_type, lap_time, start_seconds in rows:
        time_width = max(time_width, len(lap_time))
        minutes, _, _, seconds_text = _time_index_parts(start_seconds)
        minute_width = max(minute_width, len(str(minutes)))
        seconds_width = max(seconds_width, len(seconds_text))
        if lap_type == HOT_LAP_LABEL and lap_time:
            hot_lap_milliseconds.append(lap_time_milliseconds(lap_time))
    fastest_milliseconds = min(hot_lap_milliseconds) if hot_lap_milliseconds else None
    gap = LAP_REPORT_COLUMN_GAP
    lines = []
    for lap_type, lap_time, start_seconds in rows:
        line = (
            f"{lap_type:<{type_width}}{gap}{lap_time:<{time_width}}{gap}"
            f"{format_time_index(start_seconds, minute_width, seconds_width)}"
        )
        lines.append(colour_fastest_hot_lap(line, lap_type, lap_time, fastest_milliseconds))
    return lines


def crop_showinfo_filter(crop):
    crop_width, crop_height, crop_x, crop_y = crop
    return f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y},showinfo"


def read_rawvideo_crop(command, crop, video_path, progress=None, keyframe_count=None):
    crop_width, crop_height, _, _ = crop
    if crop_width < 2 or crop_height < 2:
        raise ValueError(f"crop is too small for {video_path}")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr_lines = []

    def read_stderr():
        for line in process.stderr:
            stderr_lines.append(line)

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    frame_bytes = crop_width * crop_height * 3
    frames = []
    while True:
        data = read_exact(process.stdout, frame_bytes)
        if len(data) != frame_bytes:
            break
        frames.append(data)
        frame_number = len(frames)
        if progress is not None and frame_number % INDEX_PROGRESS_STRIDE == 0:
            progress(index_progress_message(frame_number, keyframe_count))
    if progress is not None and frames and len(frames) % INDEX_PROGRESS_STRIDE != 0:
        progress(index_progress_message(len(frames), keyframe_count))
    stderr_thread.join()
    return_code = process.wait()
    stderr_text = b"".join(stderr_lines).decode("utf-8", errors="replace")
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command, stderr=stderr_text)
    pts_times = showinfo_pts_times(stderr_text)
    if len(pts_times) != len(frames):
        raise ValueError(
            f"ffmpeg returned {len(frames)} frames but {len(pts_times)} pts times for {video_path}"
        )
    return frames, pts_times


def read_keyframe_crop(video_path, crop, progress, keyframe_count):
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-skip_frame", "nokey",
        "-i", video_path,
        "-vf", crop_showinfo_filter(crop),
        "-vsync", "vfr",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]
    return read_rawvideo_crop(command, crop, video_path, progress, keyframe_count)


def absolute_span_times(pts_times, start_seconds, video_path):
    if not pts_times:
        return []
    first = pts_times[0]
    if abs(first) <= LAP_PTS_ORIGIN_TOLERANCE_SECONDS:
        return [start_seconds + pts_time for pts_time in pts_times]
    if abs(first - start_seconds) <= LAP_PTS_ORIGIN_TOLERANCE_SECONDS:
        return list(pts_times)
    raise ValueError(
        f"ffmpeg pts_time {first} is not near 0 or {start_seconds} for {video_path}"
    )


def read_span_crop(video_path, crop, start_seconds, end_seconds):
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-ss", f"{start_seconds:.6f}",
        "-to", f"{end_seconds:.6f}",
        "-i", video_path,
        "-vf", crop_showinfo_filter(crop),
        "-vsync", "vfr",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]
    frames, pts_times = read_rawvideo_crop(command, crop, video_path)
    return frames, absolute_span_times(pts_times, start_seconds, video_path)


def lap_start_in_bracket(video_path, bracket, crop, letter_box, digit_box):
    previous_time, new_time, new_digit = bracket
    raw_frames, times = read_span_crop(video_path, crop, previous_time, new_time)
    digits = classify_raw_frames(raw_frames, crop, letter_box, digit_box)
    return held_lap_start_time(zip(times, digits, strict=True), new_digit)


def hud_keyframe_filter(lap_crop, timer_crop):
    lap_width, lap_height, lap_x, lap_y = lap_crop
    timer_width, timer_height, timer_x, timer_y = timer_crop
    stacked_height = max(lap_height, timer_height)
    return (
        "split[lap][timer];"
        f"[lap]crop={lap_width}:{lap_height}:{lap_x}:{lap_y},"
        f"pad={lap_width}:{stacked_height}:0:0[lap_out];"
        f"[timer]crop={timer_width}:{timer_height}:{timer_x}:{timer_y},"
        f"pad={timer_width}:{stacked_height}:0:0[timer_out];"
        "[lap_out][timer_out]hstack,showinfo"
    )


def split_hud_frame(frame, lap_crop, timer_crop):
    lap_width, lap_height, _, _ = lap_crop
    timer_width, timer_height, _, _ = timer_crop
    lap = frame[:lap_height, :lap_width]
    timer = frame[:timer_height, lap_width:lap_width + timer_width]
    return lap, timer


def read_hud_keyframe_samples(
    video_path, lap_crop, timer_crop, letter_box, digit_box, progress, keyframe_count,
):
    lap_width, lap_height, _, _ = lap_crop
    timer_width, timer_height, _, _ = timer_crop
    stacked_height = max(lap_height, timer_height)
    stacked_width = lap_width + timer_width
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-skip_frame", "nokey",
        "-i", video_path,
        "-vf", hud_keyframe_filter(lap_crop, timer_crop),
        "-vsync", "vfr",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]
    raw_frames, pts_times = read_rawvideo_crop(
        command, (stacked_width, stacked_height, 0, 0), video_path, progress, keyframe_count,
    )
    digit_samples = []
    timer_samples = []
    for index, data in enumerate(raw_frames):
        frame = np.frombuffer(data, dtype=np.uint8).reshape((stacked_height, stacked_width, 3))
        lap, timer = split_hud_frame(frame, lap_crop, timer_crop)
        digit = classify_lap_image(np.ascontiguousarray(lap), letter_box, digit_box)
        state = timer_glyph_state(cv2.cvtColor(np.ascontiguousarray(timer), cv2.COLOR_BGR2GRAY))
        digit_samples.append((pts_times[index], digit))
        timer_samples.append((pts_times[index], state))
        raw_frames[index] = None
    return digit_samples, timer_samples


def timer_states_from_raw(raw_frames, crop):
    crop_width, crop_height, _, _ = crop
    states = []
    for index, data in enumerate(raw_frames):
        image = np.frombuffer(data, dtype=np.uint8).reshape((crop_height, crop_width, 3))
        states.append(timer_glyph_state(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)))
        raw_frames[index] = None
    return states


def garage_exit_in_bracket(video_path, bracket, crop, letter_box, digit_box):
    previous_time, appearance_time = bracket
    raw_frames, times = read_span_crop(video_path, crop, previous_time, appearance_time)
    digits = classify_raw_frames(raw_frames, crop, letter_box, digit_box)
    return first_held_time(
        zip(times, digits, strict=True),
        lambda digit: digit is not None,
        LAP_DIGIT_HOLD_FRAMES,
    )


def timer_restart_time(frames):
    has_seen_long = False
    run_length = 0
    run_start = None
    for time_seconds, state in frames:
        if state == "long":
            has_seen_long = True
            run_length = 0
            continue
        if not has_seen_long or state != "short":
            run_length = 0
            continue
        if run_length == 0:
            run_start = time_seconds
        run_length += 1
        if run_length >= LAP_DIGIT_HOLD_FRAMES:
            return run_start
    return None


def in_lap_in_bracket(video_path, bracket, crop):
    previous_time, short_time = bracket
    raw_frames, times = read_span_crop(video_path, crop, previous_time, short_time)
    states = timer_states_from_raw(raw_frames, crop)
    return timer_restart_time(zip(times, states, strict=True))


def kept_times(starts, duration):
    kept = []
    for start in starts:
        if start is None or start < 0:
            continue
        if duration is not None and start > duration:
            continue
        kept.append(start)
    kept.sort()
    return kept


def map_refinements(jobs, progress):
    job_count = len(jobs)
    if job_count == 0:
        return []
    done_count = 0
    done_lock = threading.Lock()

    def run_one(job):
        nonlocal done_count
        result = job()
        with done_lock:
            done_count += 1
            if progress is not None:
                progress(index_progress_message(done_count, job_count))
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=LAP_REFINE_WORKERS) as executor:
        futures = [executor.submit(run_one, job) for job in jobs]
        return [future.result() for future in futures]


def index_lap_session(video_path, progress=None):
    """Return flying-lap starts and the console classification lines."""
    frame_width, frame_height, duration = probe_video_geometry(video_path)
    lap_crop = lap_crop_for_frame(frame_width, frame_height)
    timer_crop = timer_crop_for_frame(frame_width, frame_height)
    letter_box = scale_reference_box(
        LAP_LETTER_X, LAP_LETTER_Y, LAP_LETTER_WIDTH, LAP_LETTER_HEIGHT, frame_width, frame_height,
    )
    digit_box = scale_reference_box(
        LAP_DIGIT_X, LAP_DIGIT_Y, LAP_DIGIT_WIDTH, LAP_DIGIT_HEIGHT, frame_width, frame_height,
    )
    keyframe_count = count_keyframes(video_path)
    digit_samples, timer_samples = read_hud_keyframe_samples(
        video_path, lap_crop, timer_crop, letter_box, digit_box, progress, keyframe_count,
    )
    flying_brackets = lap_brackets_from_digits(digit_samples)
    paired = [
        (time_seconds, digit, state)
        for (time_seconds, digit), (_timer_time, state) in zip(digit_samples, timer_samples, strict=True)
    ]
    garage_brackets = garage_exit_brackets(paired)
    in_brackets = in_lap_brackets(timer_samples, flying_brackets)
    flying_jobs = [
        lambda bracket=bracket: lap_start_in_bracket(
            video_path, bracket, lap_crop, letter_box, digit_box,
        )
        for bracket in flying_brackets
    ]
    garage_jobs = [
        lambda bracket=bracket: garage_exit_in_bracket(
            video_path, bracket, lap_crop, letter_box, digit_box,
        )
        for bracket in garage_brackets
    ]
    in_jobs = [
        lambda bracket=bracket: in_lap_in_bracket(video_path, bracket, timer_crop)
        for bracket in in_brackets
    ]
    refined = map_refinements(flying_jobs + garage_jobs + in_jobs, progress)
    flying_count = len(flying_jobs)
    garage_count = len(garage_jobs)
    flying_starts = kept_times(refined[:flying_count], duration)
    garage_exits = kept_times(refined[flying_count:flying_count + garage_count], duration)
    in_laps = kept_times(refined[flying_count + garage_count:], duration)
    entries = classify_finished_laps(flying_starts, garage_exits, in_laps)
    return flying_starts, format_lap_report(entries)


def failure_message(error, video_path):
    message = str(error)
    if video_path not in message:
        return f"{message} ({video_path})"
    return message


def print_lap_report(report_lines):
    for line in report_lines:
        print(line, file=sys.stderr)


def print_lap_starts(video_path):
    started = time.perf_counter()
    try:
        starts, report_lines = index_lap_session(video_path)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(failure_message(error, video_path), file=sys.stderr)
        raise SystemExit(1) from error
    elapsed = time.perf_counter() - started
    print_lap_report(report_lines)
    for start in starts:
        print(f"{start:.3f}")
    print(f"indexed {len(starts)} laps in {elapsed:.1f} s", file=sys.stderr)


class VideoFrameExtractor(tk.Tk):
    def __init__(self, file_path):
        super().__init__()
        self.title("Frame Extractor")

        self.video_path = file_path
        self.vid_cap = None
        self.current_frame = None
        self.total_frames = 0
        self.current_image = None
        self.display_image = None
        self.fps = 0  # Frames per second of the video
        self.lap_starts = []
        self.has_lap_index = False
        self.is_indexing_laps = False
        self.lap_index_queue = queue.Queue()
        self.mask_pixels = None
        self.mask_pixel_count = 0
        self.nearby_penalty_pixels = None
        self.nearby_penalty_pixel_count = 0
        self.nearby_penalty_weight = 0.35
        self.nearby_penalty_radius_px = 10
        self.search_window_increment_seconds = 5 * 60
        self.search_window_start_seconds = 0

        self.canvas = tk.Canvas(self)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X)

        btn_prev_frame = tk.Button(control_frame, text="<< Prev Frame", command=self.prev_frame)
        btn_prev_frame.pack(side=tk.LEFT)

        btn_next_frame = tk.Button(control_frame, text="Next Frame >>", command=self.next_frame)
        btn_next_frame.pack(side=tk.LEFT)

        jump_label = tk.Label(control_frame, text="Jump to frame/time:")
        jump_label.pack(side=tk.LEFT)

        self.jump_entry = tk.Entry(control_frame)
        self.jump_entry.bind("<Return>", self.jump_to_frame)
        self.jump_entry.pack(side=tk.LEFT)

        btn_auto_detect_red = tk.Button(control_frame, text="Auto Detect Red", command=self.auto_detect_red_frame)
        btn_auto_detect_red.pack(side=tk.RIGHT)

        btn_save_frame = tk.Button(control_frame, text="Save Frame", command=self.save_frame)
        btn_save_frame.pack(side=tk.RIGHT)

        lap_control_frame = tk.Frame(self)
        lap_control_frame.pack(side=tk.TOP, fill=tk.X)

        self.index_laps_button = tk.Button(lap_control_frame, text="Index laps", command=self.start_index_laps)
        self.index_laps_button.pack(side=tk.LEFT)

        btn_prev_lap = tk.Button(lap_control_frame, text="Prev lap start", command=self.show_previous_lap_start)
        btn_prev_lap.pack(side=tk.LEFT)

        btn_next_lap = tk.Button(lap_control_frame, text="Next lap start", command=self.show_next_lap_start)
        btn_next_lap.pack(side=tk.LEFT)

        # Label to display the current frame and time
        self.status_label = Label(self, text="Frame: 0 Time: 0s")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, anchor=tk.CENTER)

        self.bind("<Configure>", self.on_resize)

        # Load video from the given file path
        self.load_video(file_path)

    def update_status(self):
        if self.vid_cap is not None:
            time_in_seconds = self.current_frame / self.fps
            hours = int(time_in_seconds // 3600)
            minutes = int((time_in_seconds % 3600) // 60)
            seconds = time_in_seconds % 60

            if hours > 0:
                time_str = f"{hours:02}:{minutes:02}:{seconds:06.4f}"
            else:
                time_str = f"{minutes:02}:{seconds:06.4f}"

            self.status_label.config(text=f"Frame: {self.current_frame} Time: {time_str} ({time_in_seconds:06.4f}s)")
            self.jump_entry.delete(0, tk.END)
            self.jump_entry.insert(0, time_str)

    def load_video(self, file_path):
        self.vid_cap = cv2.VideoCapture(file_path)
        if not self.vid_cap.isOpened():
            messagebox.showerror("Error", f"Cannot open video file: {file_path}")
            self.destroy()
            return

        self.total_frames = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.vid_cap.get(cv2.CAP_PROP_FPS)
        self.current_frame = 0
        self.search_window_start_seconds = 0

        frame_width = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.load_mask(frame_width, frame_height)

        # Set the width to 1280 pixels and calculate the height to maintain 16:9 aspect ratio
        self.width = 960
        self.height = int(self.width * 9 / 16)

        self.geometry(f"{self.width}x{self.height + WINDOW_CONTROL_HEIGHT}")
        self.canvas.config(width=self.width, height=self.height)

        self.show_frame()

    def load_mask(self, frame_width, frame_height):
        mask_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mask.png")
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        if mask is None:
            self.mask_pixels = None
            self.mask_pixel_count = 0
            self.nearby_penalty_pixels = None
            self.nearby_penalty_pixel_count = 0
            messagebox.showwarning("Mask Missing", f"Could not load mask file: {mask_path}")
            return

        resized_mask = cv2.resize(mask, (frame_width, frame_height), interpolation=cv2.INTER_NEAREST)
        _, binary_mask = cv2.threshold(resized_mask, 127, 255, cv2.THRESH_BINARY)
        self.mask_pixels = binary_mask > 0
        self.mask_pixel_count = int(np.count_nonzero(self.mask_pixels))

        kernel_size = max(3, (2 * self.nearby_penalty_radius_px) + 1)
        penalty_kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        dilated_mask = cv2.dilate(binary_mask, penalty_kernel, iterations=1) > 0
        self.nearby_penalty_pixels = np.logical_and(dilated_mask, np.logical_not(self.mask_pixels))
        self.nearby_penalty_pixel_count = int(np.count_nonzero(self.nearby_penalty_pixels))

        if self.nearby_penalty_pixel_count == 0:
            self.nearby_penalty_pixels = None

        if self.mask_pixel_count == 0:
            self.mask_pixels = None
            self.nearby_penalty_pixels = None
            self.nearby_penalty_pixel_count = 0
            messagebox.showwarning("Mask Invalid", "mask.png did not contain any white mask pixels after resizing.")

    def calculate_red_score(self, frame):
        if self.mask_pixels is None or self.mask_pixel_count == 0:
            return -1.0

        rgb_frame = frame.astype(np.float32) / 255.0
        r_channel = rgb_frame[:, :, 2]
        g_channel = rgb_frame[:, :, 1]
        b_channel = rgb_frame[:, :, 0]

        # Blend geometric closeness to pure red with red dominance to reduce false positives.
        distance_to_red = np.sqrt((1.0 - r_channel) ** 2 + g_channel ** 2 + b_channel ** 2)
        closeness_to_red = 1.0 - (distance_to_red / np.sqrt(3.0))
        red_dominance = np.clip(r_channel - np.maximum(g_channel, b_channel), 0.0, 1.0)

        combined_score = (0.4 * closeness_to_red) + (0.6 * red_dominance)
        in_mask_score = float(np.mean(combined_score[self.mask_pixels]))

        nearby_penalty_score = 0.0
        if self.nearby_penalty_pixels is not None and self.nearby_penalty_pixel_count > 0:
            # Penalize nearby red bleed outside the circles.
            nearby_penalty_score = float(np.mean(red_dominance[self.nearby_penalty_pixels]))

        final_score = in_mask_score - (self.nearby_penalty_weight * nearby_penalty_score)
        return float(np.clip(final_score, -1.0, 1.0))

    def find_frame_before_red_drop(self, start_frame, peak_score):
        # Balanced defaults: require both relative and absolute drop to avoid noise-triggered detection.
        drop_ratio_threshold = 0.70
        drop_abs_threshold = 0.07
        consecutive_drop_frames_required = 2

        if self.vid_cap is None or start_frame >= self.total_frames - 1:
            return start_frame, peak_score, start_frame, peak_score, False

        last_stable_frame = start_frame
        last_stable_score = peak_score
        first_drop_frame = None
        first_drop_score = None
        drop_streak = 0

        total_refine_frames = max(self.total_frames - (start_frame + 1), 1)

        for offset, frame_number in enumerate(range(start_frame + 1, self.total_frames), start=1):
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.vid_cap.read()
            if not ret:
                continue

            current_score = self.calculate_red_score(frame)
            relative_threshold = peak_score * drop_ratio_threshold
            is_significant_drop = (
                current_score <= relative_threshold
                and (peak_score - current_score) >= drop_abs_threshold
            )

            if is_significant_drop:
                if drop_streak == 0:
                    first_drop_frame = frame_number
                    first_drop_score = current_score
                drop_streak += 1
            else:
                drop_streak = 0
                first_drop_frame = None
                first_drop_score = None
                last_stable_frame = frame_number
                last_stable_score = current_score

            if offset % max(int(self.fps), 1) == 0 or frame_number == self.total_frames - 1:
                percent = (offset / total_refine_frames) * 100
                refine_text = (
                    f"Refining lights-out frame... {percent:05.2f}% "
                    f"(score: {current_score:.4f}, threshold: {relative_threshold:.4f})"
                )
                self.status_label.config(text=refine_text)
                self.update_idletasks()
                print(refine_text, end="\r", flush=True)

            if drop_streak >= consecutive_drop_frames_required and first_drop_frame is not None:
                return last_stable_frame, last_stable_score, first_drop_frame, first_drop_score, True

        return start_frame, peak_score, start_frame, peak_score, False

    def auto_detect_red_frame(self):
        if self.vid_cap is None:
            return

        if self.mask_pixels is None or self.mask_pixel_count == 0:
            messagebox.showerror("Mask Error", "Cannot run detection without a valid mask.png.")
            return

        stride_seconds = 0.5
        stride_frames = max(1, int(round(self.fps * stride_seconds)))

        current_window_start_seconds = self.search_window_start_seconds
        current_window_end_seconds = current_window_start_seconds + self.search_window_increment_seconds

        if self.fps > 0:
            start_frame = min(
                self.total_frames,
                max(0, int(round(current_window_start_seconds * self.fps))),
            )
            end_frame_exclusive = min(
                self.total_frames,
                max(1, int(round(current_window_end_seconds * self.fps))),
            )
        else:
            start_frame = 0
            end_frame_exclusive = self.total_frames

        if start_frame >= self.total_frames or start_frame >= end_frame_exclusive:
            messagebox.showinfo(
                "Search Complete",
                "No more 5-minute windows left in this video. Reload the video to restart from 0:00.",
            )
            return

        window_start_minutes = current_window_start_seconds / 60.0
        window_end_minutes = (end_frame_exclusive / self.fps) / 60.0 if self.fps > 0 else 0

        self.status_label.config(
            text=(
                f"Scanning red lights in {window_start_minutes:.1f}-{window_end_minutes:.1f} min "
                f"(every {stride_seconds:.1f}s)..."
            )
        )
        self.update_idletasks()
        print(
            f"Scanning red lights in {window_start_minutes:.1f}-{window_end_minutes:.1f} min "
            f"(every {stride_seconds:.1f}s)..."
        )

        best_frame_number = self.current_frame
        best_score = -1.0
        processed_samples = 0
        printed_inline_progress = False

        frame_indices = list(range(start_frame, end_frame_exclusive, stride_frames))
        if end_frame_exclusive > start_frame and frame_indices and frame_indices[-1] != end_frame_exclusive - 1:
            frame_indices.append(end_frame_exclusive - 1)

        total_samples = len(frame_indices)

        for sample_index, frame_number in enumerate(frame_indices, start=1):
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.vid_cap.read()
            if not ret:
                continue

            score = self.calculate_red_score(frame)
            if score > best_score:
                best_score = score
                best_frame_number = frame_number

            processed_samples += 1

            if sample_index % max(int(self.fps), 1) == 0 or sample_index == total_samples:
                percent = (sample_index / max(total_samples, 1)) * 100
                progress_text = (
                    f"Scanning red lights in {window_start_minutes:.1f}-{window_end_minutes:.1f} min "
                    f"(every {stride_seconds:.1f}s)... "
                    f"{percent:05.2f}% (best score: {best_score:.4f})"
                )
                self.status_label.config(text=progress_text)
                self.update_idletasks()
                print(progress_text, end="\r", flush=True)
                printed_inline_progress = True

        if printed_inline_progress:
            print()

        if processed_samples == 0:
            messagebox.showerror("Detection Error", "No frames were processed during auto detection.")
            return

        print("Refining detected peak to frame right before red lights disappear...")
        pre_drop_frame, pre_drop_score, first_drop_frame, first_drop_score, drop_found = self.find_frame_before_red_drop(
            best_frame_number,
            best_score,
        )
        print()

        self.current_frame = pre_drop_frame
        self.show_frame()

        selected_time_seconds = (self.current_frame / self.fps) if self.fps > 0 else 0.0

        if drop_found:
            pre_drop_time_seconds = (pre_drop_frame / self.fps) if self.fps > 0 else 0.0
            first_drop_time_seconds = (first_drop_frame / self.fps) if self.fps > 0 else 0.0
            final_text = (
                f"Pre-drop frame: {pre_drop_frame} ({pre_drop_time_seconds:.4f}s) score {pre_drop_score:.4f} | "
                f"First drop frame: {first_drop_frame} ({first_drop_time_seconds:.4f}s) score {first_drop_score:.4f}"
            )
        else:
            final_text = (
                f"Frame: {best_frame_number} (peak red) | Peak score: {best_score:.4f} | "
                "No significant drop found ahead"
            )

        self.status_label.config(text=final_text)
        print(final_text)
        print(f"Selected frame/time: {self.current_frame} ({selected_time_seconds:.4f}s)")

        self.search_window_start_seconds += self.search_window_increment_seconds
        if self.fps > 0:
            max_video_seconds = self.total_frames / self.fps
            if self.search_window_start_seconds >= max_video_seconds:
                print("Next search window: end of video reached")
            else:
                next_window_start_seconds = self.search_window_start_seconds
                next_window_end_seconds = min(
                    next_window_start_seconds + self.search_window_increment_seconds,
                    max_video_seconds,
                )
                print(
                    f"Next search window: {next_window_start_seconds / 60.0:.1f}-"
                    f"{next_window_end_seconds / 60.0:.1f} min"
                )

    def show_frame(self):
        if self.vid_cap is not None:
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            ret, frame = self.vid_cap.read()
            if ret:
                # Keep the UI frame index aligned with the actual decoded frame index.
                actual_frame = int(self.vid_cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                if actual_frame >= 0:
                    self.current_frame = actual_frame

                self.current_image = frame

                if self.width > 0 and self.height > 0:
                    display_frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                    self.display_image = Image.fromarray(display_frame)
                    self.photo = ImageTk.PhotoImage(image=self.display_image)
                    self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

                self.update_status()  # Update the status label with the current frame and time

    def next_frame(self):
        if self.vid_cap is not None and self.current_frame < self.total_frames - 1:
            self.current_frame += 1
            self.show_frame()

    def prev_frame(self):
        if self.vid_cap is not None and self.current_frame > 0:
            self.current_frame -= 1
            self.show_frame()

    def jump_to_frame(self, event=None):
        input_value = self.jump_entry.get()
        if self.vid_cap is not None and input_value:
            try:
                if ':' in input_value:
                    # Input is time in format HH:MM:SS or MM:SS
                    time_parts = input_value.split(':')
                    if len(time_parts) == 3:
                        hours, minutes, seconds = map(float, time_parts)
                    elif len(time_parts) == 2:
                        hours = 0
                        minutes, seconds = map(float, time_parts)
                    else:
                        raise ValueError("Invalid time format.")

                    time_in_seconds = hours * 3600 + minutes * 60 + seconds
                    frame_number = int(time_in_seconds * self.fps)
                else:
                    # Input is frame number
                    frame_number = int(input_value)

                if 0 <= frame_number < self.total_frames:
                    self.current_frame = frame_number
                    self.show_frame()
                else:
                    raise ValueError("Invalid frame number.")
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {e}")

    def save_frame(self):
        if self.current_image is not None:
            image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            file_path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG files", "*.jpg"), ("All files", "*.*")])
            if file_path:
                image.save(file_path)

    def start_index_laps(self):
        if self.is_indexing_laps:
            return
        self.is_indexing_laps = True
        self.index_laps_button.config(state=tk.DISABLED)
        worker = threading.Thread(target=self.index_laps_worker, daemon=True)
        worker.start()
        self.after(LAP_INDEX_POLL_MS, self.poll_lap_index)

    def index_laps_worker(self):
        video_path = self.video_path

        def progress(message):
            self.lap_index_queue.put(("progress", message))

        try:
            starts, report_lines = index_lap_session(video_path, progress=progress)
        except Exception as error:
            self.lap_index_queue.put(("error", failure_message(error, video_path)))
            return
        print_lap_report(report_lines)
        self.lap_index_queue.put(("done", starts))

    def poll_lap_index(self):
        if not self.is_indexing_laps:
            return
        try:
            while True:
                kind, payload = self.lap_index_queue.get_nowait()
                if kind == "progress":
                    self.status_label.config(text=payload)
                elif kind == "done":
                    self.finish_lap_index(payload)
                    return
                elif kind == "error":
                    self.fail_lap_index(payload)
                    return
        except queue.Empty:
            pass
        self.after(LAP_INDEX_POLL_MS, self.poll_lap_index)

    def finish_lap_index(self, starts):
        self.lap_starts = starts
        self.has_lap_index = True
        self.is_indexing_laps = False
        self.index_laps_button.config(state=tk.NORMAL)
        if starts:
            self.status_label.config(text=f"Indexed {len(starts)} laps")
        else:
            self.status_label.config(text="No lap starts found")

    def fail_lap_index(self, message):
        self.is_indexing_laps = False
        self.index_laps_button.config(state=tk.NORMAL)
        messagebox.showerror("Error", message)

    def show_next_lap_start(self):
        self.show_lap_start(next_lap_start, "No later lap start")

    def show_previous_lap_start(self):
        self.show_lap_start(previous_lap_start, "No earlier lap start")

    def show_lap_start(self, choose_start, missing_message):
        if not self.has_lap_index:
            self.status_label.config(text="Index laps first")
            return
        if self.vid_cap is None or not self.fps:
            return
        current_seconds = self.current_frame / self.fps
        half_frame = 0.5 / self.fps
        start_seconds = choose_start(self.lap_starts, current_seconds, half_frame)
        if start_seconds is None:
            self.status_label.config(text=missing_message)
            return
        frame_number = int(round(start_seconds * self.fps))
        frame_number = min(max(frame_number, 0), self.total_frames - 1)
        self.current_frame = frame_number
        self.show_frame()

    def on_resize(self, event):
        if self.vid_cap is not None and event.width > 1 and event.height > 1:
            # Maintain 16:9 aspect ratio
            new_width = event.width
            new_height = int(new_width * 9 / 16)
            
            if new_height > event.height - WINDOW_CONTROL_HEIGHT:
                new_height = event.height - WINDOW_CONTROL_HEIGHT
                new_width = int(new_height * 16 / 9)
            
            self.width = new_width
            self.height = new_height
            self.canvas.config(width=self.width, height=self.height)
            self.show_frame()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_file_path")
    parser.add_argument("--index-laps", action="store_true")
    args = parser.parse_args()
    if args.index_laps:
        print_lap_starts(args.video_file_path)
        return
    app = VideoFrameExtractor(args.video_file_path)
    app.mainloop()


if __name__ == "__main__":
    main()

