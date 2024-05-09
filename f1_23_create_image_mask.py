import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox

def initialize_mask(shape):
    """Initialize an empty mask without a border, matching the image shape."""
    h, w = shape[:2]
    return np.zeros((h, w), np.uint8)

def click_event(event, x, y, flags, param):
    global mask
    if event == cv2.EVENT_LBUTTONDOWN:
        # Use the blurred image for the flood fill operation
        blurred_image_for_floodfill = cv2.GaussianBlur(blurred_image, (5, 5), 0)

        # The color of the clicked point is used as a seed.
        seed_point = (x, y)
        
        # Define the maximum difference in color (in BGR space) to be included in the mask
        loDiff = (5, 5, 10, 0)
        upDiff = (5, 5, 10, 0)
        
        # Prepare a temporary mask for floodFill with an additional 1-pixel border
        h, w = blurred_image_for_floodfill.shape[:2]
        temp_mask = np.zeros((h + 2, w + 2), np.uint8)
        
        # Perform floodFill
        cv2.floodFill(blurred_image_for_floodfill, temp_mask, seed_point, (255, 0, 0), loDiff, upDiff, flags=cv2.FLOODFILL_MASK_ONLY)
        
        # Remove the 1-pixel border from the temp_mask and update the global mask
        temp_mask = temp_mask[1:-1, 1:-1]
        mask = np.maximum(mask, temp_mask)
        
        # Display the updated mask
        cv2.imshow("Mask", mask * 255)  # Multiply by 255 to make the mask clearly visible

def save_mask():
    global mask
    if mask is not None:
        save_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if save_path:
            # Ensure the mask is in the correct format (255 for white)
            final_mask = (mask * 255).astype(np.uint8)
            cv2.imwrite(save_path, final_mask)
            messagebox.showinfo("Save Mask", "The mask has been saved successfully!")
    else:
        messagebox.showinfo("Save Mask", "No mask to save.")

def create_mask_from_click(image_path):
    global image, blurred_image, mask
    image = cv2.imread(image_path)
    if image is None:
        print("Error loading image")
        return
    
    # Apply Gaussian blurring to the original image
    blurred_image = cv2.GaussianBlur(image, (5, 5), 0)
    
    # Initialize the mask to match the image dimensions
    mask = initialize_mask(image.shape)

    # Show the blurred image and set a mouse callback to capture clicks
    cv2.imshow('Blurred Image', blurred_image)
    cv2.setMouseCallback('Blurred Image', click_event)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # After closing the image window, ask the user if they want to save the mask
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    if messagebox.askyesno("Save Mask", "Do you want to save the mask?"):
        save_mask()

def select_image():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename()
    if file_path:
        create_mask_from_click(file_path)

if __name__ == "__main__":
    select_image()
