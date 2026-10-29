import inspect
import subprocess
from unittest.mock import patch

import pytest

import f1_create_split_screen_video as split


def test_preset_defaults_to_veryfast():
    signature = inspect.signature(split.process_and_combine_videos)
    assert signature.parameters["preset"].default == "veryfast"


def test_negative_start_names_the_side():
    with pytest.raises(ValueError, match="right start time"):
        split.require_non_negative_start("right", -0.1)
    split.require_non_negative_start("left", 0)


def test_non_positive_duration_names_both_paths():
    with pytest.raises(ValueError, match="jackey.mp4"):
        split.require_positive_duration(0, "jackey.mp4", "keith.mp4")
    split.require_positive_duration(0.1, "jackey.mp4", "keith.mp4")


def test_ffprobe_failure_names_the_path():
    error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="No such file or directory\n")
    with patch("f1_create_split_screen_video.subprocess.run", side_effect=error):
        with pytest.raises(ValueError, match="missing.mp4"):
            split.get_video_duration("missing.mp4")


def test_ffprobe_empty_duration_names_the_path():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="\n", stderr="")
    with patch("f1_create_split_screen_video.subprocess.run", return_value=completed):
        with pytest.raises(ValueError, match="no duration for clip.mp4"):
            split.get_video_duration("clip.mp4")


def test_loudness_scan_skips_video():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr="    I:         -23.1 LUFS\n"
    )
    with patch("f1_create_split_screen_video.subprocess.run", return_value=completed) as run:
        assert split.measure_loudness("clip.mp4", 1.5, 300) == -23.1
    command = run.call_args.args[0]
    assert "-vn" in command
    assert "clip.mp4" in command
