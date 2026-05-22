import { useEffect, useRef, useState } from "react";

import { ApiError, submitFeedWebRtcOffer } from "@/lib/api";

const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000] as const;

function createConnectionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `WebRTC preview request failed (${error.status}).`;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "WebRTC preview failed unexpectedly.";
}

async function waitForIceGatheringComplete(peer: RTCPeerConnection, timeoutMs: number): Promise<void> {
  if (peer.iceGatheringState === "complete") {
    return;
  }

  await new Promise<void>((resolve) => {
    const timeoutId = window.setTimeout(() => {
      peer.removeEventListener("icegatheringstatechange", onIceGatheringChange);
      resolve();
    }, timeoutMs);

    const onIceGatheringChange = () => {
      if (peer.iceGatheringState !== "complete") {
        return;
      }
      window.clearTimeout(timeoutId);
      peer.removeEventListener("icegatheringstatechange", onIceGatheringChange);
      resolve();
    };

    peer.addEventListener("icegatheringstatechange", onIceGatheringChange);
  });
}

function clearVideoStream(video: HTMLVideoElement | null): void {
  if (!video) {
    return;
  }

  const stream = video.srcObject;
  if (stream instanceof MediaStream) {
    for (const track of stream.getTracks()) {
      track.stop();
    }
  }

  video.srcObject = null;
}

function shouldRetry(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return true;
  }

  // Validation/state failures should not trigger reconnect churn.
  return ![404, 409, 422].includes(error.status);
}

