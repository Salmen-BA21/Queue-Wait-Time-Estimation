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
        self.root.geometry("700x650")
        self.root.resizable(True, True)

        # ── multi-video state ─────────────────────────────────
        self.video_count = tk.IntVar(value=1)
        self.video_count.trace_add("write", self._on_video_count_change)
        self.video_paths: list[str] = []
        self.current_video_index: int = 0
        self.zone_points_map: dict[str, list[list[int]]] = {}

        # tk helpers
        self.video_path = tk.StringVar()           # kept for compatibility
        self.video_selector_var = tk.StringVar()   # combobox in step 2
        self.video_listbox: tk.Listbox | None = None
        self.count_status_label: ttk.Label | None = None
        self.zone_status_label: ttk.Label | None = None

        # config state
        self.model_size = tk.StringVar(value="n")
        self.log_level = tk.StringVar(value="INFO")

        # RTSP credentials store: maps source url -> {"username", "password", "transport"}
        self.rtsp_credentials: dict[str, dict] = {}

        # RTSP form tk vars (populated in show_step1)
        self.rtsp_url_var = tk.StringVar()
        self.rtsp_user_var = tk.StringVar()
        self.rtsp_pass_var = tk.StringVar()
        self.rtsp_transport_var = tk.StringVar(value="tcp")
        self.rtsp_status_var = tk.StringVar(value="")

        # Metadata tracking variables
        self.establishment_var = tk.StringVar(value="")  # maps to establishment_id
        self.section_var = tk.StringVar(value="")  # maps to section_id
        self.employee_var = tk.StringVar(value="")  # maps to employee_id
        self.establishment_id: int | None = None
        self.section_id: int | None = None
        self.employee_id: int | None = None

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

        # Title
        ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                  font=("Arial", 16, "bold")).pack(pady=20)

        # Step indicator
        ttk.Label(self.root, text="Step 1 of 3: Select Videos",
                  font=("Arial", 12, "italic"), foreground="blue").pack(pady=10)

        # ── Number of videos ──────────────────────────────────
        count_frame = ttk.LabelFrame(self.root, text="Number of Videos", padding=10)
        count_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Label(count_frame, text="How many video feeds to analyse?",
                  font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Spinbox(count_frame, from_=1, to=10, textvariable=self.video_count,
                    width=5, font=("Arial", 10), justify=tk.CENTER).pack(side=tk.LEFT)

        # ── Video file picker ─────────────────────────────────
        video_frame = ttk.LabelFrame(self.root, text="Video Source(s)", padding=15)
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
        # configure column weights so URL entry stretches
        rtsp_tab.columnconfigure(1, weight=1)

        # Populate from existing selection (e.g. after Back navigation)
        self._refresh_listbox()

        # ── Metadata tracking ─────────────────────────────────────
        metadata_frame = ttk.LabelFrame(self.root, text="Job Information (Optional)", padding=15)
        metadata_frame.pack(fill=tk.X, padx=20, pady=10)

        # Establishment selector
        est_frame = ttk.Frame(metadata_frame)
        est_frame.pack(fill=tk.X, pady=5)
        ttk.Label(est_frame, text="Establishment:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        self.establishment_combo = ttk.Combobox(
            est_frame, textvariable=self.establishment_var, state="readonly",
            width=35, font=("Arial", 9)
        )
        self.establishment_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.establishment_combo.bind("<<ComboboxSelected>>", lambda _: self._on_establishment_select())
        ttk.Button(est_frame, text="+ New", command=self._create_new_establishment).pack(side=tk.LEFT)

        # Section selector
        sec_frame = ttk.Frame(metadata_frame)
        sec_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sec_frame, text="Section/Zone:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        self.section_combo = ttk.Combobox(
            sec_frame, textvariable=self.section_var, state="readonly",
            width=35, font=("Arial", 9)
        )
        self.section_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.section_combo.bind("<<ComboboxSelected>>", lambda _: self._on_section_select())
        ttk.Button(sec_frame, text="+ New", command=self._create_new_section).pack(side=tk.LEFT)

        # Employee selector
        emp_frame = ttk.Frame(metadata_frame)
        emp_frame.pack(fill=tk.X, pady=5)
        ttk.Label(emp_frame, text="Cashier/Employee:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        self.employee_combo = ttk.Combobox(
            emp_frame, textvariable=self.employee_var, state="readonly",
            width=35, font=("Arial", 9)
        )
        self.employee_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.employee_combo.bind("<<ComboboxSelected>>", lambda _: self._on_employee_select())
        ttk.Button(emp_frame, text="+ New", command=self._create_new_employee).pack(side=tk.LEFT)

        # Populate establishment dropdown
        self._refresh_establishment_combo()

        # ── Nav buttons ───────────────────────────────────────
        btn = ttk.Frame(self.root)
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

    # ── Metadata helpers ──────────────────────────────────────

    def _refresh_establishment_combo(self):
        """Populate establishment dropdown from database."""
        if not self.db_hierarchy:
            self.establishment_combo.config(values=[])
            return
        establishments = [f"{est['name']} (ID: {est_id})"
                         for est_id, est in self.db_hierarchy.items()]
        self.establishment_combo.config(values=establishments)

    def _on_establishment_select(self):
        """When establishment is selected, populate sections."""
        selection = self.establishment_var.get()
        if not selection:
            self.section_combo.config(values=[])
            self.employee_combo.config(values=[])
            self.establishment_id = None
            return

        # Extract ID from "Name (ID: 123)" format
        try:
            est_id = int(selection.split("ID: ")[1].rstrip(")"))
            self.establishment_id = est_id
        except (ValueError, IndexError):
            return

        # Load sections for this establishment
        est_data = self.db_hierarchy.get(est_id, {})
        sections_dict = est_data.get('sections', {})
        sections = [f"{sec['name']} (ID: {sec_id})"
                   for sec_id, sec in sections_dict.items()]
        self.section_combo.config(values=sections)
        self.section_var.set("")
        self.section_id = None
        self.employee_combo.config(values=[])
        self.employee_var.set("")
        self.employee_id = None

    def _on_section_select(self):
        """When section is selected, populate employees."""
        selection = self.section_var.get()
        if not selection or self.establishment_id is None:
            self.employee_combo.config(values=[])
            self.section_id = None
            return

        try:
            sec_id = int(selection.split("ID: ")[1].rstrip(")"))
            self.section_id = sec_id
        except (ValueError, IndexError):
            return

        # Load employees for this section
        est_data = self.db_hierarchy.get(self.establishment_id, {})
        sec_data = est_data.get('sections', {}).get(sec_id, {})
        employees_dict = sec_data.get('employees', {})
        employees = [f"{emp_name} (ID: {emp_id})"
                    for emp_id, emp_name in employees_dict.items()]
        self.employee_combo.config(values=employees)
        self.employee_var.set("")
        self.employee_id = None

    def _on_employee_select(self):
        """When employee is selected, store the ID."""
        selection = self.employee_var.get()
        if not selection:
            self.employee_id = None
            return

        try:
            emp_id = int(selection.split("ID: ")[1].rstrip(")"))
            self.employee_id = emp_id
        except (ValueError, IndexError):
            pass

    def _create_new_establishment(self):
        """Dialog to create a new establishment."""
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
                from src.database import create_establishment
                est_id = create_establishment(name)
                # Reload hierarchy
                from src.database import get_full_hierarchy
                self.db_hierarchy = get_full_hierarchy()
                self._refresh_establishment_combo()
                # Select the newly created establishment
                self.establishment_var.set(f"{name} (ID: {est_id})")
                self._on_establishment_select()
                dialog.destroy()
                messagebox.showinfo("Success", f"Created establishment: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create establishment:\n{e}")

        ttk.Button(dialog, text="Create", command=save_establishment).pack(side=tk.LEFT, padx=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_new_section(self):
        """Dialog to create a new section."""
        if self.establishment_id is None:
            messagebox.showwarning("Required", "Please select an establishment first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("New Section")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Section/Zone Name:", font=("Arial", 10)).pack(pady=10, padx=20)
        name_entry = ttk.Entry(dialog, font=("Arial", 10), width=35)
        name_entry.pack(pady=(0, 20), padx=20)
        name_entry.focus()

        def save_section():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Required", "Please enter a section name.")
                return
            try:
                from src.database import create_section
                sec_id = create_section(name, self.establishment_id)
                # Reload hierarchy
                from src.database import get_full_hierarchy
                self.db_hierarchy = get_full_hierarchy()
                self._on_establishment_select()  # Refresh section dropdown
                # Select the newly created section
                self.section_var.set(f"{name} (ID: {sec_id})")
                self._on_section_select()
                dialog.destroy()
                messagebox.showinfo("Success", f"Created section: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create section:\n{e}")

        ttk.Button(dialog, text="Create", command=save_section).pack(side=tk.LEFT, padx=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _create_new_employee(self):
        """Dialog to create a new employee."""
        if self.section_id is None:
            messagebox.showwarning("Required", "Please select a section first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("New Cashier/Employee")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Employee Name:", font=("Arial", 10)).pack(pady=10, padx=20)
        name_entry = ttk.Entry(dialog, font=("Arial", 10), width=35)
        name_entry.pack(pady=(0, 20), padx=20)
        name_entry.focus()

        def save_employee():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Required", "Please enter an employee name.")
                return
            try:
                from src.database import create_employee
                emp_id = create_employee(name, self.section_id)
                # Reload hierarchy
                from src.database import get_full_hierarchy
                self.db_hierarchy = get_full_hierarchy()
                self._on_section_select()  # Refresh employee dropdown
                # Select the newly created employee
                self.employee_var.set(f"{name} (ID: {emp_id})")
                self._on_employee_select()
                dialog.destroy()
                messagebox.showinfo("Success", f"Created employee: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create employee:\n{e}")

        ttk.Button(dialog, text="Create", command=save_employee).pack(side=tk.LEFT, padx=10)
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
        self.show_step2()

    # ══════════════════════════════════════════════════════════
    # Step 2 – Configure Model & Zone (per video)
    # ══════════════════════════════════════════════════════════

    def show_step2(self):
        """Step 2: model settings + zone for each video."""
        self._clear_window()

        ttk.Label(self.root, text="Queue Wait-Time Estimation System",
                  font=("Arial", 16, "bold")).pack(pady=15)

        ttk.Label(self.root, text="Step 2 of 3: Configure Model & Zone",
                  font=("Arial", 12, "italic"), foreground="blue").pack(pady=10)

        # ── Model configuration ───────────────────────────────
        model_frame = ttk.LabelFrame(self.root, text="Model Configuration", padding=10)
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

        # ── Zone selection (per video) ────────────────────────
        zone_frame = ttk.LabelFrame(self.root, text="Zone Selection (per video)", padding=10)
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

        # ── Nav buttons ───────────────────────────────────────
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

    # ══════════════════════════════════════════════════════════
    # Step 3 – Review & Run
    # ══════════════════════════════════════════════════════════

    def show_step3(self):
        """Step 3: summary of all videos + zones, then launch."""
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
            # Metadata arguments (optional)
            if self.establishment_id is not None:
                cmd.extend(["--establishment-id", str(self.establishment_id)])
            if self.section_id is not None:
                cmd.extend(["--section-id", str(self.section_id)])
            if self.employee_id is not None:
                cmd.extend(["--employee-id", str(self.employee_id)])
            commands.append(cmd)
        return commands

    def _run_analysis(self):
        """Spawn one analysis process per video in its own console."""
        try:
            cmds = self.get_analysis_commands()
            if not cmds:
                messagebox.showerror("Error", "No videos to analyse.")
                return
            started = 0
            for cmd in cmds:
                if sys.platform == "win32":
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(cmd)
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
