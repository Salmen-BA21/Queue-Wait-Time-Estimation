"""
Entry point – Queue Wait-Time Estimation System.

Run with::

    python -m src.main --source 0
    python -m src.main --source videos/test.mp4 --model-size s
    python -m src.main --source rtsp://192.168.1.10/stream --log-interval-sec 10
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import shlex
import socket
import struct
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from urllib.parse import urlparse, urlunparse

import cv2
import numpy as np
import supervision as sv

from src.config import (
    AppConfig,
    DEFAULT_CONFIDENCE,
    DEFAULT_INFERENCE_DEVICE,
    DEFAULT_DETECTOR_IMAGE_SIZE,
    DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY,
    DEFAULT_LOG_INTERVAL_SEC,
    DEFAULT_OUTPUT_FPS,
    DEFAULT_PROCESS_EVERY_N_FRAMES,
    DEFAULT_REALTIME_FILE_PLAYBACK,
    DASHBOARD_EVENT_EMIT_INTERVAL_SEC,
    DASHBOARD_FRAME_EMIT_INTERVAL_SEC,
    PUBLISHED_WEBRTC_PUBLISH_ENABLED,
    PUBLISHED_WEBRTC_RTSP_HOST,
    PUBLISHED_WEBRTC_RTSP_PORT,
    PUBLISHED_WEBRTC_FPS,
    PUBLISHED_WEBRTC_FFMPEG_BINARY,
    WINDOW_NAME,
    N8N_WEBHOOK_URL,
    N8N_WEBHOOK_SECRET,
    WEBHOOK_ENABLED,
    WEBHOOK_SEND_INTERVAL_SEC,
    ALERT_DEDUPE_WINDOW_SEC,
)
from src.detector import PersonDetector
from src.queue_analyzer import QueueAnalyzer, QueueMetrics
from src.threshold_detector import QueueThresholdDetector, ThresholdConfig
from src.tracker import ObjectTracker
from src.utils.drawing import create_annotators, draw_detections
from src.utils.logging_setup import setup_logging
from src.video_capture import VideoStream, open_video_source
from src.webhook_client import WebhookClient
from src.zone_manager import ZoneManager

logger: logging.Logger  # assigned in main()


class DashboardEventWriter:
    """Writes line-delimited dashboard events for the API runtime to tail."""

    def __init__(self, path: str | None, frame_channel: "DashboardFrameChannelClient | None" = None) -> None:
        self._stream = None
        self._frame_channel = frame_channel
        if path:
            event_path = Path(path)
            event_path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = event_path.open("a", encoding="utf-8", buffering=1)

    def emit(self, event: str, payload: dict[str, object]) -> None:
        record = {"event": event, "payload": payload}
        
        # Try to send via socket first (low latency)
        if self._frame_channel is not None and self._frame_channel.configured:
            try:
                self._frame_channel.send_event(record)
                # Socket send succeeded, no need for file fallback
                return
            except Exception:
                # Socket send failed, fall back to file writing
                pass
        
        # Fallback to file writing if socket is unavailable
        if self._stream is None:
            return

        self._stream.write(json.dumps(record) + "\n")
        self._stream.flush()

    def close(self) -> None:
        if self._stream is not None and not self._stream.closed:
            self._stream.close()


class DashboardFrameChannelClient:
    """Pushes encoded dashboard frames to the API runtime over a local binary socket."""

    def __init__(self, *, host: str | None, port: int | None, token: str | None) -> None:
        self._host = host.strip() if isinstance(host, str) else ""
        self._port = int(port) if isinstance(port, int) else None
        self._token = token.strip() if isinstance(token, str) else ""
        self._socket: socket.socket | None = None

    @property
    def configured(self) -> bool:
        return bool(self._host and self._port and self._token)

    def send_frame(self, frame_bytes: bytes) -> None:
        if not self.configured or not frame_bytes:
            return

        if self._socket is None and not self._connect():
            return

        # Prepend message type byte (0x01 for frames) and length
        payload = struct.pack(">BI", 0x01, len(frame_bytes)) + frame_bytes
        sock = self._socket
        if sock is None:
            return

        try:
            sock.sendall(payload)
        except OSError:
            self._close_socket()

    def send_event(self, event_dict: dict) -> None:
        """Send an event message over the socket channel."""
        if not self.configured:
            return

        if self._socket is None and not self._connect():
            return

        try:
            # Serialize event to JSON
            event_json = json.dumps(event_dict)
            event_bytes = event_json.encode("utf-8")
            
            # Prepend message type byte (0x02 for events) and length
            payload = struct.pack(">BI", 0x02, len(event_bytes)) + event_bytes
            sock = self._socket
            if sock is None:
                return

            sock.sendall(payload)
        except (OSError, UnicodeEncodeError):
            self._close_socket()

    def close(self) -> None:
        self._close_socket()

    def _connect(self) -> bool:
        if not self.configured:
            return False

        port = self._port
        if port is None:
            return False

        try:
            sock = socket.create_connection((self._host, port), timeout=0.4)
            sock.settimeout(0.4)
            token_bytes = self._token.encode("utf-8")
            if len(token_bytes) > 65535:
                sock.close()
                return False

            sock.sendall(struct.pack(">H", len(token_bytes)) + token_bytes)
            self._socket = sock
            return True
        except OSError:
            self._close_socket()
            return False

    def _close_socket(self) -> None:
        if self._socket is None:
            return

        try:
            self._socket.close()
        except OSError:
            pass
        finally:
            self._socket = None


class PublishedWebRtcPublisher:
    """Publish unified backend frames to a MediaMTX RTSP path using FFmpeg."""

    def __init__(self, cfg: AppConfig, event_writer: DashboardEventWriter) -> None:
        self._enabled = bool(cfg.annotated_webrtc_enable)
        self._path = (cfg.annotated_webrtc_path or "").strip()
        self._host = (cfg.annotated_webrtc_rtsp_host or "").strip()
        self._port = int(cfg.annotated_webrtc_rtsp_port) if cfg.annotated_webrtc_rtsp_port else None
        self._target_fps = max(1, int(cfg.annotated_webrtc_fps))
        self._ffmpeg_binary = (cfg.annotated_webrtc_ffmpeg_binary or "ffmpeg").strip() or "ffmpeg"
        self._event_writer = event_writer
        self._process: subprocess.Popen | None = None
        self._frame_size: tuple[int, int] | None = None
        self._last_ready: bool | None = None
        self._last_reason: str | None = None
        self._last_compatibility_reason: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._path and self._host and self._port)

    @property
    def path(self) -> str | None:
        return self._path or None

    @property
    def ready(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _resolve_codec_policy(self, *, width: int, height: int) -> tuple[list[str], str | None]:
        """Return baseline-compatible codec args and fallback reason if needed."""
        args: list[str] = [
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level:v",
            "3.1",
            "-preset",
            "ultrafast",  # Changed from veryfast to ultrafast for lower latency
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-x264-params", "bframes=0:force-cfr=1:nal-hrd=cbr",  # Force constant frame rate, no B-frames
        ]
        reason: str | None = None
        if (width % 2) != 0 or (height % 2) != 0:
            args.extend(["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"])
            reason = "codec_fallback_dimension_alignment"
        return args, reason

    def start_if_needed(self, frame: np.ndarray) -> None:
        if not self.configured:
            if self._enabled:
                self._emit_status(
                    ready=False,
                    reason="publisher_unavailable",
                    compatibility_reason="codec_fallback_publisher_unconfigured",
                )
            return
        if self.ready:
            return

        height, width = frame.shape[:2]
        if shutil.which(self._ffmpeg_binary) is None:
            logger.error("FFmpeg binary not found for publish pipeline: %s", self._ffmpeg_binary)
            self._emit_status(
                ready=False,
                reason="publisher_unavailable",
                compatibility_reason="codec_fallback_encoder_missing",
            )
            return
        self._frame_size = (width, height)
        command, compatibility_reason = self._build_command(width=width, height=height)
        logger.info(f"Starting annotated WebRTC publisher: {' '.join(command)}")
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
            logger.info(f"FFmpeg process started with PID {self._process.pid}")
            
            # Log FFmpeg stderr in a separate thread to avoid blocking
            import threading
            def log_ffmpeg_output():
                if self._process and self._process.stderr:
                    for line in iter(self._process.stderr.readline, b''):
                        if line:
                            logger.warning(f"FFmpeg: {line.decode('utf-8', errors='ignore').strip()}")
            
            stderr_thread = threading.Thread(target=log_ffmpeg_output, daemon=True)
            stderr_thread.start()
            
        except OSError as exc:
            logger.error(f"Failed to start FFmpeg process: {exc}")
            self._process = None
            self._emit_status(
                ready=False,
                reason="publisher_unavailable",
                compatibility_reason="codec_fallback_encoder_missing",
            )
            return

        if self.ready:
            logger.info("Annotated WebRTC publisher is ready")
            self._emit_status(ready=True, reason=None, compatibility_reason=compatibility_reason)
        else:
            logger.warning("Annotated WebRTC publisher started but not ready")
            self._emit_status(
                ready=False,
                reason="publisher_not_ready",
                compatibility_reason=compatibility_reason,
            )

    def send_frame(self, frame: np.ndarray) -> None:
        if not self.configured:
            return

        self.start_if_needed(frame)
        process = self._process
        if process is None or process.poll() is not None:
            self._emit_status(
                ready=False,
                reason="publisher_not_ready",
                compatibility_reason=self._last_compatibility_reason,
            )
            return

        expected_size = self._frame_size
        if expected_size is None:
            return
        if (frame.shape[1], frame.shape[0]) != expected_size:
            self.close()
            self.start_if_needed(frame)
            process = self._process
            if process is None or process.poll() is not None:
                self._emit_status(
                    ready=False,
                    reason="publisher_not_ready",
                    compatibility_reason=self._last_compatibility_reason,
                )
                return

        stdin = process.stdin
        if stdin is None:
            self._emit_status(
                ready=False,
                reason="publisher_not_ready",
                compatibility_reason=self._last_compatibility_reason,
            )
            return

        try:
            stdin.write(frame.tobytes())
            stdin.flush()
        except (BrokenPipeError, OSError):
            self.close()
            self._emit_status(
                ready=False,
                reason="publisher_not_ready",
                compatibility_reason=self._last_compatibility_reason,
            )

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return

        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass

        try:
            process.terminate()
            process.wait(timeout=2.0)
        except Exception:
            try:
                process.kill()
            except OSError:
                pass

    def _build_command(self, *, width: int, height: int) -> tuple[list[str], str | None]:
        path = self._path.lstrip("/")
        rtsp_url = f"rtsp://{self._host}:{self._port}/{path}"
        codec_policy_args, compatibility_reason = self._resolve_codec_policy(width=width, height=height)
        
        return [
            self._ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(self._target_fps),
            "-i",
            "-",
            "-an",
            *codec_policy_args,
            "-g", str(self._target_fps),  # Keyframe every 1 second
            "-bf", "0",  # No B-frames for lower latency
            "-f", "rtsp",
            "-rtsp_transport", "udp",  # UDP for low latency
            "-buffer_size", "65535",  # Increase UDP buffer
            "-pkt_size", "1316",  # Optimal packet size for UDP
            "-max_delay", "0",  # Minimize muxing delay
            "-flush_packets", "1",  # Flush packets immediately
            rtsp_url,
        ], compatibility_reason

    def _emit_status(
        self,
        *,
        ready: bool,
        reason: str | None,
        compatibility_reason: str | None = None,
    ) -> None:
        if (
            self._last_reason == reason
            and self._last_ready == ready
            and self._last_compatibility_reason == compatibility_reason
        ):
            return
        self._last_ready = ready
        self._last_reason = reason
        self._last_compatibility_reason = compatibility_reason
        logger.info(f"Emitting transport_status: ready={ready}, reason={reason}, path={self.path}")
        self._event_writer.emit(
            "transport_status",
            {
                "published_webrtc_ready": ready,
                "published_webrtc_path": self.path,
                "reason": reason,
                "compatibility_reason": compatibility_reason,
            },
        )


class UnifiedPublishPipeline:
    """Single publish-path abstraction used by the worker runtime."""

    def __init__(self, cfg: AppConfig, event_writer: DashboardEventWriter) -> None:
        self._publisher = PublishedWebRtcPublisher(cfg, event_writer)

    @property
    def configured(self) -> bool:
        return self._publisher.configured

    @property
    def ready(self) -> bool:
        return self._publisher.ready

    @property
    def path(self) -> str | None:
        return self._publisher.path

    def emit_initial_status(self, event_writer: DashboardEventWriter) -> None:
        if not self.configured:
            event_writer.emit(
                "transport_status",
                {
                    "published_webrtc_ready": False,
                    "published_webrtc_path": self.path,
                    "reason": "publisher_unavailable",
                },
            )
            return
        event_writer.emit(
            "transport_status",
            {
                "published_webrtc_ready": False,
                "published_webrtc_path": self.path,
                "reason": "publisher_not_ready",
            },
        )

    def publish_frame(self, frame: np.ndarray) -> None:
        if not self.configured:
            return
        self._publisher.send_frame(frame)

    def close(self) -> None:
        self._publisher.close()


# Backward-compatible internal alias during naming transition.
AnnotatedWebRtcPublisher = PublishedWebRtcPublisher


@dataclass(frozen=True)
class GStreamerHybridGraphSpec:
    """Precomputed graph details for the hybrid analyzer/publish topology."""

    mode: str
    source_kind: str
    pipeline: str
    command: list[str]
    compatibility_reason: str | None = None


class GStreamerPublishProcess:
    """Manage a gst-launch subprocess lifecycle for publish branch."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start(self, command: list[str]) -> bool:
        self.stop()
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except OSError as exc:
            self._last_error = str(exc)
            self._process = None
            return False
        self._last_error = None
        return self.running

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=2.0)
        except Exception:
            try:
                process.kill()
            except OSError:
                pass

    def poll(self) -> int | None:
        if self._process is None:
            return None
        return self._process.poll()


