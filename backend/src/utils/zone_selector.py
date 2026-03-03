"""
Zone selector utility – interactive polygon drawing for queue area definition.

This module provides tools to visually define custom queue zone polygons
by clicking on video frames.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("queue_system.zone_selector")


class InteractiveZoneSelector:
    """Interactive tool to define polygon zones by clicking on video frames.
    
    Parameters
    ----------
    video_path : str
        Path to the video file to use for zone definition.
    """
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.points: list[list[int]] = []
        self.frame: Optional[np.ndarray] = None
        self.frame_display: Optional[np.ndarray] = None
        self.frame_w = 0
        self.frame_h = 0
        
    def mouse_callback(self, event, x: int, y: int, flags, param):
        """Handle mouse clicks to define polygon vertices."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append([x, y])
            print(f"✓ Point {len(self.points)}: ({x}, {y})")
            self.draw_polygon()
            
    def draw_polygon(self):
        """Draw current polygon and points on frame."""
        if self.frame is None:
            return
            
        self.frame_display = self.frame.copy()
        
        # Draw points as circles
        for i, pt in enumerate(self.points):
            cv2.circle(self.frame_display, tuple(pt), 8, (0, 255, 0), -1)
            cv2.putText(
                self.frame_display,
                str(i + 1),
                (pt[0] + 15, pt[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        
        # Draw connecting lines
        if len(self.points) > 1:
            for i in range(len(self.points) - 1):
                cv2.line(
                    self.frame_display,
                    tuple(self.points[i]),
                    tuple(self.points[i + 1]),
                    (255, 255, 0),
                    2,
                )
            # Close polygon if we have 3+ points
            if len(self.points) > 2:
                cv2.line(
                    self.frame_display,
                    tuple(self.points[-1]),
                    tuple(self.points[0]),
                    (255, 255, 0),
                    2,
                )
        
        # Draw instruction text
        h, w = self.frame_display.shape[:2]
        cv2.putText(
            self.frame_display,
            f"Points: {len(self.points)} | [c]onfirm [r]eset [q]uit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        
        cv2.imshow("Zone Selector - Define Cashier Area", self.frame_display)
    
    def run(self) -> Optional[dict]:
        """Start interactive zone selection.
        
        Returns
        -------
        dict or None
            Dictionary with 'pixel' and 'normalized' coordinate lists,
            or None if cancelled.
        """
        cap = cv2.VideoCapture(self.video_path)
        ret, self.frame = cap.read()
        cap.release()
        
        if not ret:
            logger.error(f"Could not open video: {self.video_path}")
            print(f"❌ Error: Could not open video {self.video_path}")
            return None
        
        self.frame_h, self.frame_w = self.frame.shape[:2]
        
        print(f"\n{'='*60}")
        print(f"📍 Interactive Zone Selector")
        print(f"{'='*60}")
        print(f"Resolution: {self.frame_w}x{self.frame_h}")
        print(f"\nInstructions:")
        print(f"  • Left-click to add polygon vertices (at least 3)")
        print(f"  • 'c' - Confirm and save polygon")
        print(f"  • 'r' - Reset all points")
        print(f"  • 'q' - Cancel")
        print(f"{'='*60}\n")
        
        cv2.namedWindow("Zone Selector - Define Cashier Area")
        cv2.setMouseCallback(
            "Zone Selector - Define Cashier Area", self.mouse_callback
        )
        
        self.draw_polygon()
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('c'):  # Confirm
                if len(self.points) >= 3:
                    result = self._save_polygon()
                    cv2.destroyAllWindows()
                    return result
                else:
                    print("⚠️  Need at least 3 points to define a polygon!")
            
            elif key == ord('r'):  # Reset
                self.points = []
                self.draw_polygon()
                print("🔄 Polygon reset")
            
            elif key == ord('q'):  # Quit
                print("❌ Cancelled")
                cv2.destroyAllWindows()
                return None
    
    def _save_polygon(self) -> dict:
        """Save and display polygon coordinates."""
        # Normalize coordinates
        normalized = [
            [x / self.frame_w, y / self.frame_h] for x, y in self.points
        ]
        
        result = {
            "pixel": self.points,
            "normalized": normalized,
        }
        
        print(f"\n{'='*60}")
        print(f"✓ Polygon saved!")
        print(f"{'='*60}")
        print(f"\nPixel coordinates:")
        print(f"  {json.dumps(self.points)}")
        print(f"\nNormalized coordinates (0-1):")
        print(f"  {json.dumps(normalized)}")
        print(f"\n{'='*60}")
        print(f"Use with the main script:")
        print(f"{'='*60}")
        print(f"python -m src.main \\")
        print(f"  --source videos/retail_store.mp4 \\")
        print(f"  --zone-points '{json.dumps(self.points)}'")
        print(f"{'='*60}\n")
        
        return result


def select_zone(video_path: str) -> Optional[dict]:
    """Convenience function to select a zone interactively.
    
    Parameters
    ----------
    video_path : str
        Path to the video file.
    
    Returns
    -------
    dict or None
        Dictionary with 'pixel' and 'normalized' coordinates,
        or None if cancelled.
    
    Examples
    --------
    >>> coords = select_zone('videos/retail_store.mp4')
    >>> if coords:
    ...     print(coords['pixel'])
    """
    selector = InteractiveZoneSelector(video_path)
    return selector.run()