export function useFeedWebRtc({ feedId, enabled }: { feedId: string; enabled: boolean }) {
  const isSupported =
    typeof window !== "undefined"
    && typeof window.RTCPeerConnection !== "undefined"
    && typeof window.MediaStream !== "undefined";

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const frameCallbackIdRef = useRef<number | null>(null);
  const statsIntervalRef = useRef<number | null>(null);

  const [streamReady, setStreamReady] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [playoutTimestampMs, setPlayoutTimestampMs] = useState<number | null>(null);
  const [estimatedPlayoutTimestampMs, setEstimatedPlayoutTimestampMs] = useState<number | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !streamReady || !mediaStreamRef.current) {
      return;
    }

    video.srcObject = mediaStreamRef.current;
    void video.play().catch(() => {
      // Autoplay can be blocked in strict environments. The user still has a fallback transport.
    });
  }, [streamReady]);

  useEffect(() => {
    reconnectAttemptRef.current = 0;
  }, [feedId]);

  useEffect(() => {
    let cancelled = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
    const clearTimingCollectors = () => {
      const video = videoRef.current;
      if (
        frameCallbackIdRef.current !== null
        && video
        && typeof video.cancelVideoFrameCallback === "function"
      ) {
        video.cancelVideoFrameCallback(frameCallbackIdRef.current);
      } else if (frameCallbackIdRef.current !== null && typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(frameCallbackIdRef.current);
      }
      frameCallbackIdRef.current = null;
      if (statsIntervalRef.current !== null) {
        window.clearInterval(statsIntervalRef.current);
        statsIntervalRef.current = null;
      }
    };

    const cleanupPeer = () => {
      clearTimingCollectors();
      const peer = peerRef.current;
      peerRef.current = null;
      if (peer) {
        peer.ontrack = null;
        peer.onconnectionstatechange = null;
        peer.close();
      }

      mediaStreamRef.current = null;
      clearVideoStream(videoRef.current);
      setPlayoutTimestampMs(null);
      setEstimatedPlayoutTimestampMs(null);
    };

    const startTimingCollectors = (peer: RTCPeerConnection) => {
      const video = videoRef.current;
      if (!video) {
        return;
      }

      const hasRequestVideoFrameCallback = typeof video.requestVideoFrameCallback === "function";
      if (hasRequestVideoFrameCallback) {
        const tick = (_now: number, metadata: VideoFrameCallbackMetadata) => {
          setPlayoutTimestampMs(metadata.expectedDisplayTime);
          frameCallbackIdRef.current = video.requestVideoFrameCallback(tick);
        };
        frameCallbackIdRef.current = video.requestVideoFrameCallback(tick);
      } else {
        const rafTick = () => {
          setPlayoutTimestampMs(performance.timeOrigin + performance.now());
          frameCallbackIdRef.current = window.requestAnimationFrame(rafTick);
        };
        frameCallbackIdRef.current = window.requestAnimationFrame(rafTick);
      }

      statsIntervalRef.current = window.setInterval(async () => {
        try {
          const stats = await peer.getStats();
          let bestTimestampMs: number | null = null;
          stats.forEach((report) => {
            if (report.type !== "inbound-rtp") {
              return;
            }
            const candidate = report as RTCInboundRtpStreamStats & { estimatedPlayoutTimestamp?: number };
            if (typeof candidate.estimatedPlayoutTimestamp === "number" && Number.isFinite(candidate.estimatedPlayoutTimestamp)) {
              if (bestTimestampMs === null || candidate.estimatedPlayoutTimestamp > bestTimestampMs) {
                bestTimestampMs = candidate.estimatedPlayoutTimestamp;
              }
            }
          });
          if (bestTimestampMs !== null) {
            setEstimatedPlayoutTimestampMs(bestTimestampMs);
          }
        } catch {
          // Ignore stats failures; fallback timing path will remain active.
        }
      }, 1000);
    };

    const scheduleReconnect = (error: unknown) => {
      if (cancelled || !enabled || !shouldRetry(error)) {
        return;
      }

      const attempt = reconnectAttemptRef.current;
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      reconnectAttemptRef.current += 1;

      clearReconnectTimer();
      reconnectTimerRef.current = window.setTimeout(() => {
        void connect();
      }, delay);
    };

    const connect = async () => {
      if (cancelled || !enabled || !isSupported) {
        return;
      }

      setIsConnecting(true);
      setStreamReady(false);
      setConnectionError(null);
      cleanupPeer();

      const peer = new RTCPeerConnection();
      peerRef.current = peer;

      peer.ontrack = (event) => {
        mediaStreamRef.current = event.streams[0] ?? new MediaStream([event.track]);
        reconnectAttemptRef.current = 0;
        setConnectionError(null);
        setStreamReady(true);
        startTimingCollectors(peer);
      };

      peer.onconnectionstatechange = () => {
        if (peer.connectionState === "connected") {
          reconnectAttemptRef.current = 0;
          setConnectionError(null);
          return;
        }

        if (peer.connectionState === "failed" || peer.connectionState === "disconnected") {
          setStreamReady(false);
          scheduleReconnect(new Error("WebRTC connection dropped."));
        }
      };

      try {
        peer.addTransceiver("video", { direction: "recvonly" });

        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        await waitForIceGatheringComplete(peer, 3000);

        const localOffer = peer.localDescription;
        if (!localOffer?.sdp) {
          throw new Error("WebRTC SDP offer is unavailable.");
        }

        const response = await submitFeedWebRtcOffer(feedId, {
          offer: {
            type: "offer",
            sdp: localOffer.sdp,
          },
        });

        await peer.setRemoteDescription({
          type: "answer",
          sdp: response.answer.sdp,
        });
      } catch (error) {
        setStreamReady(false);
        setConnectionError(createConnectionErrorMessage(error));
        scheduleReconnect(error);
      } finally {
        if (!cancelled) {
          setIsConnecting(false);
        }
      }
    };

    if (!enabled) {
      clearReconnectTimer();
      cleanupPeer();
      reconnectAttemptRef.current = 0;
      setStreamReady(false);
      setIsConnecting(false);
      setConnectionError(null);
      return () => {
        cancelled = true;
      };
    }

    if (!isSupported) {
      clearReconnectTimer();
      cleanupPeer();
      setStreamReady(false);
      setIsConnecting(false);
      setConnectionError("WebRTC is not supported in this browser environment.");
      return () => {
        cancelled = true;
      };
    }

    void connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      cleanupPeer();
    };
  }, [enabled, feedId, isSupported]);

  return {
    videoRef,
    streamReady,
    isConnecting,
    isSupported,
    connectionError,
    playoutTimestampMs,
    estimatedPlayoutTimestampMs,
  };
}
