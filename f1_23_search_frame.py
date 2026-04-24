import tkinter as tk
from tkinter import messagebox, Label, filedialog
import cv2
from PIL import Image, ImageTk
import sys
import os
import numpy as np

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

        self.geometry(f"{self.width}x{self.height+100}")
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

