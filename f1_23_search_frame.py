import tkinter as tk
from tkinter import messagebox, Label, filedialog
import cv2
from PIL import Image, ImageTk
import sys

class VideoFrameExtractor(tk.Tk):
    def __init__(self, file_path):
        super().__init__()
        self.title("Frame Extractor")

        self.vid_cap = None
        self.current_frame = None
        self.total_frames = 0
        self.current_image = None
        self.display_image = None
        self.fps = 0  # Frames per second of the video

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

        btn_save_frame = tk.Button(control_frame, text="Save Frame", command=self.save_frame)
        btn_save_frame.pack(side=tk.RIGHT)

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

        # Set the width to 1280 pixels and calculate the height to maintain 16:9 aspect ratio
        self.width = 960
        self.height = int(self.width * 9 / 16)

        self.geometry(f"{self.width}x{self.height+100}")
        self.canvas.config(width=self.width, height=self.height)

        self.show_frame()

    def show_frame(self):
        if self.vid_cap is not None:
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            ret, frame = self.vid_cap.read()
            if ret:
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

    def on_resize(self, event):
        if self.vid_cap is not None and event.width > 1 and event.height > 1:
            # Maintain 16:9 aspect ratio
            new_width = event.width
            new_height = int(new_width * 9 / 16)
            
            if new_height > event.height - 100:
                new_height = event.height - 100
                new_width = int(new_height * 16 / 9)
            
            self.width = new_width
            self.height = new_height
            self.canvas.config(width=self.width, height=self.height)
            self.show_frame()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <video_file_path>")
        sys.exit(1)

    video_file_path = sys.argv[1]
    app = VideoFrameExtractor(video_file_path)
    app.mainloop()

