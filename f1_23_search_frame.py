import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, Label

import cv2
from PIL import Image, ImageTk

class VideoFrameExtractor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Frame Extractor")

        self.vid_cap = None
        self.current_frame = None
        self.total_frames = 0
        self.current_image = None
        self.display_image = None
        self.fps = 0  # Frames per second of the video

        self.canvas = tk.Canvas(self)
        self.canvas.pack()

        btn_load_video = tk.Button(self, text="Load Video", command=self.load_video)
        btn_load_video.pack(side=tk.LEFT)

        btn_prev_frame = tk.Button(self, text="<< Prev Frame", command=self.prev_frame)
        btn_prev_frame.pack(side=tk.LEFT)

        btn_next_frame = tk.Button(self, text="Next Frame >>", command=self.next_frame)
        btn_next_frame.pack(side=tk.LEFT)

        btn_jump_frame = tk.Button(self, text="Jump to Frame", command=self.jump_to_frame)
        btn_jump_frame.pack(side=tk.LEFT)

        btn_save_frame = tk.Button(self, text="Save Frame", command=self.save_frame)
        btn_save_frame.pack(side=tk.RIGHT)

        # Label to display the current frame and time
        self.status_label = Label(self, text="Frame: 0 Time: 0s")
        self.status_label.pack(side=tk.BOTTOM)

    def update_status(self):
        if self.vid_cap is not None:
            time = self.current_frame / self.fps
            self.status_label.config(text=f"Frame: {self.current_frame} Time: {time:.6f}s")

    def load_video(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.vid_cap = cv2.VideoCapture(file_path)
            self.total_frames = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.vid_cap.get(cv2.CAP_PROP_FPS)
            self.current_frame = 0

            self.width = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH) // 2)
            self.height = int(self.vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) // 2)

            self.geometry(f"{self.width}x{self.height+100}")
            self.canvas.config(width=self.width, height=self.height)

            self.show_frame()

    def show_frame(self):
        if self.vid_cap is not None:
            self.vid_cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            ret, frame = self.vid_cap.read()
            if ret:
                self.current_image = frame

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

    def jump_to_frame(self):
        frame_number = simpledialog.askinteger("Jump to Frame", "Enter frame number:", parent=self)
        if frame_number is not None and 0 <= frame_number < self.total_frames:
            self.current_frame = frame_number
            self.show_frame()
        else:
            tk.messagebox.showerror("Error", "Invalid frame number.")

    def save_frame(self):
        if self.current_image is not None:
            image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            file_path = filedialog.asksaveasfilename(defaultextension=".jpg")
            if file_path:
                image.save(file_path)

if __name__ == "__main__":
    app = VideoFrameExtractor()
    app.mainloop()

