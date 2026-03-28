import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

describe("FeedGrid MJPEG transport", () => {
  it("renders RTSP feeds with the MJPEG endpoint instead of snapshot polling", () => {
    vi.mocked(getFeedSnapshot).mockResolvedValue({
      feed_id: "feed-1",
      source: "rtsp://camera-1/live",
      captured: true,
      resolution: "1280x720",
      width: 1280,
      height: 720,
      image_data_url: "data:image/jpeg;base64,ZmFrZQ==",
      error: null,
    });

    render(
      <FeedGrid
        feeds={[createFeed()]}
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
        feeds={[createFeed()]}
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
});