class GStreamerHybridEngine:
    """Builds a hybrid single-ingest graph and reports availability/compatibility."""

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg

    @staticmethod
    def is_available() -> bool:
        return shutil.which("gst-launch-1.0") is not None

    def _build_rtsp_source_uri(self, source_text: str) -> str:
        parsed = urlparse(source_text)
        if parsed.scheme.lower() != "rtsp":
            return source_text
        if parsed.username is not None or parsed.password is not None:
            return source_text
        username = (self._cfg.rtsp_username or "").strip()
        password = (self._cfg.rtsp_password or "").strip()
        if not username and not password:
            return source_text
        host = parsed.hostname or ""
        netloc = host
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        user_part = username or ""
        pass_part = f":{password}" if password else ""
        netloc = f"{user_part}{pass_part}@{netloc}"
        return urlunparse(parsed._replace(netloc=netloc))

    def build_graph_spec(self, *, source: str | int, publish_path: str | None) -> GStreamerHybridGraphSpec:
        source_text = str(source).strip()
        source_kind = "rtsp" if source_text.lower().startswith("rtsp://") else "file_or_device"
        path = (publish_path or "ann-feed").strip("/")
        rtsp_target = f"rtsp://{self._cfg.annotated_webrtc_rtsp_host}:{self._cfg.annotated_webrtc_rtsp_port}/{path}"
        latency = max(0, int(self._cfg.gstreamer_rtsp_latency_ms))

        if source_kind == "rtsp":
            source_uri = self._build_rtsp_source_uri(source_text)
            ingest = (
                f"rtspsrc location=\"{source_uri}\" protocols=tcp latency={latency} ! "
                "rtph264depay ! h264parse ! avdec_h264 ! videoconvert"
            )
        else:
            ingest = (
                f"filesrc location=\"{source_text}\" ! decodebin ! videoconvert"
                if not source_text.isdigit()
                else f"v4l2src device=/dev/video{source_text} ! videoconvert"
            )

        graph = (
            f"{ingest} ! tee name=t "
            "t. ! queue leaky=downstream max-size-buffers=8 ! videoconvert ! appsink name=analyzer_sink sync=false emit-signals=true max-buffers=2 drop=true "
            "t. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=30 bframes=0 byte-stream=true "
            "! video/x-h264,profile=baseline ! rtspclientsink protocols=tcp "
            f"location=\"{rtsp_target}\""
        )
        command = ["gst-launch-1.0", "-e", *shlex.split(graph, posix=False)]
        return GStreamerHybridGraphSpec(
            mode="gstreamer_hybrid",
            source_kind=source_kind,
            pipeline=graph,
            command=command,
        )


