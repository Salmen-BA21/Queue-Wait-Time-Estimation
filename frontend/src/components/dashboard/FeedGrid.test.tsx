import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FeedGrid } from "@/components/dashboard/FeedGrid";
import type { VideoFeed } from "@/lib/api";

const mockUseFeedWebRtc = vi.fn();

vi.mock("@/hooks/use-feed-webrtc", () => ({
  useFeedWebRtc: (args: unknown) => mockUseFeedWebRtc(args),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    resolveApiUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUseFeedWebRtc.mockReturnValue({
    videoRef: { current: null },
    streamReady: false,
    isConnecting: false,
    isSupported: false,
    connectionError: null,
    playoutTimestampMs: null,
    estimatedPlayoutTimestampMs: null,
  });
});

function createFeed(overrides: Partial<VideoFeed> = {}): VideoFeed {
  return {
    feed_id: "feed-1",
    name: "Checkout 1",
    source: "rtsp://camera-1/live",
    preview_path: null,
    model_size: "n",
    status: "running",
    created_at: "2026-03-10T12:00:00Z",
    updated_at: "2026-03-10T12:00:00Z",
    establishment_id: null,
    caisse_id: null,
    zone: {
      points: [
        { x: 0.1, y: 0.1 },
        { x: 0.5, y: 0.1 },
        { x: 0.5, y: 0.7 },
      ],
    },
    queue_length_warning: 8,
    latest_metrics: null,
    transport: {
      webrtc: {
        enabled: true,
        ready: true,
        path_name: "feed-1",
        reason: null,
      },
    },
    last_error: null,
    last_warning: null,
    last_warning_code: null,
    ...overrides,
  };
}

function createMetrics(overrides: Partial<NonNullable<VideoFeed["latest_metrics"]>> = {}): NonNullable<VideoFeed["latest_metrics"]> {
  return {
    timestamp: Date.now() / 1000,
    people_in_zone: 2,
    arrival_rate: 0.1,
    service_rate: 0.2,
    wait_time_seconds: 6.5,
    queue_stable: true,
    detections: [[10, 20, 80, 120]],
    render_frame_jpeg_base64: null,
    frame_seq: 12,
    pts_ms: 10_000,
    server_emitted_at_ms: 9_980,
    ...overrides,
  };
}

describe("FeedGrid WebRTC synced overlays", () => {
  it("shows single WEBRTC badge for live WebRTC transport", () => {
    mockUseFeedWebRtc.mockReturnValue({
      videoRef: { current: null },
      streamReady: true,
      isConnecting: false,
      isSupported: true,
      connectionError: null,
      playoutTimestampMs: 10_000,
      estimatedPlayoutTimestampMs: 10_000,
    });

    render(
      <FeedGrid
        feeds={[createFeed({ latest_metrics: createMetrics() })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    expect(screen.getByTestId("transport-badge")).toHaveTextContent("WEBRTC");
  });

  it("renders synced detection boxes when PTS matches playout time", () => {
    mockUseFeedWebRtc.mockReturnValue({
      videoRef: { current: null },
      streamReady: true,
      isConnecting: false,
      isSupported: true,
      connectionError: null,
      playoutTimestampMs: 10_005,
      estimatedPlayoutTimestampMs: 10_005,
    });

    render(
      <FeedGrid
        feeds={[createFeed({ latest_metrics: createMetrics() })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    const videoEl = document.querySelector("video") as HTMLVideoElement | null;
    expect(videoEl).not.toBeNull();
    Object.defineProperty(videoEl, "videoWidth", { configurable: true, value: 1280 });
    Object.defineProperty(videoEl, "videoHeight", { configurable: true, value: 720 });
    fireEvent.loadedMetadata(videoEl!);

    expect(screen.queryAllByTestId("detection-box").length).toBeGreaterThan(0);
  });

  it("suppresses detection boxes when metadata-video skew is too large", () => {
    mockUseFeedWebRtc.mockReturnValue({
      videoRef: { current: null },
      streamReady: true,
      isConnecting: false,
      isSupported: true,
      connectionError: null,
      playoutTimestampMs: 20_000,
      estimatedPlayoutTimestampMs: 20_000,
    });

    render(
      <FeedGrid
        feeds={[createFeed({ latest_metrics: createMetrics({ pts_ms: 10_000 }) })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    const videoEl = document.querySelector("video") as HTMLVideoElement | null;
    expect(videoEl).not.toBeNull();
    Object.defineProperty(videoEl, "videoWidth", { configurable: true, value: 1280 });
    Object.defineProperty(videoEl, "videoHeight", { configurable: true, value: 720 });
    fireEvent.loadedMetadata(videoEl!);

    expect(screen.queryAllByTestId("detection-box")).toHaveLength(0);
  });
});
