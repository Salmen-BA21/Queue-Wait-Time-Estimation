"""
GUI interface for queue estimation system.

Allows users to select one or more video sources, define per-video zones,
and run analysis – each video launches in its own terminal process.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

# Ensure the backend root is in sys.path so imports work from anywhere
_backend_root = Path(__file__).parent.parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

logger = logging.getLogger("queue_system.gui")


# ═══════════════════════════════════════════════════════════════
# Zone Selector
# ═══════════════════════════════════════════════════════════════

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

        # Store image references to prevent garbage collection
        self.pil_image = None
        self.photo = None
        self.photo_list: list = []

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

    # ── frame helpers ─────────────────────────────────────────

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
                cv2.putText(frame, str(i + 1), (pt[0] + 15, pt[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Draw lines
            if len(self.points) > 1:
                for i in range(len(self.points) - 1):
                    cv2.line(frame, tuple(self.points[i]), tuple(self.points[i + 1]),
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

            # Create PhotoImage and STORE as instance variables
            self.pil_image = Image.fromarray(frame_rgb)
            self.photo = ImageTk.PhotoImage(image=self.pil_image)
            self.photo_list = [self.photo, self.pil_image]

            # Display on canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.photo)

            self.update_info()
            print("[OK] Frame displayed successfully")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    # ── interaction ───────────────────────────────────────────

    def on_canvas_click(self, event):
        """Handle canvas click."""
        x = int((event.x - self.offset_x) / self.scale)
        y = int((event.y - self.offset_y) / self.scale)

        if 0 <= x < self.frame_w and 0 <= y < self.frame_h:
            self.points.append([x, y])
            self.display_frame()
        else:
            messagebox.showwarning("Out of bounds", "Click within the video frame!")

    def reset(self):
        """Reset polygon."""
        self.points = []
        self.display_frame()

    def update_info(self):
        """Update info label."""
        self.info_label.config(
            text=f"Points: {len(self.points)}/4 | Video: {self.frame_w}x{self.frame_h}")

    def confirm(self):
        """Confirm zone selection."""
        if len(self.points) < 3:
            messagebox.showwarning("Invalid", "Need at least 3 points!")
            return

        normalized = [[x / self.frame_w, y / self.frame_h] for x, y in self.points]
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
            self.root.wait_window()
        else:
            self.root.mainloop()
        return self.result


# ═══════════════════════════════════════════════════════════════
# Main Window – multi-video workflow
# ═══════════════════════════════════════════════════════════════

class MainWindow:
    """Main GUI application window with step-by-step workflow.

    Supports selecting *multiple* video files, configuring a zone for each,
    and launching one analysis process per video.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Queue Wait-Time Estimation System")
        self.root.geometry("700x900")
        self.root.resizable(True, True)

        # ── multi-video state ─────────────────────────────────
        self.video_count = tk.IntVar(value=1)
        self.video_count.trace_add("write", self._on_video_count_change)
        self.video_paths: list[str] = []
        self.current_video_index: int = 0
        self.zone_points_map: dict[str, list[list[int]]] = {}
        # Per-video job information: maps video path -> {"establishment_id", "caisse_id"}
        self.video_metadata_map: dict[str, dict[str, int | None]] = {}

        # tk helpers
        self.video_path = tk.StringVar()           # kept for compatibility
        self.video_selector_var = tk.StringVar()   # combobox in step 2
        self.video_listbox: tk.Listbox | None = None
        self.count_status_label: ttk.Label | None = None
        self.zone_status_label: ttk.Label | None = None

        # Per-video job info UI variables (used in Step 2)
        self.video_establishment_var = tk.StringVar(value="")
        self.video_caisse_var = tk.StringVar(value="")

        # config state
        self.model_size = tk.StringVar(value="n")
        self.log_level = tk.StringVar(value="INFO")
        self.webhook_enabled = tk.BooleanVar(value=True)

        # RTSP credentials store: maps source url -> {"username", "password", "transport"}
        self.rtsp_credentials: dict[str, dict] = {}

        # RTSP form tk vars (populated in show_step1)
        self.rtsp_url_var = tk.StringVar()
        self.rtsp_user_var = tk.StringVar()
        self.rtsp_pass_var = tk.StringVar()
        self.rtsp_transport_var = tk.StringVar(value="tcp")
        self.rtsp_status_var = tk.StringVar(value="")

        # Database hierarchy cache (will be populated on startup)
        self.db_hierarchy: dict = {}

        self._setup_ui()
        self._init_database()
        self.show_step1()

    # ── helpers ───────────────────────────────────────────────

    def _clear_window(self):
        """Remove all widgets so a new step can be drawn."""
        for w in self.root.winfo_children():
            w.destroy()

    def _setup_ui(self):
        """Reserved for future global UI setup."""
        pass

    def _create_scrollable_frame(self) -> tuple[tk.Canvas, ttk.Frame]:
        """Create a scrollable frame container.

        Returns:
            (canvas, content_frame) where content_frame is the frame to add widgets to
        """
        # Create outer frame to hold canvas and scrollbar
        outer_frame = ttk.Frame(self.root)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Create canvas and scrollbar
        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        # Bind canvas configuration to update scrollregion
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        # Create window in canvas
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return canvas, content_frame

    def _init_database(self):
        """Initialize metadata database on first run."""
        try:
            from src.database import init_db, get_full_hierarchy
            # Initialize database schema
            init_db()
            # Load hierarchy into memory for quick dropdown updates
            self.db_hierarchy = get_full_hierarchy()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize metadata database: {e}")
            messagebox.showerror("Database Error",
                f"Could not initialize database:\n{e}\n\n"
                "Metadata tracking will be skipped.")

    # ══════════════════════════════════════════════════════════
    # Step 1 – Select Videos
    # ══════════════════════════════════════════════════════════

    def show_step1(self):
        """Step 1: choose how many videos, then pick that many files."""
        self._clear_window()

        # Title (fixed at top)
        ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                  font=("Arial", 16, "bold")).pack(pady=20)

        # Step indicator (fixed at top)
        ttk.Label(self.root, text="Step 1 of 3: Select Videos",
                  font=("Arial", 12, "italic"), foreground="blue").pack(pady=10)

        # Create scrollable content area
        _, content_frame = self._create_scrollable_frame()

        # ── Number of videos ──────────────────────────────────
        count_frame = ttk.LabelFrame(content_frame, text="Number of Videos", padding=10)
        count_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Label(count_frame, text="How many video feeds to analyse?",
                  font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Spinbox(count_frame, from_=1, to=10, textvariable=self.video_count,
                    width=5, font=("Arial", 10), justify=tk.CENTER).pack(side=tk.LEFT)

        # ── Video file picker ─────────────────────────────────
        video_frame = ttk.LabelFrame(content_frame, text="Video Source(s)", padding=15)
        video_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Count status
        self.count_status_label = ttk.Label(video_frame, text="",
                                            font=("Arial", 10, "bold"))
        self.count_status_label.pack(anchor=tk.W, pady=(0, 5))

        # Listbox showing selected files
        lb_frame = ttk.Frame(video_frame)
        lb_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.video_listbox = tk.Listbox(lb_frame, font=("Arial", 10),
                                        selectmode=tk.SINGLE, height=6)
        lb_scroll = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL,
                                  command=self.video_listbox.yview)
        self.video_listbox.configure(yscrollcommand=lb_scroll.set)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scroll.pack(side=tk.LEFT, fill=tk.Y)

        # Add / Remove buttons + source-type tabs
        action_frame = ttk.Frame(video_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(action_frame, text="- Remove Selected",
                   command=self._remove_video).pack(side=tk.LEFT, padx=(0, 5))

        # ── Source-type notebook ───────────────────────────────
        notebook = ttk.Notebook(video_frame)
        notebook.pack(fill=tk.X, pady=(8, 0))

        # Tab 1 – Video File
        file_tab = ttk.Frame(notebook, padding=8)
        notebook.add(file_tab, text="  Video File  ")
        ttk.Label(file_tab, text="Supported: MP4, AVI, MOV",
                  font=("Arial", 9), foreground="gray").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(file_tab, text="+ Browse File",
                   command=self._add_video).pack(side=tk.LEFT)

        # Tab 2 – IP Camera (RTSP)
        rtsp_tab = ttk.Frame(notebook, padding=8)
        notebook.add(rtsp_tab, text="  IP Camera (RTSP)  ")

        r = 0
        ttk.Label(rtsp_tab, text="RTSP URL:", font=("Arial", 9)).grid(
            row=r, column=0, sticky=tk.W, padx=(0, 5), pady=3)
        ttk.Entry(rtsp_tab, textvariable=self.rtsp_url_var, width=45,
                  font=("Arial", 9)).grid(row=r, column=1, columnspan=3,
                                          sticky=tk.EW, pady=3)
        ttk.Label(rtsp_tab, text="e.g. rtsp://192.168.1.10:554/live/main",
                  font=("Arial", 8), foreground="gray").grid(
            row=r, column=4, sticky=tk.W, padx=(5, 0), pady=3)

        r += 1
        ttk.Label(rtsp_tab, text="Username:", font=("Arial", 9)).grid(
            row=r, column=0, sticky=tk.W, padx=(0, 5), pady=3)
        ttk.Entry(rtsp_tab, textvariable=self.rtsp_user_var, width=18,
                  font=("Arial", 9)).grid(row=r, column=1, sticky=tk.W, pady=3)
        ttk.Label(rtsp_tab, text="Password:", font=("Arial", 9)).grid(
            row=r, column=2, sticky=tk.W, padx=(10, 5), pady=3)
        ttk.Entry(rtsp_tab, textvariable=self.rtsp_pass_var, width=18,
                  show="*", font=("Arial", 9)).grid(row=r, column=3, sticky=tk.W, pady=3)

        r += 1
        ttk.Label(rtsp_tab, text="Transport:", font=("Arial", 9)).grid(
            row=r, column=0, sticky=tk.W, padx=(0, 5), pady=3)
        ttk.Combobox(rtsp_tab, textvariable=self.rtsp_transport_var,
                     values=["tcp", "udp"], state="readonly",
                     width=6, font=("Arial", 9)).grid(row=r, column=1, sticky=tk.W, pady=3)
        ttk.Label(rtsp_tab, text="(tcp = reliable,  udp = low-latency)",
                  font=("Arial", 8), foreground="gray").grid(
            row=r, column=2, columnspan=3, sticky=tk.W, padx=(10, 0), pady=3)

        r += 1
        btn_row = ttk.Frame(rtsp_tab)
        btn_row.grid(row=r, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))
        ttk.Button(btn_row, text="Test Connection",
                   command=self._test_rtsp_from_form).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="+ Add Camera",
                   command=self._add_camera_from_form).pack(side=tk.LEFT)

        self.rtsp_status_label = ttk.Label(rtsp_tab, textvariable=self.rtsp_status_var,
                                           font=("Arial", 9))
        self.rtsp_status_label.grid(row=r, column=0, columnspan=5,
                                    sticky=tk.W, pady=(3, 0))
        # Tab 3 – IP Camera Discovery
        onvif_tab = ttk.Frame(notebook, padding=8)
        notebook.add(onvif_tab, text="  IP Camera Discovery  ")

        # Discovery section
        discovery_frame = ttk.LabelFrame(onvif_tab, text="Network Discovery", padding=8)
        discovery_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(discovery_frame, text="Automatically find IP cameras on your network",
                  font=("Arial", 9), foreground="blue").pack(anchor=tk.W, pady=(0, 8))

        btn_frame = ttk.Frame(discovery_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="🔍 Discover Cameras",
                   command=self._discover_ip_cameras).pack(side=tk.LEFT, padx=(0, 8))
        self.onvif_status_var = tk.StringVar(value="")
        self.onvif_status_label = ttk.Label(btn_frame, textvariable=self.onvif_status_var,
                                           font=("Arial", 9))
        self.onvif_status_label.pack(side=tk.LEFT)

        # Results section
        results_frame = ttk.LabelFrame(onvif_tab, text="Discovered Cameras", padding=8)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Camera list
        list_frame = ttk.Frame(results_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.onvif_listbox = tk.Listbox(list_frame, height=6, font=("Arial", 9),
                                       yscrollcommand=scrollbar.set,
                                       selectmode=tk.MULTIPLE)
        self.onvif_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.onvif_listbox.yview)

        # Camera details
        self.onvif_details_text = tk.Text(results_frame, height=4, font=("Arial", 9),
                                         wrap=tk.WORD, state=tk.DISABLED)
        self.onvif_details_text.pack(fill=tk.X, pady=(8, 0))

        # Bind selection change to show details
        self.onvif_listbox.bind('<<ListboxSelect>>', self._on_ip_camera_selection_change)

        # Action buttons
        action_frame = ttk.Frame(onvif_tab)
        action_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(action_frame, text="Test Selected Camera",
                   command=self._test_selected_ip_camera).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(action_frame, text="+ Add Selected Cameras",
                   command=self._add_selected_ip_cameras).pack(side=tk.LEFT)

        # Store discovered cameras
        self.discovered_cameras: list[dict] = []

        # ── Nav buttons (fixed at bottom) ───────────────────────────────────
        btn = ttk.Frame(self.root)
        btn.pack(fill=tk.X, padx=20, pady=20)
        btn.pack(fill=tk.X, padx=20, pady=20)
        ttk.Button(btn, text="Next ->", command=self._validate_and_go_step2).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn, text="Exit", command=self.root.quit).pack(side=tk.LEFT, padx=5)

    # ── step-1 helpers ────────────────────────────────────────

    def _add_video(self):
        """Open a single-file dialog and append the result to the list."""
        expected = self.video_count.get()
        if len(self.video_paths) >= expected:
            messagebox.showwarning(
                "Limit reached",
                f"You already have {expected} video(s) selected.\n"
                "Remove one first or increase the count.",
            )
            return
        filename = filedialog.askopenfilename(
            title="Add Video File",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov"), ("All Files", "*.*")],
            initialdir="videos",
        )
        if filename and filename not in self.video_paths:
            self.video_paths.append(filename)
            self._refresh_listbox()

    def _remove_video(self):
        """Remove the currently-selected item from the list."""
        if self.video_listbox is None:
            return
        sel = self.video_listbox.curselection()
        if not sel:
            messagebox.showinfo("Remove", "Select a video in the list first.")
            return
        idx = sel[0]
        path = self.video_paths.pop(idx)
        self.zone_points_map.pop(path, None)
        self._refresh_listbox()

    def _refresh_listbox(self):
        """Sync the Listbox, count label and video_path var with video_paths."""
        if self.video_listbox is None:
            return
        self.video_listbox.delete(0, tk.END)
        for i, p in enumerate(self.video_paths):
            if p.lower().startswith("rtsp://"):
                label = f"{i+1}.  [CAM] {p}"
            else:
                label = f"{i+1}.  {Path(p).name}"
            self.video_listbox.insert(tk.END, label)
        # update count status label
        expected = self.video_count.get()
        n = len(self.video_paths)
        color = "green" if n == expected else ("orange" if n > 0 else "red")
        if self.count_status_label is not None:
            self.count_status_label.config(
                text=f"{n} of {expected} source(s) selected", foreground=color)
        # keep backward-compatible single-path var
        self.video_path.set(self.video_paths[0] if self.video_paths else "")

    def _on_video_count_change(self, *_args):
        """Clear previous selections when the count spinbox changes."""
        self.video_paths.clear()
        self.zone_points_map.clear()
        self.rtsp_credentials.clear()
        self.video_path.set("")
        self._refresh_listbox()

    def _add_camera_from_form(self):
        """Validate the RTSP form and add the camera URL to the source list."""
        expected = self.video_count.get()
        if len(self.video_paths) >= expected:
            messagebox.showwarning(
                "Limit reached",
                f"You already have {expected} source(s) selected.\n"
                "Remove one first or increase the count.",
            )
            return

        url = self.rtsp_url_var.get().strip()
        if not url:
            messagebox.showerror("Missing URL", "Please enter an RTSP URL.")
            return
        if not url.lower().startswith("rtsp://"):
            messagebox.showerror(
                "Invalid URL",
                "URL must start with rtsp://\n"
                "Example: rtsp://192.168.1.10:554/live/main",
            )
            return
        if url in self.video_paths:
            messagebox.showwarning("Duplicate", "This camera URL is already in the list.")
            return

        self.rtsp_credentials[url] = {
            "username": self.rtsp_user_var.get().strip() or None,
            "password": self.rtsp_pass_var.get().strip() or None,
            "transport": self.rtsp_transport_var.get() or "tcp",
        }
        self.video_paths.append(url)
        self._refresh_listbox()
        self.rtsp_status_var.set("")

    def _test_rtsp_from_form(self):
        """Test the RTSP URL entered in the form and show the result."""
        url = self.rtsp_url_var.get().strip()
        if not url:
            messagebox.showerror("Missing URL", "Please enter an RTSP URL first.")
            return
        if not url.lower().startswith("rtsp://"):
            messagebox.showerror(
                "Invalid URL",
                "URL must start with rtsp://\n"
                "Example: rtsp://192.168.1.10:554/live/main",
            )
            return

        self.rtsp_status_var.set("Testing connection…")
        if hasattr(self, "rtsp_status_label"):
            self.rtsp_status_label.config(foreground="blue")
        self.root.update_idletasks()

        try:
            from src.rtsp_camera import RTSPCamera
            ok, info = RTSPCamera.test_connection(
                url,
                username=self.rtsp_user_var.get().strip() or None,
                password=self.rtsp_pass_var.get().strip() or None,
                transport=self.rtsp_transport_var.get() or "tcp",
            )
        except Exception as exc:
            ok, info = False, {"error": str(exc)}

        if ok:
            msg = (
                f"Connection successful!\n\n"
                f"Resolution : {info['resolution']}\n"
                f"FPS        : {info['fps']:.1f}\n"
                f"Transport  : {info['transport']}"
            )
            self.rtsp_status_var.set(
                f"OK  {info['resolution']} @ {info['fps']:.1f} FPS"
            )
            if hasattr(self, "rtsp_status_label"):
                self.rtsp_status_label.config(foreground="green")
            messagebox.showinfo("RTSP Test – OK", msg)
        else:
            err = info.get("error", "Unknown error")
            self.rtsp_status_var.set(f"FAILED  {err}")
            if hasattr(self, "rtsp_status_label"):
                self.rtsp_status_label.config(foreground="red")
            messagebox.showerror("RTSP Test – Failed", f"Could not connect:\n\n{err}")

    # ── IP Camera discovery helpers ───────────────────────────────────────

    def _discover_ip_cameras(self):
        """Discover ONVIF cameras on the network."""
        self.onvif_status_var.set("🔍 Discovering cameras...")
        self.onvif_status_label.config(foreground="blue")
        self.onvif_listbox.delete(0, tk.END)
        self.onvif_details_text.config(state=tk.NORMAL)
        self.onvif_details_text.delete(1.0, tk.END)
        self.onvif_details_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

        try:
            from src.rtsp_camera import RTSPCamera

            # Discover cameras
            self.discovered_cameras = RTSPCamera.discover_onvif_devices(timeout=5.0)

            if not self.discovered_cameras:
                self.onvif_status_var.set("❌ No IP cameras found")
                self.onvif_status_label.config(foreground="red")
                messagebox.showinfo("Discovery Complete", "No IP cameras found on the network.\n\nPossible reasons:\n• No IP cameras connected\n• Cameras not ONVIF-compliant\n• Firewall blocking multicast traffic\n• Cameras on different subnet")
                return

            # Populate listbox
            for i, camera in enumerate(self.discovered_cameras):
                name = camera.get('name', 'Unknown')
                manufacturer = camera.get('manufacturer', 'Unknown')
                model = camera.get('model', 'Unknown')
                ip = camera.get('ip', 'Unknown')

                display_text = f"{name} - {manufacturer} {model} ({ip})"
                self.onvif_listbox.insert(tk.END, display_text)

            self.onvif_status_var.set(f"✅ Found {len(self.discovered_cameras)} camera(s)")
            self.onvif_status_label.config(foreground="green")

            messagebox.showinfo("Discovery Complete",
                              f"Found {len(self.discovered_cameras)} ONVIF camera(s)!\n\n"
                              "Select cameras from the list to view details and add them to your analysis.")

        except Exception as e:
            self.onvif_status_var.set("❌ Discovery failed")
            self.onvif_status_label.config(foreground="red")
            messagebox.showerror("Discovery Error", f"Failed to discover cameras:\n\n{str(e)}")

    def _on_ip_camera_selection_change(self, event):
        """Update camera details when selection changes."""
        selection = self.onvif_listbox.curselection()
        if not selection:
            self.onvif_details_text.config(state=tk.NORMAL)
            self.onvif_details_text.delete(1.0, tk.END)
            self.onvif_details_text.config(state=tk.DISABLED)
            return

        # Show details for first selected camera
        idx = selection[0]
        if idx < len(self.discovered_cameras):
            camera = self.discovered_cameras[idx]

            details = f"📹 Camera Details:\n\n"
            details += f"Name: {camera.get('name', 'Unknown')}\n"
            details += f"IP Address: {camera.get('ip', 'Unknown')}\n"
            details += f"Manufacturer: {camera.get('manufacturer', 'Unknown')}\n"
            details += f"Model: {camera.get('model', 'Unknown')}\n"
            details += f"Serial: {camera.get('serial', 'Unknown')}\n"
            details += f"Hardware: {camera.get('hardware', 'Unknown')}\n"
            details += f"Location: {camera.get('location', 'Unknown')}\n\n"

            if camera.get('services'):
                details += "🔗 Available Services:\n"
                for service, url in camera['services'].items():
                    details += f"• {service}: {url}\n"

            self.onvif_details_text.config(state=tk.NORMAL)
            self.onvif_details_text.delete(1.0, tk.END)
            self.onvif_details_text.insert(1.0, details)
            self.onvif_details_text.config(state=tk.DISABLED)

    def _test_selected_ip_camera(self):
        """Test connection to selected ONVIF camera."""
        selection = self.onvif_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a camera to test.")
            return

        idx = selection[0]
        if idx >= len(self.discovered_cameras):
            return

        camera = self.discovered_cameras[idx]

        # Ask for credentials
        cred_dialog = tk.Toplevel(self.root)
        cred_dialog.title("Camera Credentials")
        cred_dialog.geometry("350x200")
        cred_dialog.transient(self.root)
        cred_dialog.grab_set()

        ttk.Label(cred_dialog, text=f"Test connection to:\n{camera.get('name', 'Unknown')}",
                  font=("Arial", 10)).pack(pady=10)

        ttk.Label(cred_dialog, text="Username (optional):", font=("Arial", 9)).pack(anchor=tk.W, padx=20)
        username_var = tk.StringVar()
        ttk.Entry(cred_dialog, textvariable=username_var, font=("Arial", 9)).pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Label(cred_dialog, text="Password (optional):", font=("Arial", 9)).pack(anchor=tk.W, padx=20)
        password_var = tk.StringVar()
        ttk.Entry(cred_dialog, textvariable=password_var, show="*", font=("Arial", 9)).pack(fill=tk.X, padx=20, pady=(0, 15))

        test_result = {"success": False, "streams": []}

        def test_connection():
            try:
                from src.rtsp_camera import RTSPCamera

                username = username_var.get().strip() or None
                password = password_var.get().strip() or None

                # Get RTSP streams
                streams = RTSPCamera.get_rtsp_urls_from_onvif_device(
                    camera, username=username, password=password
                )

                if not streams:
                    test_result["success"] = False
                    test_result["error"] = "No RTSP streams found"
                    return

                # Test first stream
                ok, info = RTSPCamera.test_connection(
                    streams[0], username=username, password=password
                )

                test_result["success"] = ok
                test_result["streams"] = streams
                test_result["info"] = info

            except Exception as e:
                test_result["success"] = False
                test_result["error"] = str(e)

            cred_dialog.destroy()

        btn_frame = ttk.Frame(cred_dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(btn_frame, text="Test", command=test_connection).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=cred_dialog.destroy).pack(side=tk.RIGHT)

        cred_dialog.wait_window()

        # Show results
        if test_result["success"]:
            info = test_result["info"]
            streams = test_result["streams"]
            msg = (f"✅ Connection successful!\n\n"
                   f"Resolution: {info['resolution']}\n"
                   f"FPS: {info['fps']:.1f}\n"
                   f"Available streams: {len(streams)}\n\n"
                   f"First stream: {streams[0][:60]}...")
            messagebox.showinfo("Camera Test - Success", msg)
        else:
            error = test_result.get("error", "Unknown error")
            messagebox.showerror("Camera Test - Failed", f"Could not connect:\n\n{error}")

    def _add_selected_ip_cameras(self):
        """Add selected ONVIF cameras to the video sources list."""
        selection = self.onvif_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select cameras to add.")
            return

        expected = self.video_count.get()
        added_count = 0

        for idx in selection:
            if idx >= len(self.discovered_cameras):
                continue

            if len(self.video_paths) >= expected:
                messagebox.showwarning("Limit Reached",
                                     f"Cannot add more cameras. You have {expected} source(s) selected.\n"
                                     "Remove some sources first or increase the count.")
                break

            camera = self.discovered_cameras[idx]

            # Ask for credentials
            cred_dialog = tk.Toplevel(self.root)
            cred_dialog.title("Camera Credentials")
            cred_dialog.geometry("350x200")
            cred_dialog.transient(self.root)
            cred_dialog.grab_set()

            ttk.Label(cred_dialog, text=f"Add camera:\n{camera.get('name', 'Unknown')}",
                      font=("Arial", 10)).pack(pady=10)

            ttk.Label(cred_dialog, text="Username (optional):", font=("Arial", 9)).pack(anchor=tk.W, padx=20)
            username_var = tk.StringVar()
            ttk.Entry(cred_dialog, textvariable=username_var, font=("Arial", 9)).pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Label(cred_dialog, text="Password (optional):", font=("Arial", 9)).pack(anchor=tk.W, padx=20)
            password_var = tk.StringVar()
            ttk.Entry(cred_dialog, textvariable=password_var, show="*", font=("Arial", 9)).pack(fill=tk.X, padx=20, pady=(0, 15))

            credentials = {"username": None, "password": None, "rtsp_url": None}

            def add_camera():
                try:
                    from src.rtsp_camera import RTSPCamera

                    username = username_var.get().strip() or None
                    password = password_var.get().strip() or None

                    # Get RTSP streams
                    streams = RTSPCamera.get_rtsp_urls_from_onvif_device(
                        camera, username=username, password=password
                    )

                    if not streams:
                        messagebox.showerror("No Streams", "No RTSP streams found for this camera.")
                        return

                    # Use first stream
                    rtsp_url = streams[0]
                    credentials["username"] = username
                    credentials["password"] = password
                    credentials["rtsp_url"] = rtsp_url

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to get camera streams:\n\n{str(e)}")
                    return

                cred_dialog.destroy()

            btn_frame = ttk.Frame(cred_dialog)
            btn_frame.pack(fill=tk.X, padx=20, pady=10)
            ttk.Button(btn_frame, text="Add Camera", command=add_camera).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(btn_frame, text="Cancel", command=cred_dialog.destroy).pack(side=tk.RIGHT)

            cred_dialog.wait_window()

            # Add to video list if we got credentials
            if credentials["rtsp_url"]:
                rtsp_url = credentials["rtsp_url"]
                if rtsp_url not in self.video_paths:
                    self.rtsp_credentials[rtsp_url] = {
                        "username": credentials["username"],
                        "password": credentials["password"],
                        "transport": "tcp",  # Default to TCP for reliability
                    }
                    self.video_paths.append(rtsp_url)
                    added_count += 1
                else:
                    messagebox.showinfo("Duplicate", "This camera is already in the list.")

        if added_count > 0:
            self._refresh_listbox()
            messagebox.showinfo("Cameras Added", f"Successfully added {added_count} camera(s) to the analysis list!")

    # ── step-2 creation helpers ────────────────────────────────────────

    def _create_new_video_establishment(self):
        """Dialog to create a new establishment (for Step 2)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Establishment")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Establishment Name:", font=("Arial", 10)).pack(pady=10, padx=20)
        name_entry = ttk.Entry(dialog, font=("Arial", 10), width=35)
        name_entry.pack(pady=(0, 20), padx=20)
        name_entry.focus()

        def save_establishment():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Required", "Please enter an establishment name.")
                return
            try:
                from src.database import create_establishment, get_full_hierarchy
                est_id = create_establishment(name)
                # Reload hierarchy
                self.db_hierarchy = get_full_hierarchy()
                self._refresh_video_establishment_combo()
                # Select the newly created establishment
                self.video_establishment_var.set(f"{name} (ID: {est_id})")
                self._on_video_establishment_select()
                dialog.destroy()
                messagebox.showinfo("Success", f"Created establishment: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create establishment:\n{e}")

        ttk.Button(dialog, text="Create", command=save_establishment).pack(side=tk.LEFT, padx=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_new_video_caisse(self):
        """Dialog to create a new caisse (for Step 2)."""
        est_id = self._get_video_establishment_id()
        if est_id is None:
            messagebox.showwarning("Required", "Please select an establishment first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("New Caisse")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Caisse Number/Name:", font=("Arial", 10)).pack(pady=10, padx=20)
        name_entry = ttk.Entry(dialog, font=("Arial", 10), width=35)
        name_entry.pack(pady=(0, 20), padx=20)
        name_entry.focus()

        def save_caisse():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Required", "Please enter a caisse number or name.")
                return
            try:
                from src.database import create_caisse, get_full_hierarchy
                caisse_id = create_caisse(name, est_id)
                # Reload hierarchy
                self.db_hierarchy = get_full_hierarchy()
                self._refresh_video_caisse_combo(est_id)
                # Select the newly created caisse
                self.video_caisse_var.set(f"{name} (ID: {caisse_id})")
                self._on_video_caisse_select()
                dialog.destroy()
                messagebox.showinfo("Success", f"Created caisse: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create caisse:\n{e}")

        ttk.Button(dialog, text="Create", command=save_caisse).pack(side=tk.LEFT, padx=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _validate_and_go_step2(self):
        """Validate the video selection and advance to step 2."""
        expected = self.video_count.get()
        if not self.video_paths:
            messagebox.showerror("Error", "Please select your video file(s) or add a camera!")
            return
        if len(self.video_paths) != expected:
            messagebox.showerror(
                "Error",
                f"You need to select exactly {expected} source(s) "
                f"but {len(self.video_paths)} were chosen.",
            )
            return
        for p in self.video_paths:
            if not p.lower().startswith("rtsp://") and not Path(p).exists():
                messagebox.showerror("Error", f"File not found:\n{p}")
                return
        self.current_video_index = 0
        # Initialize metadata for each video if not already present
        for path in self.video_paths:
            if path not in self.video_metadata_map:
                self.video_metadata_map[path] = {
                    "establishment_id": None,
                    "caisse_id": None,
                }
        self.show_step2()

    # ══════════════════════════════════════════════════════════
    # Step 2 – Configure Model & Zone (per video)
    # ══════════════════════════════════════════════════════════

    def show_step2(self):
        """Step 2: model settings + zone for each video."""
        self._clear_window()

        # Title (fixed at top)
        ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                  font=("Arial", 16, "bold")).pack(pady=15)

        # Step indicator (fixed at top)
        ttk.Label(self.root, text="Step 2 of 3: Configure Model & Zone",
                  font=("Arial", 12, "italic"), foreground="blue").pack(pady=10)

        # Create scrollable content area
        _, content_frame = self._create_scrollable_frame()

        # ── Model configuration ───────────────────────────────
        model_frame = ttk.LabelFrame(content_frame, text="Model Configuration", padding=10)
        model_frame.pack(fill=tk.X, padx=15, pady=10)

        ttk.Label(model_frame, text="Model Size:", font=("Arial", 10)).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=8)
        ttk.Combobox(model_frame, textvariable=self.model_size,
                     values=["n (nano - fastest)", "s (small)", "m (medium)",
                             "l (large)", "x (x-large)"],
                     state="readonly", width=30, font=("Arial", 10)).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=8)

        ttk.Label(model_frame, text="Log Level:", font=("Arial", 10)).grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=8)
        ttk.Combobox(model_frame, textvariable=self.log_level,
                     values=["DEBUG", "INFO", "WARNING", "ERROR"],
                     state="readonly", width=30, font=("Arial", 10)).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=8)

        ttk.Checkbutton(
            model_frame,
            text="Send data to webhook (http://localhost:5678/webhook/queue-metrics)",
            variable=self.webhook_enabled,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=8)

        # ── Zone selection (per video) ────────────────────────
        zone_frame = ttk.LabelFrame(content_frame, text="Zone Selection (per video)", padding=10)
        zone_frame.pack(fill=tk.X, padx=15, pady=10)

        # Video selector when multiple files
        if len(self.video_paths) > 1:
            sel_frame = ttk.Frame(zone_frame)
            sel_frame.pack(fill=tk.X, padx=5, pady=5)

            ttk.Label(sel_frame, text="Current video:", font=("Arial", 10)).pack(side=tk.LEFT)
            combo_values = [f"{i+1}. {Path(p).name}" for i, p in enumerate(self.video_paths)]
            comb = ttk.Combobox(sel_frame, textvariable=self.video_selector_var,
                                values=combo_values, state="readonly",
                                width=45, font=("Arial", 10))
            comb.pack(side=tk.LEFT, padx=5)
            comb.bind("<<ComboboxSelected>>", lambda _: self._on_video_select())
            # default to first
            self.video_selector_var.set(combo_values[0])

        ttk.Label(zone_frame, text="Define the cashier area polygon:",
                  font=("Arial", 9), foreground="gray").pack(anchor=tk.W, padx=5, pady=5)

        self.zone_status_label = ttk.Label(zone_frame, text="", font=("Arial", 10))
        self.zone_status_label.pack(anchor=tk.W, padx=5, pady=5)
        self._update_zone_status()

        ttk.Button(zone_frame, text="Select Zone from Video",
                   command=self._select_zone).pack(anchor=tk.W, padx=5, pady=10)

        # ── Job Information (per video) ───────────────────────────
        job_frame = ttk.LabelFrame(content_frame, text="Job Information for This Video (Optional)", padding=10)
        job_frame.pack(fill=tk.X, padx=15, pady=10)

        # Establishment selector
        est_frame = ttk.Frame(job_frame)
        est_frame.pack(fill=tk.X, pady=5)
        ttk.Label(est_frame, text="Establishment:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        self.video_establishment_combo = ttk.Combobox(
            est_frame, textvariable=self.video_establishment_var, state="readonly",
            width=35, font=("Arial", 9)
        )
        self.video_establishment_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.video_establishment_combo.bind("<<ComboboxSelected>>", lambda _: self._on_video_establishment_select())
        ttk.Button(est_frame, text="+ New", command=self._create_new_video_establishment).pack(side=tk.LEFT)

        # Caisse selector
        caisse_frame = ttk.Frame(job_frame)
        caisse_frame.pack(fill=tk.X, pady=5)
        ttk.Label(caisse_frame, text="Caisse:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        self.video_caisse_combo = ttk.Combobox(
            caisse_frame, textvariable=self.video_caisse_var, state="readonly",
            width=35, font=("Arial", 9)
        )
        self.video_caisse_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.video_caisse_combo.bind("<<ComboboxSelected>>", lambda _: self._on_video_caisse_select())
        ttk.Button(caisse_frame, text="+ New", command=self._create_new_video_caisse).pack(side=tk.LEFT)

        # Load metadata for the current video
        self._load_video_metadata()

        # ── Nav buttons (fixed at bottom) ───────────────────────────────────
        btn = ttk.Frame(self.root)
        btn.pack(fill=tk.X, padx=15, pady=20)
        ttk.Button(btn, text="Next ->", command=self.show_step3).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn, text="<- Back", command=self.show_step1).pack(side=tk.RIGHT, padx=5)

    # ── step-2 helpers ────────────────────────────────────────

    def _on_video_select(self):
        """User picked a different video in the combobox."""
        label = self.video_selector_var.get()
        # label is "1. filename.mp4" -> extract index
        try:
            idx = int(label.split(".")[0]) - 1
        except (ValueError, IndexError):
            idx = 0
        self.current_video_index = max(0, min(idx, len(self.video_paths) - 1))
        self._update_zone_status()
        self._load_video_metadata()  # Load job info for this video

    def _select_zone(self):
        """Open zone selector for the currently-selected source."""
        if not self.video_paths:
            messagebox.showwarning("Warning", "Go back and select a source first!")
            return
        path = self.video_paths[self.current_video_index]

        # For RTSP sources, build the authenticated URL so cv2 can open it
        if path.lower().startswith("rtsp://"):
            creds = self.rtsp_credentials.get(path, {})
            from src.rtsp_camera import _build_rtsp_url, _apply_rtsp_env
            _apply_rtsp_env(creds.get("transport", "tcp"))
            display_path = _build_rtsp_url(
                path,
                username=creds.get("username"),
                password=creds.get("password"),
            )
        else:
            display_path = path

        selector = ZoneSelectorWindow(display_path, parent=self.root)
        result = selector.run()
        if result:
            self.zone_points_map[path] = result["pixel"]
            self._update_zone_status()

    def _update_zone_status(self):
        """Refresh the zone status label for the current video."""
        if self.zone_status_label is None:
            return
        if not self.video_paths:
            self.zone_status_label.config(text="Status: No video selected", foreground="red")
            return
        path = self.video_paths[self.current_video_index]
        name = Path(path).name
        if self.zone_points_map.get(path):
            n_pts = len(self.zone_points_map[path])
            self.zone_status_label.config(
                text=f"Zone defined for {name} ({n_pts} points)", foreground="green")
        else:
            self.zone_status_label.config(
                text=f"Not selected (optional) - {name}", foreground="orange")

    def _load_video_metadata(self):
        """Load job information for the current video."""
        if not self.video_paths:
            return
        path = self.video_paths[self.current_video_index]
        metadata = self.video_metadata_map.get(path, {})

        est_id = metadata.get("establishment_id")
        caisse_id = metadata.get("caisse_id")

        # Refresh combobox values
        self._refresh_video_establishment_combo()
        self._refresh_video_caisse_combo(est_id)

        # Set current selection
        if est_id:
            for item in self.video_establishment_combo["values"]:
                if f"(ID: {est_id})" in item:
                    self.video_establishment_var.set(item)
                    break
        else:
            self.video_establishment_var.set("")

        if caisse_id:
            for item in self.video_caisse_combo["values"]:
                if f"(ID: {caisse_id})" in item:
                    self.video_caisse_var.set(item)
                    break
        else:
            self.video_caisse_var.set("")

    def _refresh_video_establishment_combo(self):
        """Populate video establishment combobox."""
        if not self.db_hierarchy:
            self.video_establishment_combo["values"] = []
            return
        values = [f"{self.db_hierarchy[est_id]['name']} (ID: {est_id})"
                  for est_id in sorted(self.db_hierarchy.keys())]
        self.video_establishment_combo["values"] = values

    def _refresh_video_caisse_combo(self, est_id: int | None = None):
        """Populate video caisse combobox for the selected establishment."""
        if est_id is None:
            est_id = self._get_video_establishment_id()
        if not est_id or est_id not in self.db_hierarchy:
            self.video_caisse_combo["values"] = []
            return
        caisses = self.db_hierarchy[est_id]['caisses']
        values = [f"{caisses[caisse_id]['name']} (ID: {caisse_id})"
                  for caisse_id in sorted(caisses.keys())]
        self.video_caisse_combo["values"] = values

    def _get_video_establishment_id(self) -> int | None:
        """Extract establishment ID from current combobox selection."""
        text = self.video_establishment_var.get()
        if not text or "(ID: " not in text:
            return None
        try:
            return int(text.split("(ID: ")[1].rstrip(")"))
        except (ValueError, IndexError):
            return None

    def _get_video_caisse_id(self) -> int | None:
        """Extract caisse ID from current combobox selection."""
        text = self.video_caisse_var.get()
        if not text or "(ID: " not in text:
            return None
        try:
            return int(text.split("(ID: ")[1].rstrip(")"))
        except (ValueError, IndexError):
            return None

    def _on_video_establishment_select(self):
        """Handle video establishment selection."""
        self._save_current_video_metadata()
        est_id = self._get_video_establishment_id()
        self._refresh_video_caisse_combo(est_id)
        self.video_caisse_var.set("")

    def _on_video_caisse_select(self):
        """Handle video caisse selection."""
        self._save_current_video_metadata()

    def _save_current_video_metadata(self):
        """Save job information for the current video."""
        if not self.video_paths:
            return
        path = self.video_paths[self.current_video_index]
        self.video_metadata_map[path] = {
            "establishment_id": self._get_video_establishment_id(),
            "caisse_id": self._get_video_caisse_id(),
        }

    # ══════════════════════════════════════════════════════════
    # Step 3 – Review & Run
    # ══════════════════════════════════════════════════════════

    def show_step3(self):
        """Step 3: summary of all videos + zones, then launch."""
        # Save current video metadata before navigating away
        self._save_current_video_metadata()

        self._clear_window()

        ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                  font=("Arial", 16, "bold")).pack(pady=15)
        ttk.Label(self.root, text="Step 3 of 3: Review & Run",
                  font=("Arial", 12, "italic"), foreground="blue").pack(pady=10)

        # ── scrollable summary ────────────────────────────────
        outer = ttk.LabelFrame(self.root, text="Configuration Summary", padding=10)
        outer.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        summary_frame = ttk.Frame(canvas)

        summary_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=summary_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Per-video info
        for idx, path in enumerate(self.video_paths, start=1):
            is_rtsp = path.lower().startswith("rtsp://")
            kind = "Camera (RTSP)" if is_rtsp else "Video"
            ttk.Label(summary_frame, text=f"Source {idx}  [{kind}]:",
                      font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 2))
            ttk.Label(summary_frame, text=path,
                      font=("Arial", 9), foreground="darkgreen").pack(
                anchor=tk.W, padx=20, pady=(0, 2))

            if is_rtsp:
                creds = self.rtsp_credentials.get(path, {})
                user = creds.get("username") or "(none)"
                transport = creds.get("transport") or "tcp"
                ttk.Label(
                    summary_frame,
                    text=f"User: {user}   Transport: {transport}",
                    font=("Arial", 8), foreground="gray",
                ).pack(anchor=tk.W, padx=40, pady=(0, 2))

            points = self.zone_points_map.get(path)
            if points:
                txt = json.dumps(points)
                if len(txt) > 80:
                    txt = txt[:80] + "..."
                ttk.Label(summary_frame, text=f"Zone: {txt}",
                          font=("Arial", 8), foreground="darkgreen").pack(
                    anchor=tk.W, padx=40, pady=(0, 5))
            else:
                ttk.Label(summary_frame, text="Zone: full frame (none defined)",
                          font=("Arial", 9), foreground="orange").pack(
                    anchor=tk.W, padx=40, pady=(0, 5))

            # Per-video job information
            metadata = self.video_metadata_map.get(path, {})
            est_id = metadata.get("establishment_id")
            caisse_id = metadata.get("caisse_id")

            if est_id or caisse_id:
                if est_id:
                    est_name = self.db_hierarchy.get(est_id, {}).get('name', f"Unknown (ID: {est_id})")
                    ttk.Label(summary_frame, text=f"Establishment: {est_name}",
                              font=("Arial", 8), foreground="darkblue").pack(
                        anchor=tk.W, padx=40, pady=(0, 2))
                if caisse_id:
                    caisse_info = None
                    for est in self.db_hierarchy.values():
                        if caisse_id in est['caisses']:
                            caisse_info = est['caisses'][caisse_id]
                            break
                    caisse_name = caisse_info.get('name', f"Unknown (ID: {caisse_id})") if caisse_info else f"Unknown (ID: {caisse_id})"
                    ttk.Label(summary_frame, text=f"Caisse: {caisse_name}",
                              font=("Arial", 8), foreground="darkblue").pack(
                        anchor=tk.W, padx=40, pady=(0, 5))

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Model / log level
        ttk.Label(summary_frame, text="Model Size:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W, pady=(5, 2))
        ttk.Label(summary_frame, text=self.model_size.get(),
                  font=("Arial", 9), foreground="darkgreen").pack(
            anchor=tk.W, padx=20, pady=(0, 10))

        ttk.Label(summary_frame, text="Log Level:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W, pady=(5, 2))
        ttk.Label(summary_frame, text=self.log_level.get(),
                  font=("Arial", 9), foreground="darkgreen").pack(
            anchor=tk.W, padx=20, pady=(0, 10))

        ttk.Label(summary_frame, text="Webhook:", font=("Arial", 10, "bold")).pack(
            anchor=tk.W, pady=(5, 2))
        webhook_summary = (
            "Enabled: http://localhost:5678/webhook/queue-metrics"
            if self.webhook_enabled.get()
            else "Disabled"
        )
        ttk.Label(summary_frame, text=webhook_summary,
                  font=("Arial", 9), foreground="darkgreen" if self.webhook_enabled.get() else "gray").pack(
            anchor=tk.W, padx=20, pady=(0, 10))

        # ── Nav buttons ───────────────────────────────────────
        btn = ttk.Frame(self.root)
        btn.pack(fill=tk.X, padx=15, pady=15)
        ttk.Button(btn, text="Run Analysis", command=self._run_analysis).pack(
            side=tk.RIGHT, padx=5, ipady=5)
        ttk.Button(btn, text="<- Back", command=self.show_step2).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn, text="Exit", command=self.root.quit).pack(side=tk.LEFT, padx=5)

    # ══════════════════════════════════════════════════════════
    # Command construction & execution
    # ══════════════════════════════════════════════════════════

    def get_analysis_commands(self) -> list[list[str]]:
        """Build one subprocess arg-list per selected source.

        Each command invokes ``python -m src.main`` with the appropriate
        ``--source``, ``--model-size``, ``--log-level``, and (optionally)
        ``--zone-points`` flags.  RTSP sources also receive ``--rtsp-user``,
        ``--rtsp-pass``, and ``--rtsp-transport``.
        """
        model_size = self.model_size.get().split()[0]  # "n (nano ...)" -> "n"
        commands: list[list[str]] = []
        for path in self.video_paths:
            cmd = [
                sys.executable, "-m", "src.main",
                "--source", path,
                "--model-size", model_size,
                "--log-level", self.log_level.get(),
                "--resize-scale", "0.5",
            ]
            pts = self.zone_points_map.get(path)
            if pts:
                cmd.extend(["--zone-points", json.dumps(pts)])
            # RTSP-specific flags
            if path.lower().startswith("rtsp://"):
                creds = self.rtsp_credentials.get(path, {})
                if creds.get("username"):
                    cmd.extend(["--rtsp-user", creds["username"]])
                if creds.get("password"):
                    cmd.extend(["--rtsp-pass", creds["password"]])
                transport = creds.get("transport") or "tcp"
                cmd.extend(["--rtsp-transport", transport])
            # Per-video metadata arguments (optional)
            metadata = self.video_metadata_map.get(path, {})
            est_id = metadata.get("establishment_id")
            caisse_id = metadata.get("caisse_id")
            if est_id is not None:
                cmd.extend(["--establishment-id", str(est_id)])
            if caisse_id is not None:
                cmd.extend(["--caisse-id", str(caisse_id)])
            if not self.webhook_enabled.get():
                cmd.append("--disable-webhook")
            commands.append(cmd)
        return commands

    def _run_analysis(self):
        """Spawn one analysis process per video in its own console."""
        try:
            cmds = self.get_analysis_commands()
            if not cmds:
                messagebox.showerror("Error", "No videos to analyse.")
                return

            # Get the backend root directory for proper module imports
            backend_root = Path(__file__).parent.parent.parent

            started = 0
            for cmd in cmds:
                launch_cmd = cmd.copy()
                if sys.platform == "win32":
                    # Ensure Python uses unbuffered output for real-time logging
                    exe = launch_cmd[0].lower()
                    if exe.endswith("pythonw.exe"):
                        launch_cmd[0] = launch_cmd[0][:-11] + "python.exe"
                        exe = launch_cmd[0].lower()
                    if exe.endswith("python.exe") or exe.endswith("\\python"):
                        launch_cmd.insert(1, "-u")
                    subprocess.Popen(
                        launch_cmd,
                        shell=False,
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                        cwd=str(backend_root),
                        env=dict(os.environ),
                    )
                else:
                    subprocess.Popen(launch_cmd, cwd=str(backend_root), env=dict(os.environ))
                started += 1
            messagebox.showinfo(
                "Analysis Started",
                f"Launched {started} analysis process(es).\n"
                "Each video opens in its own console window.",
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to start analysis:\n{exc}")

    # ── lifecycle ─────────────────────────────────────────────

    def run(self):
        """Start the Tk main loop."""
        self.root.mainloop()


def main():
    """Entry point."""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
