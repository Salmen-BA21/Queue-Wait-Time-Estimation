"""
GUI interface for queue estimation system.

Allows users to select video source, define zones, and run analysis
without using the terminal.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

logger = logging.getLogger("queue_system.gui")


class ZoneSelectorWindow:
    """Interactive zone selection window."""
    
    def __init__(self, video_path: str, parent: tk.Tk | tk.Toplevel | None = None):
        self.video_path = video_path
        # Explicit Tk/Toplevel typing avoids wm_transient type errors in Pylance
        self.parent: tk.Tk | tk.Toplevel | None = parent
        self.points: list[list[int]] = []
        self.frame_original = None
        self.frame_w = 0
        self.frame_h = 0
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # Store image references as instance variables to prevent garbage collection
        self.pil_image = None
        self.photo = None
        self.photo_list = []  # Keep all images alive
        
        # Setup window (Toplevel when embedded in main GUI, standalone Tk otherwise)
        if parent is not None:
            self.root = tk.Toplevel(parent)
            self.root.transient(parent)
            self.root.grab_set()  # modal behavior
        else:
            self.root = tk.Tk()
        
        self.root.title("Queue System - Zone Selector")
        self.root.geometry("1000x700")
        
        # Video canvas
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Controls frame
        controls = ttk.Frame(self.root)
        controls.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(controls, text="Click to define cashier zone (min 3 points)", 
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(controls, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="Confirm", command=self.confirm).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=2)
        
        # Info label
        self.info_label = ttk.Label(controls, text="", font=("Arial", 9), foreground="blue")
        self.info_label.pack(side=tk.RIGHT, padx=5)
        
        self.result = None
        self.load_and_display_frame()
        
    def load_and_display_frame(self):
        """Load first frame of video and display it."""
        print(f"Loading video: {self.video_path}")
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            messagebox.showerror("Error", f"Could not open video: {self.video_path}")
            self.root.destroy()
            return
        
        print(f"Frame loaded: {frame.shape}")
        self.frame_original = frame
        self.frame_h, self.frame_w = frame.shape[:2]
        print(f"Frame dimensions: {self.frame_w}x{self.frame_h}")
        
        # Show window first
        self.root.deiconify()
        self.root.update()
        self.root.update_idletasks()
        
        # Schedule display after window is fully initialized
        self.root.after(300, self.display_frame)
        
    def display_frame(self):
        """Display frame with points and polygon."""
        if self.frame_original is None:
            self.root.after(100, self.display_frame)
            return
        
        try:
            frame = self.frame_original.copy()
            
            # Draw points
            for i, pt in enumerate(self.points):
                cv2.circle(frame, tuple(pt), 8, (0, 255, 0), -1)
                cv2.putText(frame, str(i+1), (pt[0]+15, pt[1]+5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Draw lines
            if len(self.points) > 1:
                for i in range(len(self.points) - 1):
                    cv2.line(frame, tuple(self.points[i]), tuple(self.points[i+1]),
                            (255, 255, 0), 2)
                if len(self.points) > 2:
                    cv2.line(frame, tuple(self.points[-1]), tuple(self.points[0]),
                            (255, 255, 0), 2)
            
            # Get canvas dimensions
            self.canvas.update_idletasks()
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w < 100 or canvas_h < 100:
                self.root.after(150, self.display_frame)
                return
            
            # Resize frame to fit canvas
            self.scale = min(canvas_w / self.frame_w, canvas_h / self.frame_h)
            new_w = int(self.frame_w * self.scale)
            new_h = int(self.frame_h * self.scale)
            
            frame_resized = cv2.resize(frame, (new_w, new_h))
            
            # Center the image
            self.offset_x = (canvas_w - new_w) / 2
            self.offset_y = (canvas_h - new_h) / 2
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            
            # Create PhotoImage and STORE as instance variables to prevent garbage collection
            self.pil_image = Image.fromarray(frame_rgb)
            self.photo = ImageTk.PhotoImage(image=self.pil_image)
            
            # Also keep in list for redundancy
            self.photo_list = [self.photo, self.pil_image]
            
            # Display on canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w//2, canvas_h//2, image=self.photo)
            
            self.update_info()
            print("[OK] Frame displayed successfully")
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        
    def on_canvas_click(self, event):
        """Handle canvas click."""
        # Convert canvas coordinates to frame coordinates
        x = int((event.x - self.offset_x) / self.scale)
        y = int((event.y - self.offset_y) / self.scale)
        
        # Validate bounds
        if 0 <= x < self.frame_w and 0 <= y < self.frame_h:
            self.points.append([x, y])
            self.display_frame()
        else:
            messagebox.showwarning("Out of bounds", f"Click within the video frame!")
    
    def reset(self):
        """Reset polygon."""
        self.points = []
        self.display_frame()
    
    def update_info(self):
        """Update info label."""
        self.info_label.config(text=f"Points: {len(self.points)}/4 | Video: {self.frame_w}x{self.frame_h}")
    
    def confirm(self):
        """Confirm zone selection."""
        if len(self.points) < 3:
            messagebox.showwarning("Invalid", "Need at least 3 points!")
            return
        
        normalized = [[x/self.frame_w, y/self.frame_h] for x, y in self.points]
        self.result = {
            "pixel": self.points,
            "normalized": normalized,
        }
        self.root.destroy()
    
    def cancel(self):
        """Cancel selection."""
        self.result = None
        self.root.destroy()
    
    def run(self):
        """Show window and return result."""
        if self.parent is not None:
            # Parent mainloop already running; wait for this window
            self.root.wait_window()
        else:
            self.root.mainloop()
        return self.result


class MainWindow:
    """Main GUI application window with step-by-step workflow."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Queue Wait-Time Estimation System")
        self.root.geometry("700x600")
        self.root.resizable(True, False)
        
        self.video_path = tk.StringVar()
        self.model_size = tk.StringVar(value="n")
        self.zone_points = tk.StringVar(value="None")
        self.log_level = tk.StringVar(value="INFO")
        
        self.setup_ui()
        self.show_step1()
        
    def clear_window(self):
        """Clear all widgets from window."""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def setup_ui(self):
        """Create UI elements (but hidden initially)."""
        pass
    
    def show_step1(self):
        """Step 1: Select Video File."""
        self.clear_window()
        
        # Title
        title = ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                         font=("Arial", 16, "bold"))
        title.pack(pady=20)
        
        # Step indicator
        step = ttk.Label(self.root, text="Step 1 of 3: Select Video",
                        font=("Arial", 12, "italic"), foreground="blue")
        step.pack(pady=10)
        
        # Video frame
        video_frame = ttk.LabelFrame(self.root, text="Video Source", padding=15)
        video_frame.pack(fill=tk.X, padx=20, pady=15)
        
        ttk.Label(video_frame, text="Video File:", font=("Arial", 10)).pack(anchor=tk.W, pady=5)
        
        file_frame = ttk.Frame(video_frame)
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Entry(file_frame, textvariable=self.video_path, width=50, font=("Arial", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(file_frame, text="Browse", command=self.browse_video).pack(side=tk.LEFT, padx=2)
        
        # Info
        info = ttk.Label(video_frame, text="Select a video file (MP4, AVI, MOV)",
                        font=("Arial", 9), foreground="gray")
        info.pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ttk.Button(button_frame, text="Next →", command=self.validate_and_go_step2).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.LEFT, padx=5)
    
    def show_step2(self):
        """Step 2: Model Configuration & Zone Selection."""
        self.clear_window()
        
        # Title
        title = ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                         font=("Arial", 16, "bold"))
        title.pack(pady=15)
        
        # Step indicator
        step = ttk.Label(self.root, text="Step 2 of 3: Configure Model & Zone",
                        font=("Arial", 12, "italic"), foreground="blue")
        step.pack(pady=10)
        
        # Model section
        model_frame = ttk.LabelFrame(self.root, text="Model Configuration", padding=10)
        model_frame.pack(fill=tk.X, padx=15, pady=10)
        
        ttk.Label(model_frame, text="Model Size:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=8)
        ttk.Combobox(model_frame, textvariable=self.model_size,
                    values=["n (nano - fastest)", "s (small)", "m (medium)", "l (large)", "x (x-large)"],
                    state="readonly", width=30, font=("Arial", 10)).grid(row=0, column=1, sticky=tk.W, padx=5, pady=8)
        
        ttk.Label(model_frame, text="Log Level:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=8)
        ttk.Combobox(model_frame, textvariable=self.log_level,
                    values=["DEBUG", "INFO", "WARNING", "ERROR"], state="readonly", width=30, font=("Arial", 10)).grid(row=1, column=1, sticky=tk.W, padx=5, pady=8)
        
        # Zone section
        zone_frame = ttk.LabelFrame(self.root, text="Zone Selection", padding=10)
        zone_frame.pack(fill=tk.X, padx=15, pady=10)
        
        zone_info = ttk.Label(zone_frame, text="Define the cashier area polygon:",
                             font=("Arial", 9), foreground="gray")
        zone_info.pack(anchor=tk.W, padx=5, pady=5)
        
        zone_status = ttk.Label(zone_frame, text="Status: Not selected",
                               font=("Arial", 10), foreground="red")
        zone_status.pack(anchor=tk.W, padx=5, pady=5)
        self.zone_status_label = zone_status
        self.update_zone_status()
        
        ttk.Button(zone_frame, text="Select Zone from Video", 
                  command=lambda: self.select_zone()).pack(anchor=tk.W, padx=5, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=15, pady=20)
        
        ttk.Button(button_frame, text="Next →", command=self.show_step3).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="← Back", command=self.show_step1).pack(side=tk.RIGHT, padx=5)
    
    def show_step3(self):
        """Step 3: Review & Run Analysis."""
        self.clear_window()
        
        # Title
        title = ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                         font=("Arial", 16, "bold"))
        title.pack(pady=15)
        
        # Step indicator
        step = ttk.Label(self.root, text="Step 3 of 3: Review & Run",
                        font=("Arial", 12, "italic"), foreground="blue")
        step.pack(pady=10)
        
        # Summary frame
        summary_frame = ttk.LabelFrame(self.root, text="Configuration Summary", padding=15)
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Video info
        ttk.Label(summary_frame, text="Video File:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 2))
        ttk.Label(summary_frame, text=self.video_path.get(), 
                 font=("Arial", 9), foreground="darkgreen").pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Model info
        ttk.Label(summary_frame, text="Model Size:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 2))
        ttk.Label(summary_frame, text=self.model_size.get(), 
                 font=("Arial", 9), foreground="darkgreen").pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Log level info
        ttk.Label(summary_frame, text="Log Level:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 2))
        ttk.Label(summary_frame, text=self.log_level.get(), 
                 font=("Arial", 9), foreground="darkgreen").pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Zone info
        ttk.Label(summary_frame, text="Zone Status:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 2))
        zone_text = self.zone_points.get()
        if zone_text and zone_text != "None":
            zone_display = zone_text[:80] + "..." if len(zone_text) > 80 else zone_text
            ttk.Label(summary_frame, text=zone_display, 
                     font=("Arial", 8), foreground="darkgreen").pack(anchor=tk.W, padx=20, pady=(0, 10))
        else:
            ttk.Label(summary_frame, text="Full frame (no zone defined)", 
                     font=("Arial", 9), foreground="orange").pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Button(button_frame, text="Run Analysis", command=self.run_analysis).pack(side=tk.RIGHT, padx=5, ipady=5)
        ttk.Button(button_frame, text="← Back", command=self.show_step2).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.LEFT, padx=5)
    
    def validate_and_go_step2(self):
        """Validate video selection and go to step 2."""
        if not self.video_path.get():
            messagebox.showerror("Error", "Please select a video file!")
            return
        
        # Check if file exists
        if not Path(self.video_path.get()).exists():
            messagebox.showerror("Error", f"File not found: {self.video_path.get()}")
            return
        
        self.show_step2()
    
    def browse_video(self):
        """Browse and select video file."""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov"), ("All Files", "*.*")],
            initialdir="videos"
        )
        if filename:
            self.video_path.set(filename)
    
    def select_zone(self):
        """Open zone selector window."""
        if not self.video_path.get():
            messagebox.showwarning("Warning", "Please go back and select a video first!")
            return
        
        selector = ZoneSelectorWindow(self.video_path.get(), parent=self.root)
        result = selector.run()
        
        if result:
            self.zone_points.set(json.dumps(result["pixel"]))
            self.update_zone_status()
    
    def update_zone_status(self):
        """Update zone status label."""
        if hasattr(self, 'zone_status_label'):
            zone_str = self.zone_points.get().strip()
            if zone_str and zone_str != "None":
                self.zone_status_label.config(text="Status: Zone defined ✓", foreground="green")
            else:
                self.zone_status_label.config(text="Status: Not selected (optional)", foreground="orange")
    
    def run_analysis(self):
        """Run the main analysis script."""
        try:
            # Build command
            model_size = self.model_size.get().split()[0]  # Extract just the letter
            cmd = [
                sys.executable, "-m", "src.main",
                "--source", self.video_path.get(),
                "--model-size", model_size,
                "--log-level", self.log_level.get(),
            ]
            
            # Add zone points if specified
            zone_str = self.zone_points.get().strip()
            if zone_str and zone_str != "None":
                cmd.extend(["--zone-points", zone_str])
            
            messagebox.showinfo("Starting Analysis", "Analysis starting... Check the video window.")
            
            # Run in new window
            if sys.platform == "win32":
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(cmd)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start analysis:\n{str(e)}")
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point."""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
