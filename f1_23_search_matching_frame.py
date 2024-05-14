import cv2
import numpy as np
import argparse

def scale_frame(frame, scale_factor):
    return cv2.resize(frame, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA) if scale_factor != 1 else frame

def find_resolution_scale_factor(video1_path, video2_path):
    cap1, cap2 = cv2.VideoCapture(video1_path), cv2.VideoCapture(video2_path)
    width1, height1 = cap1.get(cv2.CAP_PROP_FRAME_WIDTH), cap1.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width2, height2 = cap2.get(cv2.CAP_PROP_FRAME_WIDTH), cap2.get(cv2.CAP_PROP_FRAME_HEIGHT)
    
    # Determine which video has the smaller resolution
    resolution1 = width1 * height1
    resolution2 = width2 * height2
    
    # If video1 has the smaller resolution
    if resolution1 <= resolution2:
        scale_factor1 = 1  # Keep original size for video1
        scale_factor2 = min(width1 / width2, height1 / height2)  # Scale video2 to match video1's resolution
    else:
        scale_factor1 = min(width2 / width1, height2 / height1)  # Scale video1 to match video2's resolution
        scale_factor2 = 1  # Keep original size for video2
        
    cap1.release(), cap2.release()
    return scale_factor1, scale_factor2


def crop_top_percentage(image, x):
    """
    Crop and keep the top x percentage of the image.

    Parameters:
    - image: cv2 image object
    - x: Percentage of the top part of the image to keep (0-100)

    Returns:
    - Cropped image
    """
    if not 0 <= x <= 100:
        raise ValueError("x must be between 0 and 100")

    height = image.shape[0]
    # Calculate the number of pixels to keep
    pixels_to_keep = int((x / 100) * height)

    # Crop the top x% of the image
    cropped_image = image[:pixels_to_keep, :]

    return cropped_image

def crop_from_top_percentage(image, x1, x2):
    """
    Crop and keep the portion from x1 to x2 percent of the image from the top.

    Parameters:
    - image: cv2 image object
    - x1: Starting percentage of the part of the image to keep from the top (0-100)
    - x2: Ending percentage of the part of the image to keep from the top (0-100)

    Returns:
    - Cropped image
    """
    if not 0 <= x1 < x2 <= 100:
        raise ValueError("x1 must be between 0 and 100, x2 must be between 0 and 100, and x1 must be less than x2")

    height = image.shape[0]
    # Calculate the starting and ending pixels
    start_pixel = int((x1 / 100) * height)
    end_pixel = int((x2 / 100) * height)

    # Crop the image from x1% to x2%
    cropped_image = image[start_pixel:end_pixel, :]

    return cropped_image


def gaussian_blur_and_histogram_equalization(image):
    """
    Apply Gaussian Blur and then Histogram Equalization to an image.

    Parameters:
    - image: A cv2 image object (numpy array).

    Returns:
    - result_image: The processed image after applying Gaussian Blur and Histogram Equalization.
    """

    # Apply Gaussian Blur to the image
    blurred_image = cv2.GaussianBlur(image, (5, 5), 0)
    
    #Check if the image is colored (3 channels) or grayscale
    if len(blurred_image.shape) == 3 and blurred_image.shape[2] == 3:
        # Convert the image to the YCrCb color space
        ycrcb_image = cv2.cvtColor(blurred_image, cv2.COLOR_BGR2YCrCb)
        # Split the channels
        y_channel, cr_channel, cb_channel = cv2.split(ycrcb_image)
        # Apply Histogram Equalization to the Y channel
        equalized_y_channel = cv2.equalizeHist(y_channel)
        # Merge the channels back
        merged_channels = cv2.merge((equalized_y_channel, cr_channel, cb_channel))
        # Convert back to the BGR color space
        result_image = cv2.cvtColor(merged_channels, cv2.COLOR_YCrCb2BGR)
    else:
        # Assume the image is grayscale and directly apply Histogram Equalization
        result_image = cv2.equalizeHist(blurred_image)

    return result_image


