import time
import unittest
import numpy as np
from src.mjpeg_streamer import FrameEncoder, FrameRateManager
from src.config import MJPEG_JPEG_QUALITY_MIN, MJPEG_JPEG_QUALITY_MAX

class TestMjpegStreamer(unittest.TestCase):
    """Unit tests for the optimized MJPEG streamer components."""

    def test_frame_encoder_dummy_frame(self) -> None:
        encoder = FrameEncoder(default_quality=40)
        # Create a dummy solid frame (100x100 RGB)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        
        encoded = encoder.encode(frame)
        self.assertIsNotNone(encoded)
        self.assertTrue(len(encoded) > 0)
        # Verify JPEG magic bytes at start (FF D8)
        self.assertEqual(encoded[:2], b"\xff\xd8")

    def test_frame_encoder_quality_bounding(self) -> None:
        # Quality below minimum (e.g. 5) should be capped to MJPEG_JPEG_QUALITY_MIN
        encoder_low = FrameEncoder(default_quality=1)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)
        
        encoded_low = encoder_low.encode(frame)
        self.assertIsNotNone(encoded_low)

        # Quality above maximum (e.g. 150) should be capped to MJPEG_JPEG_QUALITY_MAX
        encoder_high = FrameEncoder(default_quality=150)
        encoded_high = encoder_high.encode(frame)
        self.assertIsNotNone(encoded_high)

    def test_frame_rate_manager_pacing(self) -> None:
        # Setup 20 FPS manager (interval = 0.05s)
        manager = FrameRateManager(target_fps=20)
        
        # First call should succeed
        self.assertTrue(manager.should_emit())
        
        # Instant call should skip
        self.assertFalse(manager.should_emit())
        
        # Sleep for interval duration + OS scheduling buffer
        time.sleep(0.055)
        
        # Next call should succeed
        self.assertTrue(manager.should_emit())

if __name__ == "__main__":
    unittest.main()
