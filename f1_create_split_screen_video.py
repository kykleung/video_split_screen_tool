import argparse
import subprocess
import time

def process_and_combine_videos(left_video_path, left_start_time, right_video_path, right_start_time, output_length=None, output_path="combined_video.mp4"):
    # Temporary file paths for intermediate processing
    left_temp = "left_temp.mp4"
    right_temp = "right_temp.mp4"

    # Get the duration of the input videos
    def get_video_duration(video_path):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return float(result.stdout.strip())

    left_duration = get_video_duration(left_video_path) - left_start_time
    right_duration = get_video_duration(right_video_path) - right_start_time

    # Determine the processing length for each video
    left_length = min(output_length, left_duration) if output_length else left_duration
    right_length = min(output_length, right_duration) if output_length else right_duration

    # Crop, resize, and pad the left video
    start_time = time.time()
    left_crop_resize_cmd = [
        "ffmpeg", "-i", left_video_path, "-ss", str(left_start_time),
        "-vf", "crop=in_w*0.75:in_h,scale=960:-1,pad=960:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-t", str(left_length) if output_length else "99999", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-threads", "0", left_temp
    ]
    subprocess.run(left_crop_resize_cmd, check=True)
    left_processing_time = time.time() - start_time

    # Crop, resize, and pad the right video
    start_time = time.time()
    right_crop_resize_cmd = [
        "ffmpeg", "-i", right_video_path, "-ss", str(right_start_time),
        "-vf", "crop=in_w*0.75:in_h,scale=960:-1,pad=960:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-t", str(right_length) if output_length else "99999", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-threads", "0", right_temp
    ]
    subprocess.run(right_crop_resize_cmd, check=True)
    right_processing_time = time.time() - start_time

    # Combine the two videos side by side
    start_time = time.time()
    combine_cmd = [
        "ffmpeg", "-i", left_temp, "-i", right_temp,
        "-filter_complex", "[0:v][1:v]hstack=inputs=2:shortest=1;[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "aac", "-b:a", "192k",
        "-threads", "0", output_path
    ]
    subprocess.run(combine_cmd, check=True)
    combine_processing_time = time.time() - start_time

    # Clean up temporary files
    subprocess.run(["rm", left_temp, right_temp])

    # Report processing times
    print("\nProcessing Times:")
    print(f"Left video processing time: {left_processing_time:.2f} seconds")
    print(f"Right video processing time: {right_processing_time:.2f} seconds")
    print(f"Video combining time: {combine_processing_time:.2f} seconds")
    print(f"Total processing time: {left_processing_time + right_processing_time + combine_processing_time:.2f} seconds")

    # Calculate and report efficiency
    final_duration = min(left_length, right_length)
    efficiency = (left_processing_time + right_processing_time + combine_processing_time) / final_duration * 100
    print(f"Video duration: {final_duration:.2f} seconds")
    print(f"Efficiency: {efficiency:.2f}% of the final output video duration")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and combine two videos side by side to achieve a standard 1080p resolution output video.")
    parser.add_argument("left_video_path", help="Path to the left video file.")
    parser.add_argument("left_start_time", type=float, help="Starting time of the left video in seconds, can be a decimal.")
    parser.add_argument("right_video_path", help="Path to the right video file.")
    parser.add_argument("right_start_time", type=float, help="Starting time of the right video in seconds, can be a decimal.")
    parser.add_argument("--output_length", type=float, help="Desired length of the output video in seconds, can be a decimal.", default=None)
    parser.add_argument("--output_path", default="combined_video.mp4", help="Output path for the combined video.")

    args = parser.parse_args()

    process_and_combine_videos(args.left_video_path, args.left_start_time, args.right_video_path, args.right_start_time, args.output_length, args.output_path)