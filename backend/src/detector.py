"""
YOLO-based person detector.

Uses **Ultralytics YOLO26** for inference and converts results into
``supervision.Detections``.
"""

from __future__ import annotations

import logging

import numpy as np
import supervision as sv
import torch
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
        image_size: int | None = None,
    ) -> None:
        resolved_device = self._resolve_device(device)
        logger.info(
            "Loading YOLO model: %s (requested_device=%s, resolved_device=%s, imgsz=%s)",
            model_path,
            device or "auto",
            resolved_device,
            image_size if image_size else "auto",
        )
        self._model = YOLO(model_path)
        self._confidence = confidence
        self._device = resolved_device
        self._image_size = image_size if image_size and image_size > 0 else None
        logger.info(
            "Model loaded successfully (torch=%s, cuda_available=%s, cuda_runtime=%s, cuda_device=%s).",
            torch.__version__,
            torch.cuda.is_available(),
            torch.version.cuda,
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        )

    @staticmethod
    def _resolve_device(device: str) -> str:
        requested = (device or "auto").strip().lower()

        if requested in {"", "auto"}:
            if torch.cuda.is_available():
                return "cuda:0"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"

        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA device requested but torch.cuda.is_available() is False. "
                "Install CUDA-enabled PyTorch or use --device cpu."
            )

        if requested == "mps" and not (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        ):
            raise RuntimeError(
                "MPS device requested but it is not available in this environment."
            )

        return requested

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
            imgsz=self._image_size,
            classes=[PERSON_CLASS_ID],
            verbose=False,
        )[0]

        detections = sv.Detections.from_ultralytics(results)

        # Keep only "person" class (COCO id 0)
        person_mask = detections.class_id == PERSON_CLASS_ID
        detections = detections[person_mask]

        return detections  # type: ignore
