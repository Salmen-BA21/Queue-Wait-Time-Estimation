import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FeedGrid } from "@/components/dashboard/FeedGrid";
import { getFeedMjpegStreamUrl, getFeedSnapshot, type VideoFeed } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFeedMjpegStreamUrl: vi.fn((feedId: string) => `http://localhost:8000/api/feeds/${feedId}/stream`),
    getFeedSnapshot: vi.fn(),
    resolveApiUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
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
    last_error: null,
    last_warning: null,
    last_warning_code: null,
    ...overrides,
  };
}

function createMetrics(renderFrameJpegBase64: string | null = null): NonNullable<VideoFeed["latest_metrics"]> {
  return {
    timestamp: Date.now(),
    people_in_zone: 2,
    arrival_rate: 0.1,
    service_rate: 0.2,
    wait_time_seconds: 6.5,
    wait_time_ci: [4.0, 9.0],
    uncertainty_level: "LOW",
    queue_stable: true,
    detections: [[10, 20, 80, 120]],
    render_frame_jpeg_base64: renderFrameJpegBase64,
  };
}

describe("FeedGrid MJPEG transport", () => {
  it("falls back to MJPEG when WebRTC is unavailable", () => {
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

    const liveFrame = screen.getByAltText("Checkout 1 live frame") as HTMLImageElement;
    expect(liveFrame.src).toContain("/api/feeds/feed-1/stream?attempt=0");
    expect(getFeedMjpegStreamUrl).toHaveBeenCalledWith("feed-1");
    expect(getFeedSnapshot).not.toHaveBeenCalled();
  });

  it("falls back to one-shot snapshot if MJPEG stream fails", async () => {
    vi.mocked(getFeedSnapshot).mockResolvedValue({
      feed_id: "feed-1",
      source: "rtsp://camera-1/live",
      captured: true,
      resolution: "1280x720",
      width: 1280,
      height: 720,
      image_data_url: "data:image/jpeg;base64,ZmFrZS1mYWxsYmFjaw==",
      error: null,
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

    fireEvent.error(screen.getByAltText("Checkout 1 live frame"));

    await waitFor(() => {
      expect(getFeedSnapshot).toHaveBeenCalledWith("feed-1");
    });
    expect(await screen.findByAltText("Checkout 1 fallback frame")).toBeInTheDocument();
  });

  it("renders running uploaded video feeds with the MJPEG endpoint", () => {
    render(
      <FeedGrid
        feeds={[
          createFeed({
            feed_id: "feed-2",
            name: "Retail Video",
            source: "/data/uploads/retail.mp4",
            preview_path: "/api/uploads/files/retail.mp4",
            status: "running",
            latest_metrics: createMetrics(),
          }),
        ]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    const liveFrame = screen.getByAltText("Retail Video live frame") as HTMLImageElement;
    expect(liveFrame.src).toContain("/api/feeds/feed-2/stream?attempt=0");
    expect(getFeedMjpegStreamUrl).toHaveBeenCalledWith("feed-2");
    expect(getFeedSnapshot).not.toHaveBeenCalled();
  });

  it("forces one MJPEG reconnect when feed transitions into running", async () => {
    const { rerender } = render(
      <FeedGrid
        feeds={[createFeed({ status: "initializing", latest_metrics: null })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    expect(screen.getByText("Initializing worker")).toBeInTheDocument();
    expect(screen.queryByAltText("Checkout 1 live frame")).not.toBeInTheDocument();

    rerender(
      <FeedGrid
        feeds={[createFeed({ status: "running", latest_metrics: createMetrics() })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    await waitFor(() => {
      expect((screen.getByAltText("Checkout 1 live frame") as HTMLImageElement).src).toContain("attempt=1");
    });
  });

  it("forces one MJPEG reconnect when first worker-rendered frame metadata appears", async () => {
    const { rerender } = render(
      <FeedGrid
        feeds={[createFeed({ status: "running", latest_metrics: createMetrics(null) })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    expect((screen.getByAltText("Checkout 1 live frame") as HTMLImageElement).src).toContain("attempt=0");

    rerender(
      <FeedGrid
        feeds={[createFeed({ status: "running", latest_metrics: createMetrics("YmFja2VuZC1yZW5kZXJlZA==") })]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    await waitFor(() => {
      expect((screen.getByAltText("Checkout 1 live frame") as HTMLImageElement).src).toContain("attempt=1");
    });
  });

  it("shows static video preview for created (not yet started) uploaded video feeds", () => {
    render(
      <FeedGrid
        feeds={[
          createFeed({
            feed_id: "feed-3",
            name: "Retail Video",
            source: "/data/uploads/retail.mp4",
            preview_path: "/api/uploads/files/retail.mp4",
            status: "created",
            latest_metrics: null,
          }),
        ]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    expect(screen.queryByAltText("Retail Video live frame")).not.toBeInTheDocument();
    const videoEl = document.querySelector("video") as HTMLVideoElement | null;
    expect(videoEl).not.toBeNull();
    expect(videoEl!.src).toContain("/api/uploads/files/retail.mp4");
  });

  it("shows loading state for running feed until first worker metrics arrive", () => {
    render(
      <FeedGrid
        feeds={[
          createFeed({
            status: "running",
            latest_metrics: null,
            source: "/data/uploads/retail.mp4",
            preview_path: "/api/uploads/files/retail.mp4",
          }),
        ]}
        emptyState={false}
        activeFeedAction={null}
        onEditZone={() => {}}
        onFeedAction={() => {}}
        onSaveThresholds={async () => {}}
        isSavingThresholds={false}
      />,
    );

    expect(screen.getByText("Preparing live stream")).toBeInTheDocument();
    expect(screen.getByText("Waiting for the first analyzed frame from the backend worker.")).toBeInTheDocument();
    expect(screen.queryByAltText("Checkout 1 live frame")).not.toBeInTheDocument();
    expect(document.querySelector("video")).toBeNull();
  });
});

