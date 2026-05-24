import time
import logging
import cv2
import numpy as np
from src.config import (
    MJPEG_TARGET_FPS,
    MJPEG_JPEG_QUALITY_DEFAULT,
    MJPEG_JPEG_QUALITY_MIN,
    MJPEG_JPEG_QUALITY_MAX,
)

logger = logging.getLogger(__name__)

class FrameEncoder:
    """Encodes raw video frames to JPEG format using OpenCV with optimization flags."""

    def __init__(self, default_quality: int | None = None) -> None:
        self.quality = default_quality if default_quality is not None else MJPEG_JPEG_QUALITY_DEFAULT

    def encode(self, frame: np.ndarray) -> bytes | None:
        """Encode a single raw NumPy array frame into JPEG bytes with optimization."""
        start_time = time.perf_counter()
        
        # Enforce quality bounds
        quality = max(MJPEG_JPEG_QUALITY_MIN, min(MJPEG_JPEG_QUALITY_MAX, self.quality))

        # cv2.IMWRITE_JPEG_OPTIMIZE enables entropy optimization.
        # cv2.IMWRITE_JPEG_PROGRESSIVE enables progressive JPEG rendering.
        params = [
            int(cv2.IMWRITE_JPEG_QUALITY), quality,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1
        ]
        
        try:
            encoded_ok, buffer = cv2.imencode(".jpg", frame, params)
        except Exception as e:
            logger.error("Error during JPEG encoding: %s", e)
            return None

        encode_duration_ms = (time.perf_counter() - start_time) * 1000.0
        
        if encode_duration_ms > 50.0:
            logger.warning(
                "Slow JPEG encoding: took %.2fms (quality: %d, size: %dx%d)",
                encode_duration_ms,
                quality,
                frame.shape[1],
                frame.shape[0]
            )
        else:
            logger.debug("Encoded frame in %.2fms", encode_duration_ms)

        if not encoded_ok or buffer is None:
            return None
            
        return buffer.tobytes()


class FrameRateManager:
    """Manages frame rate pacing and skip decisions to achieve stable frame rates."""

    def __init__(self, target_fps: int | None = None) -> None:
        self.target_fps = target_fps if target_fps is not None else MJPEG_TARGET_FPS
        self.interval = 1.0 / self.target_fps if self.target_fps > 0 else 1.0 / 15.0
        self.last_emitted_time = 0.0

    def should_emit(self) -> bool:
        """Determine if a frame should be emitted based on target FPS interval."""
        now = time.perf_counter()
        elapsed = now - self.last_emitted_time
        
        # Allow a small 2ms tolerance for OS scheduler jitter to stay within ±10ms target accuracy
        if elapsed >= (self.interval - 0.002):
            self.last_emitted_time = now
            return True
            
        return False
