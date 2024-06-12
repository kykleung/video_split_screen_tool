import argparse
from moviepy.editor import VideoFileClip, clips_array
import multiprocessing

def process_and_combine_videos(left_video_path, left_start_time, right_video_path, right_start_time, output_length=None, output_path="combined_video.mp4"):
    # Load the video files and set start times
    left_clip = VideoFileClip(left_video_path).subclip(left_start_time)
    right_clip = VideoFileClip(right_video_path).subclip(right_start_time)
    
    # Cropping 25% from both sides of each video
    crop_width_left = left_clip.size[0] * 0.25 * 0.5
    left_clip_cropped = left_clip.crop(x1=crop_width_left, x2=left_clip.size[0] - crop_width_left)
    
    crop_width_right = right_clip.size[0] * 0.25 * 0.5
    right_clip_cropped = right_clip.crop(x1=crop_width_right, x2=right_clip.size[0] - crop_width_right)

    # After cropping, resize the videos to have a combined width of 1920px while maintaining aspect ratio
    # Calculate target height based on the aspect ratio of the cropped clips
    target_width_per_clip = 960  # Half of 1920px for each clip
    target_height_left = int((target_width_per_clip / left_clip_cropped.size[0]) * left_clip_cropped.size[1])
    target_height_right = int((target_width_per_clip / right_clip_cropped.size[0]) * right_clip_cropped.size[1])
    
    # Ensuring both clips have the same height by taking the max height to maintain aspect ratio
    final_height = max(target_height_left, target_height_right)
    
    # Resizing clips to have the same height
    left_clip_final = left_clip_cropped.resize(height=final_height)
    right_clip_final = right_clip_cropped.resize(height=final_height)

    # Calculate the padding needed to reach a height of 1080
    total_padding = 1080 - final_height
    top_padding = total_padding // 2
    bottom_padding = total_padding - top_padding
    
    # Add padding to the top and bottom of each clip
    left_clip_final = left_clip_final.margin(top=top_padding, bottom=bottom_padding, color=(0,0,0))
    right_clip_final = right_clip_final.margin(top=top_padding, bottom=bottom_padding, color=(0,0,0))

    # Combine the padded clips side by side
    combined_clip = clips_array([[left_clip_final, right_clip_final]], bg_color=(0, 0, 0))
    
    # Find the duration of each original clip after applying start time offset
    left_duration = left_clip.duration - left_start_time
    right_duration = right_clip.duration - right_start_time
    
    # Determine the duration of the shorter clip
    final_duration = min(left_duration, right_duration)

    # If output_length is specified and valid, use it as the final duration
    if output_length is not None and 0 < output_length < final_duration:
        final_duration = output_length
    
    # Trim the combined clip to match the duration of the shorter input clip
    final_clip = combined_clip.subclip(0, final_duration)
    
    # Write the output file
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=multiprocessing.cpu_count())


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