class GStreamerHybridStream:
    """OpenCV/GStreamer capture bound to a single ingest graph with appsink."""

    def __init__(self, graph_pipeline: str, fallback_fps: float = 30.0) -> None:
        self._pipeline = graph_pipeline
        self._cap: cv2.VideoCapture | None = None
        self._width = 0
        self._height = 0
        self._fps = fallback_fps

    def open(self) -> "GStreamerHybridStream":
        self._cap = cv2.VideoCapture(self._pipeline, cv2.CAP_GSTREAMER)
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("Cannot open GStreamer hybrid pipeline via OpenCV CAP_GSTREAMER.")
        ok, frame = self._cap.read()
        if ok and frame is not None:
            self._height, self._width = frame.shape[:2]
        if self._cap is not None:
            fps_value = float(self._cap.get(cv2.CAP_PROP_FPS))
            if fps_value > 0:
                self._fps = fps_value
        return self

    def probe(self) -> bool:
        cap = cv2.VideoCapture(self._pipeline, cv2.CAP_GSTREAMER)
        ok = cap is not None and cap.isOpened()
        if cap is not None:
            cap.release()
        return ok

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "GStreamerHybridStream":
        return self.open()

    def __exit__(self, *_exc) -> None:  # noqa: ANN001
        self.close()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    def frames(self):
        if self._cap is None:
            return
        while True:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                break
            yield frame


class PipelineEngineSelector:
    """Resolves requested engine and emits transport diagnostics."""

    def __init__(self, cfg: AppConfig, event_writer: DashboardEventWriter, publish_pipeline: UnifiedPublishPipeline) -> None:
        self._cfg = cfg
        self._event_writer = event_writer
        self._publish_pipeline = publish_pipeline
        self.selected_mode = "opencv"
        self.compatibility_reason: str | None = None
        self.graph_spec: GStreamerHybridGraphSpec | None = None
        self._gst_process = GStreamerPublishProcess()
        self._requested_mode = "opencv"

    def resolve(self) -> None:
        requested = (self._cfg.pipeline_engine or "opencv").strip().lower()
        self._requested_mode = requested
        if requested != "gstreamer_hybrid":
            self.selected_mode = "opencv"
            return

        if not GStreamerHybridEngine.is_available():
            self.selected_mode = "opencv"
            self.compatibility_reason = "gstreamer_unavailable_fallback_opencv"
            return

        engine = GStreamerHybridEngine(self._cfg)
        self.graph_spec = engine.build_graph_spec(
            source=self._cfg.source,
            publish_path=self._publish_pipeline.path,
        )
        self.selected_mode = "gstreamer_hybrid"
        self.compatibility_reason = "gstreamer_authoritative_ingest"

    def start_runtime(self) -> None:
        # Authoritative ingest mode is handled by OpenCV CAP_GSTREAMER stream creation.
        return

    def tick(self) -> None:
        return

    def close(self) -> None:
        self._gst_process.stop()

    def emit_status(self) -> None:
        if self.selected_mode == "gstreamer_hybrid":
            published_ready = True
            reason = None
        else:
            published_ready = self._publish_pipeline.ready if self._publish_pipeline.configured else False
            reason = None if self._publish_pipeline.ready else (
                "publisher_not_ready" if self._publish_pipeline.configured else "publisher_unavailable"
            )
        self._event_writer.emit(
            "transport_status",
            {
                "published_webrtc_ready": published_ready,
                "published_webrtc_path": self._publish_pipeline.path,
                "reason": reason,
                "compatibility_reason": self.compatibility_reason,
                "pipeline_mode": self.selected_mode,
                "pipeline_graph": self.graph_spec.pipeline if self.graph_spec is not None else None,
            },
        )


@dataclass(frozen=True)
class WebhookJob:
    """Typed unit of webhook work consumed by the background dispatcher."""

    metrics: QueueMetrics
    frame_id: int
    source: str
    feed_id: str | None
    alert_triggered: bool = False
    alert_reason: str = ""
    alert_severity: str = "warning"
    confidence_scores: list[float] | None = None


class AsyncWebhookDispatcher:
    """Send webhook payloads on a background thread to keep the loop responsive."""

    def __init__(self, webhook_client: WebhookClient, max_queue_size: int = 32) -> None:
        self._client = webhook_client
        self._queue: Queue[WebhookJob] = Queue(maxsize=max_queue_size)
        self._stop_event = Event()
        self._worker = Thread(
            target=self._run,
            name="queue-webhook-dispatcher",
            daemon=True,
        )
        self._worker.start()

    def enqueue(
        self,
        *,
        metrics: QueueMetrics,
        frame_id: int,
        source: str,
        feed_id: str | None,
        alert_triggered: bool = False,
        alert_reason: str = "",
        alert_severity: str = "warning",
        confidence_scores: list[float] | None = None,
    ) -> None:
        payload = WebhookJob(
            metrics=metrics,
            frame_id=frame_id,
            source=source,
            feed_id=feed_id,
            alert_triggered=alert_triggered,
            alert_reason=alert_reason,
            alert_severity=alert_severity,
            confidence_scores=confidence_scores,
        )

        if self._stop_event.is_set():
            return

        try:
            self._queue.put_nowait(payload)
            return
        except Full:
            pass

        # Keep the latest payloads under sustained backpressure.
        try:
            self._queue.get_nowait()
            self._queue.task_done()
        except Empty:
            pass

        try:
            self._queue.put_nowait(payload)
        except Full:
            logger.debug("Dropping webhook payload: dispatcher queue is still full.")

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.2)
            except Empty:
                continue

            try:
                self._client.send_metrics(
                    metrics=payload.metrics,
                    frame_id=payload.frame_id,
                    source=payload.source,
                    feed_id=payload.feed_id,
                    alert_triggered=payload.alert_triggered,
                    alert_reason=payload.alert_reason,
                    alert_severity=payload.alert_severity,
                    confidence_scores=payload.confidence_scores,
                )
            except Exception as exc:
                logger.debug("Async webhook send failed: %s", exc)
            finally:
                self._queue.task_done()

    def stop(self, timeout_sec: float = 2.0) -> None:
        self._stop_event.set()
        self._worker.join(timeout=timeout_sec)


