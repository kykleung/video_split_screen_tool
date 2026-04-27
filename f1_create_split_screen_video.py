import argparse
import subprocess
import time
import threading

def get_video_duration(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return float(result.stdout.strip())


def process_and_combine_videos(
    left_video_path, left_start_time,
    right_video_path, right_start_time,
    output_length=None,
    output_path="combined_video.mp4",
    preset="medium",
    use_hwaccel=False,
    single_pass=True,
):
    left_available_duration = get_video_duration(left_video_path) - left_start_time
    right_available_duration = get_video_duration(right_video_path) - right_start_time

    # Only process up to the shortest available duration (or output_length if specified)
    final_duration = min(left_available_duration, right_available_duration)
    if output_length is not None:
        final_duration = min(final_duration, output_length)

    video_encoder = "h264_videotoolbox" if use_hwaccel else "libx264"
    # VideoToolbox uses -q:v (quality scale) instead of -crf
    quality_args = ["-q:v", "50"] if use_hwaccel else ["-crf", "18"]

    if single_pass:
        # --------------- Single-pass: crop + hstack + encode in one ffmpeg call ---------------
        # This avoids writing/reading two intermediate files and re-encoding a third time.
        filter_complex = (
            f"[0:v]trim=start={left_start_time}:duration={final_duration},setpts=PTS-STARTPTS,"
            f"crop=in_w*0.75:in_h,scale=960:-1,pad=960:1080:(ow-iw)/2:(oh-ih)/2:black[left];"
            f"[1:v]trim=start={right_start_time}:duration={final_duration},setpts=PTS-STARTPTS,"
            f"crop=in_w*0.75:in_h,scale=960:-1,pad=960:1080:(ow-iw)/2:(oh-ih)/2:black[right];"
            f"[left][right]hstack=inputs=2[v];"
            f"[0:a]atrim=start={left_start_time}:duration={final_duration},asetpts=PTS-STARTPTS[al];"
            f"[1:a]atrim=start={right_start_time}:duration={final_duration},asetpts=PTS-STARTPTS[ar];"
            f"[al][ar]amix=inputs=2:duration=first:dropout_transition=3[a]"
        )
        cmd = [
            "ffmpeg",
            "-i", left_video_path,
            "-i", right_video_path,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", video_encoder,
        ] + quality_args + [
            "-preset", preset,  # ignored by videotoolbox but harmless
            "-c:a", "aac", "-b:a", "192k",
            "-threads", "0",
            output_path
        ]
        # Remove -preset for hwaccel (VideoToolbox doesn't support it)
        if use_hwaccel:
            cmd = [x for x in cmd if x != "-preset" and x != preset]

        start_time = time.time()
        subprocess.run(cmd, check=True)
        total_time = time.time() - start_time

        print("\nProcessing Times (single-pass):")
        print(f"Total processing time: {total_time:.2f} seconds")
        print(f"Video duration: {final_duration:.2f} seconds")
        efficiency = total_time / final_duration * 100
        print(f"Efficiency: {efficiency:.2f}% of the final output video duration")

    else:
        # --------------- Three-step approach with parallel left/right processing ---------------
        left_temp = "left_temp.mp4"
        right_temp = "right_temp.mp4"
        timings = {}
        exceptions = {}

        def process_side(label, in_path, start_sec, out_path):
            t0 = time.time()
            crop_cmd = [
                "ffmpeg", "-i", in_path, "-ss", str(start_sec),
                "-vf", "crop=in_w*0.75:in_h,scale=960:-1,pad=960:1080:(ow-iw)/2:(oh-ih)/2:black",
                "-t", str(final_duration),
                "-c:v", video_encoder,
            ] + quality_args + [
                "-preset", preset,
                "-threads", "0", out_path
            ]
            if use_hwaccel:
                crop_cmd = [x for x in crop_cmd if x != "-preset" and x != preset]
            try:
                subprocess.run(crop_cmd, check=True)
            except Exception as e:
                exceptions[label] = e
            timings[label] = time.time() - t0

        left_thread = threading.Thread(target=process_side, args=("left", left_video_path, left_start_time, left_temp))
        right_thread = threading.Thread(target=process_side, args=("right", right_video_path, right_start_time, right_temp))

        left_thread.start()
        right_thread.start()
        left_thread.join()
        right_thread.join()

        if exceptions:
            raise RuntimeError(f"Side processing failed: {exceptions}")

        # Combine videos (stream-copy video from already-encoded temp files, re-encode audio only)
        start_time = time.time()
        combine_cmd = [
            "ffmpeg", "-i", left_temp, "-i", right_temp,
            "-filter_complex", "[0:v][1:v]hstack=inputs=2:shortest=1[v];[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", video_encoder,
        ] + quality_args + [
            "-preset", preset,
            "-c:a", "aac", "-b:a", "192k",
            "-threads", "0", output_path
        ]
        if use_hwaccel:
            combine_cmd = [x for x in combine_cmd if x != "-preset" and x != preset]

        subprocess.run(combine_cmd, check=True)
        combine_time = time.time() - start_time

        subprocess.run(["rm", left_temp, right_temp])

        wall_time = max(timings["left"], timings["right"]) + combine_time
        print("\nProcessing Times (parallel three-step):")
        print(f"Left video processing time:  {timings['left']:.2f} seconds")
        print(f"Right video processing time: {timings['right']:.2f} seconds")
        print(f"Video combining time:        {combine_time:.2f} seconds")
        print(f"Wall-clock total time:       {wall_time:.2f} seconds  (left+right ran in parallel)")
        print(f"Video duration: {final_duration:.2f} seconds")
        efficiency = wall_time / final_duration * 100
        print(f"Efficiency: {efficiency:.2f}% of the final output video duration")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process and combine two videos side by side to achieve a standard 1080p resolution output video."
    )
    parser.add_argument("left_video_path", help="Path to the left video file.")
    parser.add_argument("left_start_time", type=float, help="Starting time of the left video in seconds, can be a decimal.")
    parser.add_argument("right_video_path", help="Path to the right video file.")
    parser.add_argument("right_start_time", type=float, help="Starting time of the right video in seconds, can be a decimal.")
    parser.add_argument("--output_length", type=float, help="Desired length of the output video in seconds, can be a decimal.", default=None)
    parser.add_argument("--output_path", default="combined_video.mp4", help="Output path for the combined video.")
    parser.add_argument(
        "--preset", default="medium",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="libx264 encoding preset (default: medium). Use 'fast' or 'ultrafast' for maximum speed."
    )
    parser.add_argument(
        "--hwaccel", action="store_true",
        help="Use macOS VideoToolbox hardware H.264 encoder (h264_videotoolbox) for near-realtime encoding."
    )
    parser.add_argument(
        "--three-step", action="store_true",
        help="Use the older three-step approach (process left, process right, combine) with parallel left/right encoding. "
             "By default the faster single-pass mode is used."
    )

    args = parser.parse_args()

    process_and_combine_videos(
        args.left_video_path, args.left_start_time,
        args.right_video_path, args.right_start_time,
        args.output_length, args.output_path,
        preset=args.preset,
        use_hwaccel=args.hwaccel,
        single_pass=not args.three_step,
    )
