import tkinter as tk
from tkinter import filedialog
import cv2
from PIL import Image, ImageTk

class VideoFrameExtractor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Frame Extractor")

        self.vid_cap = None
        self.current_frame = None  # To keep track of the current frame index
        self.total_frames = 0  # Total number of frames in the video
        self.current_image = None  # Full resolution image
        self.display_image = None  # Display image

        self.canvas = tk.Canvas(self)
        self.canvas.pack()

        btn_load_video = tk.Button(self, text="Load Video", command=self.load_video)
        btn_load_video.pack(side=tk.LEFT)

        btn_prev_frame = tk.Button(self, text="<< Prev Frame", command=self.prev_frame)
        btn_prev_frame.pack(side=tk.LEFT)

        btn_next_frame = tk.Button(self, text="Next Frame >>", command=self.next_frame)
        btn_next_frame.pack(side=tk.LEFT)

        btn_save_frame = tk.Button(self, text="Save Frame", command=self.save_frame)
        btn_save_frame.pack(side=tk.RIGHT)

    def load_video(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.vid_cap = cv2.VideoCapture(file_path)
            self.total_frames = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.current_frame = 0

            # Get video resolution and calculate half size for display
            self.width = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH) // 2)
            self.height = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) // 2)

            # Adjust the window and canvas size to match half the video size for display
            self.geometry(f"{self.width}x{self.height+100}")  # Adding extra height for buttons
            self.canvas.config(width=self.width, height=self.height)

            self.show_frame()

    def show_frame(self):
        if self.vid_cap is not None:
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            ret, frame = self.vid_cap.read()
            if ret:
                self.current_image = frame  # Keep the full resolution frame for saving

                # Resize the frame for display purposes
                display_frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                self.display_image = Image.fromarray(display_frame)
                self.photo = ImageTk.PhotoImage(image=self.display_image)
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

    def next_frame(self):
        if self.vid_cap is not None and self.current_frame < self.total_frames - 1:
            self.current_frame += 1
            self.show_frame()

    def prev_frame(self):
        if self.vid_cap is not None and self.current_frame > 0:
            self.current_frame -= 1
            self.show_frame()

    def save_frame(self):
        if self.current_image is not None:
            # Convert the full resolution frame for saving
            image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            file_path = filedialog.asksaveasfilename(defaultextension=".jpg")
            if file_path:
                image.save(file_path)

if __name__ == "__main__":
    app = VideoFrameExtractor()
    app.mainloop()