# ═══════════════════════════════════════════════════════════════
# Argument parser
# ═══════════════════════════════════════════════════════════════

class TrackerIdStabilizer:
    """Stabilize tracker IDs across short exits/re-entries for GUI usage."""

    def __init__(
        self,
        *,
        reconnect_window_sec: float = 20.0,
        reconnect_max_distance_px: float = 140.0,
    ) -> None:
        self._reconnect_window_sec = max(0.0, float(reconnect_window_sec))
        self._reconnect_max_distance_px = max(1.0, float(reconnect_max_distance_px))
        self._next_stable_id = 1
        self._raw_to_stable: dict[int, int] = {}
        self._stable_last_center: dict[int, tuple[float, float]] = {}
        self._lost_pool: dict[int, tuple[float, tuple[float, float]]] = {}

    def stabilize(self, detections: sv.Detections) -> np.ndarray | None:
        raw_ids = detections.tracker_id
        if raw_ids is None:
            return None
        if len(raw_ids) == 0:
            self._expire_lost_pool(time.monotonic())
            return np.array([], dtype=np.int32)

        now = time.monotonic()
        self._expire_lost_pool(now)
        centers = [self._center_of_box(box) for box in detections.xyxy]

        current_raw_ids = {int(rid) for rid in raw_ids}
        disappeared_raw_ids = set(self._raw_to_stable.keys()) - current_raw_ids
        for raw_id in disappeared_raw_ids:
            stable_id = self._raw_to_stable.pop(raw_id, None)
            if stable_id is None:
                continue
            center = self._stable_last_center.get(stable_id)
            if center is not None:
                self._lost_pool[stable_id] = (now, center)

        stable_ids: list[int] = []
        for idx, raw_id_value in enumerate(raw_ids):
            raw_id = int(raw_id_value)
            stable_id = self._raw_to_stable.get(raw_id)
            if stable_id is None:
                stable_id = self._try_relink_stable_id(
                    current_center=centers[idx],
                    now=now,
                )
                if stable_id is None:
                    stable_id = self._next_stable_id
                    self._next_stable_id += 1
                self._raw_to_stable[raw_id] = stable_id

            self._stable_last_center[stable_id] = centers[idx]
            stable_ids.append(stable_id)

        return np.array(stable_ids, dtype=np.int32)

    @staticmethod
    def _center_of_box(box: np.ndarray) -> tuple[float, float]:
        return (float((box[0] + box[2]) / 2.0), float((box[1] + box[3]) / 2.0))

    def _try_relink_stable_id(
        self,
        *,
        current_center: tuple[float, float],
        now: float,
    ) -> int | None:
        best_stable_id: int | None = None
        best_dist = float('inf')
        for stable_id, (lost_at, prev_center) in list(self._lost_pool.items()):
            if (now - lost_at) > self._reconnect_window_sec:
                self._lost_pool.pop(stable_id, None)
                continue
            dist = math.hypot(current_center[0] - prev_center[0], current_center[1] - prev_center[1])
            if dist <= self._reconnect_max_distance_px and dist < best_dist:
                best_dist = dist
                best_stable_id = stable_id

        if best_stable_id is not None:
            self._lost_pool.pop(best_stable_id, None)
        return best_stable_id

    def _expire_lost_pool(self, now: float) -> None:
        for stable_id, (lost_at, _center) in list(self._lost_pool.items()):
            if (now - lost_at) > self._reconnect_window_sec:
                self._lost_pool.pop(stable_id, None)

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="queue-estimator",
        description=(
            "Real-time queue wait-time estimation from video feed "
            "using YOLO26 + ByteTrack."
        ),
    )
    parser.add_argument(
        "--source",
        type=str,
        default="0",
        help=(
            "Video source: 0 for webcam, path to an mp4 file, "
            "or an RTSP URL. (default: 0)"
        ),
    )
    parser.add_argument(
        "--model-size",
        type=str,
        choices=["n", "s", "m", "l", "x"],
        default="n",
        help="YOLO model size – n(ano), s(mall), m(edium), l(arge), x(large). (default: n)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=DEFAULT_INFERENCE_DEVICE,
        help=(
            "Inference device: auto, cpu, cuda, cuda:0, ... "
            f"(default: {DEFAULT_INFERENCE_DEVICE})"
        ),
    )
    parser.add_argument(
        "--detector-imgsz",
        type=int,
        default=DEFAULT_DETECTOR_IMAGE_SIZE,
        help=(
            "Inference image size passed to YOLO. "
            f"Smaller values are faster. (default: {DEFAULT_DETECTOR_IMAGE_SIZE})"
        ),
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help=(
            "Detector confidence threshold (0-1). "
            f"Lower values can recover more RTSP detections. (default: {DEFAULT_CONFIDENCE:.2f})"
        ),
    )
    parser.add_argument(
        "--process-every-n-frames",
        type=int,
        default=DEFAULT_PROCESS_EVERY_N_FRAMES,
        help=(
            "Run detection/tracking every N frames and reuse the latest result in-between. "
            f"(default: {DEFAULT_PROCESS_EVERY_N_FRAMES})"
        ),
    )
    parser.add_argument(
        "--zone-points",
        type=str,
        default=None,
        help=(
            "JSON list of [x,y] polygon points defining the queue zone. "
            'Example: \'[[100,200],[400,200],[400,600],[100,600]]\'. '
            "If omitted, the full frame is used."
        ),
    )
    parser.add_argument(
        "--output-fps",
        type=int,
        default=DEFAULT_OUTPUT_FPS,
        help=f"Display refresh rate in FPS. (default: {DEFAULT_OUTPUT_FPS})",
    )
    parser.set_defaults(realtime_file_playback=DEFAULT_REALTIME_FILE_PLAYBACK)
    file_playback_group = parser.add_mutually_exclusive_group()
    file_playback_group.add_argument(
        "--realtime-file-playback",
        dest="realtime_file_playback",
        action="store_true",
        help=(
            "Pace non-RTSP file sources to their native FPS for natural playback speed. "
            f"(default: {DEFAULT_REALTIME_FILE_PLAYBACK})"
        ),
    )
    file_playback_group.add_argument(
        "--no-realtime-file-playback",
        dest="realtime_file_playback",
        action="store_false",
        help="Process non-RTSP file sources as fast as possible.",
    )
    parser.add_argument(
        "--log-interval-sec",
        type=float,
        default=DEFAULT_LOG_INTERVAL_SEC,
        help=(
            f"How often (seconds) to log metrics to the console. "
            f"(default: {DEFAULT_LOG_INTERVAL_SEC})"
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level: DEBUG, INFO, WARNING, ERROR. (default: INFO)",
    )
    parser.add_argument(
        "--resize-scale",
        type=float,
        default=1.0,
        help="Scale factor to resize the frame (e.g., 0.5 for 50%%). (default: 1.0)",
    )
    parser.add_argument(
        "--queue-length-warning",
        type=int,
        default=8,
        help="Queue length warning threshold in people. (default: 8)",
    )
    # ── RTSP-specific ─────────────────────────────────────────────
    parser.add_argument(
        "--rtsp-user",
        type=str,
        default=None,
        help="Username for RTSP camera authentication (optional).",
    )
    parser.add_argument(
        "--rtsp-pass",
        type=str,
        default=None,
        help="Password for RTSP camera authentication (optional).",
    )
    parser.add_argument(
        "--rtsp-reconnect",
        type=int,
        default=None,
        help="Number of reconnect attempts on RTSP stream loss (default from config).",
    )
    parser.add_argument(
        "--rtsp-transport",
        type=str,
        choices=["tcp", "udp"],
        default=None,
        help="RTSP transport protocol: tcp (reliable) or udp (low-latency). (default: tcp)",
    )
    # ── Metadata tracking ──────────────────────────────────────────
    parser.add_argument(
        "--establishment-id",
        type=int,
        default=None,
        help="Database ID of the establishment (company/store) (optional).",
    )
    parser.add_argument(
        "--register-id",
        "--caisse-id",
        dest="caisse_id",
        type=int,
        default=None,
        help="Database ID of the checkout/register being monitored (optional).",
    )
    parser.add_argument(
        "--feed-id",
        type=str,
        default=None,
        help="Unique identifier for this source/feed (e.g., cashier_3).",
    )
    parser.add_argument(
        "--disable-webhook",
        action="store_true",
        help="Disable sending queue metrics to the configured webhook endpoint.",
    )
    parser.add_argument(
        "--events-file",
        type=str,
        default=None,
        help="Optional JSONL file used to stream structured dashboard events back to the API runtime.",
    )
    parser.add_argument(
        "--dashboard-render-frames",
        action="store_true",
        help=(
            "Include worker-rendered JPEG frames in dashboard metrics events "
            "so browser tracking boxes stay synchronized with detections."
        ),
    )
    parser.add_argument(
        "--dashboard-frame-jpeg-quality",
        type=int,
        default=DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY,
        help=(
            "JPEG quality (1-100) for dashboard-rendered frames when "
            "--dashboard-render-frames is enabled. (default: "
            f"{DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY})"
        ),
    )
    parser.add_argument(
        "--dashboard-frame-channel-host",
        type=str,
        default=None,
        help="Optional host for local binary dashboard frame transport.",
    )
    parser.add_argument(
        "--dashboard-frame-channel-port",
        type=int,
        default=None,
        help="Optional TCP port for local binary dashboard frame transport.",
    )
    parser.add_argument(
        "--dashboard-frame-channel-token",
        type=str,
        default=None,
        help="Optional shared token used to authenticate the binary dashboard frame channel.",
    )
    parser.add_argument(
        "--published-webrtc-enable",
        "--annotated-webrtc-enable",
        action="store_true",
        default=PUBLISHED_WEBRTC_PUBLISH_ENABLED,
        help=(
            "Enable worker-side published WebRTC publishing via MediaMTX RTSP relay. "
            f"(default: {PUBLISHED_WEBRTC_PUBLISH_ENABLED})"
        ),
    )
    parser.add_argument(
        "--published-webrtc-path",
        "--annotated-webrtc-path",
        type=str,
        default=None,
        help="MediaMTX path name used for published WebRTC relay publishing.",
    )
    parser.add_argument(
        "--published-webrtc-rtsp-host",
        "--annotated-webrtc-rtsp-host",
        type=str,
        default=PUBLISHED_WEBRTC_RTSP_HOST,
        help=f"MediaMTX RTSP host for published relay publishing. (default: {PUBLISHED_WEBRTC_RTSP_HOST})",
    )
    parser.add_argument(
        "--published-webrtc-rtsp-port",
        "--annotated-webrtc-rtsp-port",
        type=int,
        default=PUBLISHED_WEBRTC_RTSP_PORT,
        help=f"MediaMTX RTSP port for published relay publishing. (default: {PUBLISHED_WEBRTC_RTSP_PORT})",
    )
    parser.add_argument(
        "--published-webrtc-fps",
        "--annotated-webrtc-fps",
        type=int,
        default=PUBLISHED_WEBRTC_FPS,
        help=f"Target FPS for published relay publishing. (default: {PUBLISHED_WEBRTC_FPS})",
    )
    parser.add_argument(
        "--published-webrtc-ffmpeg-binary",
        "--annotated-webrtc-ffmpeg-binary",
        type=str,
        default=PUBLISHED_WEBRTC_FFMPEG_BINARY,
        help=(
            "FFmpeg executable used for published WebRTC relay publishing. "
            f"(default: {PUBLISHED_WEBRTC_FFMPEG_BINARY})"
        ),
    )
    parser.add_argument(
        "--pipeline-engine",
        type=str,
        choices=["opencv", "gstreamer_hybrid"],
        default="opencv",
        help="Worker ingest engine mode. (default: opencv)",
    )
    parser.add_argument(
        "--gstreamer-rtsp-latency-ms",
        type=int,
        default=150,
        help="Requested rtspsrc latency for GStreamer hybrid graph. (default: 150)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without opening any GUI windows (cv2.imshow). (default: False)",
    )
    parser.add_argument(
        "--show-tracker-ids",
        action="store_true",
        help="Show tracker ID labels on the desktop OpenCV window.",
    )
    return parser


def parse_zone_points(raw: str | None) -> list[list[float]] | None:
    """Parse the ``--zone-points`` JSON string into a list of [x, y] pairs."""
    if raw is None:
        return None
    try:
        points = json.loads(raw)
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("Need at least 3 points for a polygon.")

        parsed_points: list[list[float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise ValueError("Each zone point must be a [x, y] pair.")

            x = float(point[0])
            y = float(point[1])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Zone point coordinates must be finite numbers.")

            parsed_points.append([x, y])

        return parsed_points
    except (json.JSONDecodeError, TypeError, IndexError, ValueError) as exc:
        logger.warning("Invalid --zone-points (%s). Using full-frame zone.", exc)
        return None


# ═══════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════

def run(cfg: AppConfig) -> None:
    """Run the main detection → tracking → analysis loop.

    Parameters
    ----------
    cfg : AppConfig
        Assembled runtime configuration.
    """
    # ── Initialise components ─────────────────────────────────
    detector = PersonDetector(
        model_path=cfg.model_path,
        confidence=cfg.confidence,
        device=cfg.inference_device,
        image_size=cfg.detector_imgsz if cfg.detector_imgsz > 0 else None,
    )

    webhook_client = WebhookClient(N8N_WEBHOOK_URL, webhook_secret=N8N_WEBHOOK_SECRET) if cfg.webhook_enabled else None
    webhook_dispatcher = AsyncWebhookDispatcher(webhook_client) if webhook_client else None
    frame_channel = DashboardFrameChannelClient(
        host=cfg.dashboard_frame_channel_host,
        port=cfg.dashboard_frame_channel_port,
        token=cfg.dashboard_frame_channel_token,
    )
    event_writer = DashboardEventWriter(cfg.events_file, frame_channel=frame_channel)
    publish_pipeline = UnifiedPublishPipeline(cfg, event_writer)
    engine_selector = PipelineEngineSelector(cfg, event_writer, publish_pipeline)
    engine_selector.resolve()
    engine_selector.start_runtime()
    if cfg.annotated_webrtc_enable:
        publish_pipeline.emit_initial_status(event_writer)
    engine_selector.emit_status()

    stream = None
    if engine_selector.selected_mode == "gstreamer_hybrid" and engine_selector.graph_spec is not None:
        try:
            stream = GStreamerHybridStream(engine_selector.graph_spec.pipeline)
        except RuntimeError:
            stream = None
    if stream is None:
        if engine_selector.selected_mode == "gstreamer_hybrid":
            engine_selector.selected_mode = "opencv"
            engine_selector.compatibility_reason = "gstreamer_launch_failed_fallback_ffmpeg"
            engine_selector.emit_status()
        stream = open_video_source(
            cfg.source,
            rtsp_username=cfg.rtsp_username,
            rtsp_password=cfg.rtsp_password,
            rtsp_reconnect=cfg.rtsp_reconnect if cfg.rtsp_reconnect is not None else None,
            rtsp_transport=cfg.rtsp_transport if cfg.rtsp_transport else None,
        )
    elif isinstance(stream, GStreamerHybridStream) and not stream.probe():
        engine_selector.selected_mode = "opencv"
        engine_selector.compatibility_reason = "gstreamer_launch_failed_fallback_ffmpeg"
        engine_selector.emit_status()
        stream = open_video_source(
            cfg.source,
            rtsp_username=cfg.rtsp_username,
            rtsp_password=cfg.rtsp_password,
            rtsp_reconnect=cfg.rtsp_reconnect if cfg.rtsp_reconnect is not None else None,
            rtsp_transport=cfg.rtsp_transport if cfg.rtsp_transport else None,
        )

    with stream:
        tracker = ObjectTracker(frame_rate=int(stream.fps))
        zone_mgr = ZoneManager(
            polygon_points=cfg.zone_polygon,
            frame_resolution=stream.resolution,
        )
        annotators = create_annotators()
        analyzer = QueueAnalyzer()
        id_stabilizer = TrackerIdStabilizer()
        threshold_detector = QueueThresholdDetector(
            ThresholdConfig(
                queue_length_warning=cfg.queue_length_warning,
            )
        )

        # Multi-stream identity for webhook payloads; fallback to source string
        feed_identifier = (
            str(cfg.feed_id)
            if cfg.feed_id
            else (f"caisse_{cfg.caisse_id}" if cfg.caisse_id is not None else str(cfg.source))
        )

        source_is_file = _is_file_source(cfg.source)
        source_fps = max(float(stream.fps), 1.0)
        realtime_file_playback = bool(cfg.realtime_file_playback and source_is_file)

        display_target_fps = cfg.output_fps
        if realtime_file_playback and display_target_fps <= 0 and not cfg.headless:
            display_target_fps = max(1, int(round(source_fps)))

        frame_delay = int(1000 / display_target_fps) if display_target_fps > 0 else 1
        playback_target_fps = _compute_playback_target_fps(
            source_fps=source_fps,
            output_fps=display_target_fps,
            realtime_file_playback=realtime_file_playback,
        )
        process_stride = max(1, int(cfg.process_every_n_frames))
        last_log_time = time.monotonic()
        last_webhook_time = time.monotonic()
        last_dashboard_event_time = time.monotonic()
        last_dashboard_frame_time = time.monotonic()
        last_warning_message: str | None = None
        last_warning_webhook_time = 0.0
        frame_count = 0
        dashboard_jpeg_quality = int(np.clip(cfg.dashboard_frame_jpeg_quality, 30, 95))

        last_detections: sv.Detections | None = None
        last_in_zone: np.ndarray | None = None
        last_labels: list[str] = []
        last_metrics: QueueMetrics | None = None

        # Real-time pacing for headless file playback (GUI path is paced by waitKey).
        playback_started_at = time.perf_counter()
        playback_frame_index = 0

        # Rolling performance counters (reset on each metrics log window)
        window_started_at = time.monotonic()
        last_logged_frame_count = 0
        processed_frames_window = 0
        detect_ms_window = 0.0
        track_ms_window = 0.0
        analyze_ms_window = 0.0
        dashboard_encode_ms_window = 0.0
        dashboard_emitted_frames_window = 0

        logger.info(
            "Entering main loop. Press 'q' to quit. (process_every_n_frames=%d, detector_imgsz=%s, realtime_file_playback=%s)",
            process_stride,
            cfg.detector_imgsz if cfg.detector_imgsz > 0 else "auto",
            realtime_file_playback,
        )

        try:
            for frame in stream.frames():
                frame_count += 1
                playback_frame_index += 1
                event_timestamp = time.time()

                should_process_frame = (
                    last_detections is None
                    or last_metrics is None
                    or process_stride <= 1
                    or (frame_count % process_stride == 0)
                )

                alerts = []
                if should_process_frame:
                    stage_started = time.perf_counter()
                    detections = detector.detect(frame)
                    detect_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    stage_started = time.perf_counter()
                    detections = tracker.update(detections)
                    track_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    stage_started = time.perf_counter()
                    in_zone = zone_mgr.trigger(detections)
                    stable_tracker_ids = (
                        id_stabilizer.stabilize(detections)
                        if cfg.show_tracker_ids
                        else detections.tracker_id
                    )
                    metrics = analyzer.update(
                        in_zone_mask=in_zone,
                        tracker_ids=stable_tracker_ids,
                    )
                    analyze_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    alerts = threshold_detector.check_metrics(
                        people_in_zone=metrics.people_in_zone,
                        estimated_wait_sec=metrics.estimated_wait_sec,
                        arrival_rate=metrics.arrival_rate,
                        service_rate=metrics.service_rate,
                        frame_id=frame_count,
                        timestamp=event_timestamp,
                    )
                    labels = _build_labels(stable_tracker_ids, in_zone)

                    last_detections = detections
                    last_in_zone = in_zone
                    last_metrics = metrics
                    last_labels = labels
                    processed_frames_window += 1
                else:
                    detections = last_detections
                    in_zone = last_in_zone if last_in_zone is not None else np.array([], dtype=bool)
                    metrics = last_metrics
                    labels = last_labels

                if detections is None or metrics is None:
                    continue

                rendered_display_frame: np.ndarray | None = None

                # 5. Draw + 6. Show
                if not cfg.headless:
                    rendered_display_frame = frame.copy()
                    if cfg.show_tracker_ids:
                        rendered_display_frame = draw_detections(
                            rendered_display_frame,
                            detections,
                            annotators=annotators,
                            labels=labels,
                        )
                    rendered_display_frame = zone_mgr.annotate(rendered_display_frame)

                    # Resize frame if scale != 1.0
                    if cfg.resize_scale != 1.0:
                        rendered_display_frame = cv2.resize(
                            rendered_display_frame,
                            (0, 0),
                            fx=cfg.resize_scale,
                            fy=cfg.resize_scale,
                        )

                    cv2.imshow(WINDOW_NAME, rendered_display_frame)

                    wait_delay = frame_delay
                    if realtime_file_playback:
                        target_elapsed = playback_frame_index / playback_target_fps
                        elapsed = time.perf_counter() - playback_started_at
                        sleep_sec = target_elapsed - elapsed
                        wait_delay = max(1, int(sleep_sec * 1000)) if sleep_sec > 0 else 1

                    key = cv2.waitKey(wait_delay) & 0xFF
                    if key == ord("q"):
                        logger.info("Quit requested by user.")
                        break

                # 7. Periodic logging and event emission
                now = time.monotonic()
                engine_selector.tick()
                if (
                    (
                        (cfg.dashboard_render_frames and frame_channel.configured)
                        or publish_pipeline.configured
                    )
                    and (now - last_dashboard_frame_time) >= DASHBOARD_FRAME_EMIT_INTERVAL_SEC
                ):
                    if rendered_display_frame is not None:
                        render_frame = rendered_display_frame
                    else:
                        render_frame = frame.copy()
                        if cfg.show_tracker_ids:
                            render_frame = draw_detections(
                                render_frame,
                                detections,
                                annotators=annotators,
                                labels=labels,
                            )
                        render_frame = zone_mgr.annotate(render_frame)

                        if cfg.resize_scale != 1.0:
                            render_frame = cv2.resize(
                                render_frame,
                                (0, 0),
                                fx=cfg.resize_scale,
                                fy=cfg.resize_scale,
                            )

                    if cfg.dashboard_render_frames and frame_channel.configured:
                        encode_started_at = time.perf_counter()
                        encoded_ok, encoded_frame = cv2.imencode(
                            ".jpg",
                            render_frame,
                            [int(cv2.IMWRITE_JPEG_QUALITY), dashboard_jpeg_quality],
                        )
                        encode_elapsed_ms = (time.perf_counter() - encode_started_at) * 1000.0
                        dashboard_encode_ms_window += encode_elapsed_ms
                        if encoded_ok:
                            frame_channel.send_frame(encoded_frame.tobytes())

                    if publish_pipeline.configured and engine_selector.selected_mode != "gstreamer_hybrid":
                        publish_pipeline.publish_frame(render_frame)

                    dashboard_emitted_frames_window += 1
                    last_dashboard_frame_time = now

                if (now - last_dashboard_event_time) >= DASHBOARD_EVENT_EMIT_INTERVAL_SEC:
                    elapsed_window = max(now - window_started_at, 1e-6)
                    emitted_fps = dashboard_emitted_frames_window / elapsed_window
                    queue_age_ms = max(0.0, (now - last_dashboard_frame_time) * 1000.0)
                    frame_age_ms = max(0.0, (time.time() - event_timestamp) * 1000.0)
                    avg_encode_ms = (
                        dashboard_encode_ms_window / dashboard_emitted_frames_window
                        if dashboard_emitted_frames_window
                        else 0.0
                    )

                    event_writer.emit(
                        "metrics_update",
                        {
                            "metrics": _dashboard_metrics_payload(
                                metrics,
                                event_timestamp,
                                frame_count,
                                detections,
                            ),
                            "performance": {
                                "dashboard_emit_fps": emitted_fps,
                                "dashboard_jpeg_encode_ms": avg_encode_ms,
                                "queue_age_ms": queue_age_ms,
                                "end_to_end_frame_age_ms": frame_age_ms,
                            },
                        },
                    )
                    last_dashboard_event_time = now

                for alert in alerts:
                    if alert.message == last_warning_message:
                        continue

                    event_writer.emit(
                        "alert_fired",
                        {"alert": _dashboard_alert_payload(alert)},
                    )
                    last_warning_message = alert.message

                    # Immediately forward the warning to webhook (if configured), respecting dedupe window.
                    if webhook_dispatcher:
                        now_ts = time.time()
                        if (now_ts - last_warning_webhook_time) >= ALERT_DEDUPE_WINDOW_SEC:
                            webhook_dispatcher.enqueue(
                                metrics=metrics,
                                frame_id=frame_count,
                                source=str(cfg.source),
                                feed_id=feed_identifier,
                                alert_triggered=True,
                                alert_reason=alert.message,
                                alert_severity=alert.severity.value,
                            )
                            last_warning_webhook_time = now_ts

                if (now - last_log_time) >= cfg.log_interval_sec:
                    elapsed = max(now - window_started_at, 1e-6)
                    loop_fps = (frame_count - last_logged_frame_count) / elapsed
                    processed_fps = processed_frames_window / elapsed
                    avg_detect_ms = detect_ms_window / processed_frames_window if processed_frames_window else 0.0
                    avg_track_ms = track_ms_window / processed_frames_window if processed_frames_window else 0.0
                    avg_analyze_ms = analyze_ms_window / processed_frames_window if processed_frames_window else 0.0

                    _log_metrics(
                        metrics,
                        frame_count,
                        loop_fps=loop_fps,
                        processed_fps=processed_fps,
                        process_stride=process_stride,
                        avg_detect_ms=avg_detect_ms,
                        avg_track_ms=avg_track_ms,
                        avg_analyze_ms=avg_analyze_ms,
                    )
                    logger.info(
                        "transport_perf emit_fps=%.2f encode_ms=%.2f queue_age_ms=%.2f e2e_frame_age_ms=%.2f",
                        dashboard_emitted_frames_window / elapsed,
                        dashboard_encode_ms_window / dashboard_emitted_frames_window if dashboard_emitted_frames_window else 0.0,
                        max(0.0, (now - last_dashboard_frame_time) * 1000.0),
                        max(0.0, (time.time() - event_timestamp) * 1000.0),
                    )
                    event_writer.emit(
                        "transport_status",
                        {
                            "published_webrtc_ready": (
                                engine_selector.selected_mode == "gstreamer_hybrid"
                                or (publish_pipeline.ready if publish_pipeline.configured else False)
                            ),
                            "published_webrtc_path": publish_pipeline.path,
                            "reason": (
                                None
                                if engine_selector.selected_mode == "gstreamer_hybrid"
                                else (
                                    None
                                    if publish_pipeline.ready
                                    else ("publisher_not_ready" if publish_pipeline.configured else "publisher_unavailable")
                                )
                            ),
                            "compatibility_reason": engine_selector.compatibility_reason,
                            "pipeline_mode": engine_selector.selected_mode,
                            "pipeline_graph": (
                                engine_selector.graph_spec.pipeline
                                if engine_selector.graph_spec is not None
                                else None
                            ),
                            "performance": {
                                "dashboard_emit_fps": dashboard_emitted_frames_window / elapsed,
                                "dashboard_jpeg_encode_ms": (
                                    dashboard_encode_ms_window / dashboard_emitted_frames_window
                                    if dashboard_emitted_frames_window
                                    else 0.0
                                ),
                                "queue_age_ms": max(0.0, (now - last_dashboard_frame_time) * 1000.0),
                                "end_to_end_frame_age_ms": max(0.0, (time.time() - event_timestamp) * 1000.0),
                            },
                        },
                    )
                    last_log_time = now
                    window_started_at = now
                    last_logged_frame_count = frame_count
                    processed_frames_window = 0
                    detect_ms_window = 0.0
                    track_ms_window = 0.0
                    analyze_ms_window = 0.0
                    dashboard_encode_ms_window = 0.0
                    dashboard_emitted_frames_window = 0

                # 8. Periodic webhook sending to n8n
                if webhook_dispatcher and (now - last_webhook_time) >= WEBHOOK_SEND_INTERVAL_SEC:
                    webhook_dispatcher.enqueue(
                        metrics=metrics,
                        frame_id=frame_count,
                        source=str(cfg.source),
                        feed_id=feed_identifier,
                    )
                    last_webhook_time = now

                if realtime_file_playback and cfg.headless:
                    target_elapsed = playback_frame_index / playback_target_fps
                    elapsed = time.perf_counter() - playback_started_at
                    sleep_sec = target_elapsed - elapsed
                    if sleep_sec > 0:
                        time.sleep(min(sleep_sec, 0.25))
        finally:
            if webhook_dispatcher:
                webhook_dispatcher.stop()
            if webhook_client:
                webhook_client.close()
            engine_selector.close()
            publish_pipeline.close()
            event_writer.close()
            frame_channel.close()

    cv2.destroyAllWindows()
    logger.info("Pipeline finished. Processed %d frames.", frame_count)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _build_labels(tracker_ids: np.ndarray | None, in_zone: np.ndarray) -> list[str]:
    """Generate per-detection labels and avoid implicit unknown placeholders."""
    labels: list[str] = []
    for idx, inside in enumerate(in_zone):
        if tracker_ids is not None and idx < len(tracker_ids):
            tag = f"#{int(tracker_ids[idx])}"
        else:
            tag = "No ID"
        if inside:
            tag += " [IN]"
        labels.append(tag)
    return labels


def _is_file_source(source: str | int) -> bool:
    """Return True when source is a local video file path."""
    if isinstance(source, int):
        return False

    source_text = str(source).strip()
    if not source_text or source_text.isdigit():
        return False

    return not source_text.lower().startswith("rtsp://")


def _compute_playback_target_fps(
    *,
    source_fps: float,
    output_fps: int,
    realtime_file_playback: bool,
) -> float:
    """Choose target FPS for playback pacing.

    Real-time file playback should follow the file's native FPS (float) for
    natural speed, while non-realtime mode can optionally use output_fps.
    """
    normalized_source_fps = max(float(source_fps), 1.0)
    if realtime_file_playback:
        return normalized_source_fps
    if output_fps > 0:
        return float(output_fps)
    return normalized_source_fps


def _metrics_dict(m: QueueMetrics) -> dict[str, str]:
    """Convert ``QueueMetrics`` to a display-friendly overlay dictionary."""
    return {
        "People": str(m.people_in_zone),
        "λ (arr)": f"{m.arrival_rate:.3f}",
        "μ (svc)": f"{m.service_rate:.3f}",
        "Wait": f"{m.estimated_wait_sec:.1f}s",
    }


def _log_metrics(
    m: QueueMetrics,
    frame_count: int,
    *,
    loop_fps: float,
    processed_fps: float,
    process_stride: int,
    avg_detect_ms: float,
    avg_track_ms: float,
    avg_analyze_ms: float,
) -> None:
    """Write queue metrics and rolling loop performance diagnostics."""
    logger.info(
        "[frame %d] zone=%d | λ=%.4f | μ=%.4f | W=%.1fs | loop_fps=%.2f | proc_fps=%.2f | stride=%d | detect=%.1fms | track=%.1fms | analyze=%.1fms",
        frame_count,
        m.people_in_zone,
        m.arrival_rate,
        m.service_rate,
        m.estimated_wait_sec,
        loop_fps,
        processed_fps,
        process_stride,
        avg_detect_ms,
        avg_track_ms,
        avg_analyze_ms,
    )


def _dashboard_metrics_payload(
    m: QueueMetrics,
    timestamp: float,
    frame_seq: int,
    detections: sv.Detections | None = None,
) -> dict[str, object]:
    """Convert runtime metrics into the frontend websocket contract."""

    # Convert supervision detections (xyxy) to nested list for JSON
    # Each detection is [x1, y1, x2, y2, confidence, class_id, tracker_id]
    det_list: list[list[float]] | None = None
    if detections is not None:
        det_list = []
        for i, box in enumerate(detections.xyxy):
            row = [
                float(box[0]), float(box[1]), float(box[2]), float(box[3]),
                float(detections.confidence[i]) if detections.confidence is not None else 1.0,
                float(detections.class_id[i]) if detections.class_id is not None else 0.0,
                float(detections.tracker_id[i]) if detections.tracker_id is not None else -1.0,
            ]
            det_list.append(row)

    return {
        "timestamp": timestamp,
        "people_in_zone": m.people_in_zone,
        "arrival_rate": m.arrival_rate,
        "service_rate": m.service_rate,
        "wait_time_seconds": m.estimated_wait_sec,
        "detections": det_list,
        "frame_seq": frame_seq,
        "pts_ms": timestamp * 1000.0,
        "server_emitted_at_ms": time.time() * 1000.0,
    }


def _dashboard_alert_payload(alert) -> dict[str, object]:  # noqa: ANN001
    """Convert threshold alerts into the frontend websocket contract."""
    return {
        "alert_type": alert.alert_type.value,
        "severity": alert.severity.value,
        "message": alert.message,
        "threshold_name": alert.threshold_name,
        "current_value": alert.current_value,
        "threshold_value": alert.threshold_value,
        "frame_id": alert.frame_id,
        "timestamp": datetime.fromtimestamp(alert.timestamp, tz=timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    """Parse CLI args and launch the pipeline."""
    global logger

    parser = build_parser()
    args = parser.parse_args()

    logger = setup_logging(level=args.log_level)

    zone_pts = parse_zone_points(args.zone_points)

    cfg = AppConfig(
        source=args.source,
        model_size=args.model_size,
        confidence=max(0.05, min(0.95, float(args.confidence))),
        inference_device=(args.device or "auto").strip() or "auto",
        zone_points=zone_pts,
        output_fps=args.output_fps,
        log_interval_sec=args.log_interval_sec,
        resize_scale=args.resize_scale,
        detector_imgsz=max(0, int(args.detector_imgsz)),
        process_every_n_frames=max(1, int(args.process_every_n_frames)),
        realtime_file_playback=bool(args.realtime_file_playback),
        queue_length_warning=args.queue_length_warning,
        rtsp_username=args.rtsp_user,
        rtsp_password=args.rtsp_pass,
        rtsp_reconnect=args.rtsp_reconnect,
        rtsp_transport=args.rtsp_transport or "tcp",
        establishment_id=args.establishment_id,
        caisse_id=args.caisse_id,
        webhook_enabled=WEBHOOK_ENABLED and not args.disable_webhook,
        events_file=args.events_file,
        dashboard_render_frames=args.dashboard_render_frames,
        dashboard_frame_jpeg_quality=args.dashboard_frame_jpeg_quality,
        dashboard_frame_channel_host=args.dashboard_frame_channel_host,
        dashboard_frame_channel_port=args.dashboard_frame_channel_port,
        dashboard_frame_channel_token=args.dashboard_frame_channel_token,
        annotated_webrtc_enable=bool(args.published_webrtc_enable),
        annotated_webrtc_path=args.published_webrtc_path,
        annotated_webrtc_rtsp_host=args.published_webrtc_rtsp_host,
        annotated_webrtc_rtsp_port=args.published_webrtc_rtsp_port,
        annotated_webrtc_fps=max(1, int(args.published_webrtc_fps)),
        annotated_webrtc_ffmpeg_binary=args.published_webrtc_ffmpeg_binary,
        pipeline_engine=(args.pipeline_engine or "opencv").strip().lower(),
        gstreamer_rtsp_latency_ms=max(0, int(args.gstreamer_rtsp_latency_ms)),
        show_tracker_ids=bool(args.show_tracker_ids),
        headless=args.headless,
    )

    logger.info("Configuration: %s", cfg)
    run(cfg)


if __name__ == "__main__":
    main()