def find_most_similar_frame(reference_frame, target_video_path, scale_factor, duration_limit):
    
    # Display the concatenated image
    reference_frame = gaussian_blur_and_histogram_equalization(crop_from_top_percentage(reference_frame, 20, 65))
    cv2.imshow("reference frame", reference_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    target_cap = cv2.VideoCapture(target_video_path)
    fps = target_cap.get(cv2.CAP_PROP_FPS)  # Frames per second
    max_frame_number = int(fps * duration_limit)
    
    best_score, best_frame_number = float('inf'), -1
    best_frame_image = None  # Store the unscaled image of the most similar frame
    frame_count = 0
    
    while frame_count < max_frame_number:
        ret, frame = target_cap.read()
        if not ret:
            break
        scaled_frame = scale_frame(frame, scale_factor)
        cropped_scaled_frame = gaussian_blur_and_histogram_equalization(crop_from_top_percentage(scaled_frame, 20, 65))

        # Compute the absolute difference
        diff = cv2.absdiff(reference_frame, cropped_scaled_frame)
        score = np.sum(diff)
        print(f"{frame_count}: {score}") 

        if score < best_score:
            best_score, best_frame_number = score, frame_count
            best_frame_image = frame  # Store the current frame as it's the best match so far
        frame_count += 1
    
    target_cap.release()
    return best_frame_number, best_frame_image


def display_matching_images(image1, image2, window_name="Matching Images"):
    # Concatenate images horizontally
    concatenated_image = cv2.hconcat([image1, image2])

    # Display the concatenated image
    cv2.imshow(window_name, concatenated_image)

    # Wait for a key press and close the window
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main(video1_path, video2_path, duration):
    scale_factor1, scale_factor2 = find_resolution_scale_factor(video1_path, video2_path)
    video1, video2 = cv2.VideoCapture(video1_path), cv2.VideoCapture(video2_path)
    fps_video1, fps_video2 = video1.get(cv2.CAP_PROP_FPS), video2.get(cv2.CAP_PROP_FPS)
    ret, first_frame_video1 = video1.read()
    video1.release()
    video2.release()
    if not ret:
        print("Error reading first frame of video 1.")
        return
    
    scaled_first_frame_video1 = scale_frame(first_frame_video1, scale_factor1)
    cropped_first_frame_video1 = scaled_first_frame_video1[:int(scaled_first_frame_video1.shape[0] * 0.6), :, :]
    frame_number_video1 = 0  # Assuming the first frame is what we're comparing
    best_frame_video1 = first_frame_video1

    # Step 1: Find similar frame in video 2
    frame_number_video2, best_frame_video2 = find_most_similar_frame(scaled_first_frame_video1, video2_path, scale_factor2, duration)
    print(f"Step 1: Similar frame in video 2 found at frame number: {frame_number_video2}")

    # Step 2: Use the found frame in video 2 to perform a reverse search in video 1
    scaled_frame_video2 = scale_frame(best_frame_video2, scale_factor2)
    frame_number_video1, reverse_search_best_frame_video1 = find_most_similar_frame(scaled_frame_video2, video1_path, scale_factor1, duration)
    print(f"Step 2: Reverse search frame in video 1 found at frame number: {frame_number_video1}")

    # Step 3: If reverse search does not return to the
    # Check if the reverse search returns to the first frame of video 1
    if frame_number_video1 == 0:
        print("Reverse search successfully returned to the first frame of video 1. The match is confirmed.")
    else:
        print("Reverse search did not return to the first frame of video 1. Performing another reverse search in video 2.")
        # Perform a third search in video 2 using the first frame of video 1 again to confirm the match
        best_frame_video1 = reverse_search_best_frame_video1
        scaled_frame_video1 = scale_frame(best_frame_video1, scale_factor1)
        prev_frame_number_video2 = frame_number_video2
        frame_number_video2, best_frame_video2 = find_most_similar_frame(scaled_frame_video1, video2_path, scale_factor2, duration)
        print(f"Step 3: Third search in video 2 found a similar frame at frame number: {frame_number_video2}")
        if frame_number_video2 == prev_frame_number_video2:
            print("The third search confirmed the frame found in the first search.")
        else:
            print("The third search found a different frame. No matching frames found.")
            return
    
    print(f"Matching Frame Video 1: {frame_number_video1}, Time: {frame_number_video1/fps_video1:.6f} seconds")
    print(f"Matching Frame Video 2: {frame_number_video2}, Time: {frame_number_video2/fps_video2:.6f} seconds")
    display_matching_images(scale_frame(best_frame_video1, scale_factor1), scale_frame(best_frame_video2, scale_factor2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and display matching frames between two videos after adjusting their resolution.")
    parser.add_argument("video1_path", type=str, help="Path to the first video file.")
    parser.add_argument("video2_path", type=str, help="Path to the second video file.")
    parser.add_argument("--duration", type=float, default=10.0, help="Maximum duration (in seconds) to search for a match from the start of the second video.")

    args = parser.parse_args()

    main(args.video1_path, args.video2_path, args.duration)





