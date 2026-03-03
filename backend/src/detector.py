"""
YOLO-based person detector.

Uses **Ultralytics YOLO26** for inference and converts results into
``supervision.Detections``.
"""

from __future__ import annotations

import logging

import numpy as np
import supervision as sv
from ultralytics import YOLO  # type: ignore

from src.config import PERSON_CLASS_ID

logger = logging.getLogger("queue_system.detector")


class PersonDetector:
    """Load a YOLO model and return person-only detections.

    Parameters
    ----------
    model_path : str
        YOLO weight file (e.g. ``yolo26n.pt``).  Downloaded automatically
        by Ultralytics on first use.
    confidence : float
        Minimum confidence threshold.
    device : str
        Inference device – ``"cuda"`` / ``"cpu"`` / ``"mps"``.
        Leave empty to let Ultralytics auto-detect.
    """

    def __init__(
        self,
        model_path: str = "yolo26n.pt",
        confidence: float = 0.35,
        device: str = "",
    ) -> None:
        logger.info("Loading YOLO model: %s (device=%s)", model_path, device or "auto")
        self._model = YOLO(model_path)
        self._confidence = confidence
        self._device = device or None
        logger.info("Model loaded successfully.")

    def detect(self, frame: np.ndarray) -> sv.Detections:
        """Run inference and return person-only ``sv.Detections``.

        Parameters
        ----------
        frame : np.ndarray
            BGR image from OpenCV.

        Returns
        -------
        sv.Detections
            Filtered detections (persons only).
        """
        results = self._model(
            frame,
            conf=self._confidence,
            device=self._device,
            verbose=False,
        )[0]

        detections = sv.Detections.from_ultralytics(results)

        # Keep only "person" class (COCO id 0)
        person_mask = detections.class_id == PERSON_CLASS_ID
        detections = detections[person_mask]

        return detections  # type: ignore
