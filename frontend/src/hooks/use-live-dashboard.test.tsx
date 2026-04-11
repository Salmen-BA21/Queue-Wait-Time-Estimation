import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLiveDashboard } from "@/hooks/use-live-dashboard";
import type { DashboardSocketEvent, SystemHealth, VideoFeed } from "@/lib/api";
import {
  connectDashboardSocket,
  createFeed,
  getSystemHealth,
  listFeeds,
  restartFeed,
  startFeed,
  stopFeed,
  updateZone,
} from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    connectDashboardSocket: vi.fn(),
    createFeed: vi.fn(),
    getSystemHealth: vi.fn(),
    listFeeds: vi.fn(),
    restartFeed: vi.fn(),
    startFeed: vi.fn(),
    stopFeed: vi.fn(),
    updateZone: vi.fn(),
  };
});

class MockDashboardSocket {
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn(() => {
    this.onclose?.({} as CloseEvent);
  });

  emit(event: DashboardSocketEvent): void {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
  }
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function createFeedRecord(overrides: Partial<VideoFeed> = {}): VideoFeed {
  return {
    feed_id: "feed-1",
    name: "Checkout 1",
    source: "rtsp://camera-1/live",
    preview_path: null,
    model_size: "n",
    status: "created",
    created_at: "2026-03-10T12:00:00Z",
    updated_at: "2026-03-10T12:00:00Z",
    establishment_id: null,
    caisse_id: null,
    zone: null,
    latest_metrics: null,
    last_error: null,
    last_warning: null,
    last_warning_code: null,
    ...overrides,
  };
}

describe("useLiveDashboard", () => {
  let socket: MockDashboardSocket;
  let queryClient: QueryClient;

  beforeEach(() => {
    socket = new MockDashboardSocket();
    queryClient = createQueryClient();

    vi.mocked(connectDashboardSocket).mockReturnValue(socket as unknown as WebSocket);
    vi.mocked(listFeeds).mockResolvedValue([createFeedRecord()]);
    vi.mocked(getSystemHealth).mockResolvedValue({
      status: "ok",
      api_version: "test",
      total_feeds: 1,
      active_feeds: 0,
      websocket_clients: 1,
      timestamp: "2026-03-10T12:00:00Z",
    } satisfies SystemHealth);
    vi.mocked(createFeed).mockResolvedValue(createFeedRecord({ feed_id: "feed-new", name: "New Feed" }));
    vi.mocked(updateZone).mockResolvedValue(createFeedRecord({ zone: { points: [{ x: 0.1, y: 0.1 }, { x: 0.2, y: 0.2 }, { x: 0.3, y: 0.3 }] } }));
    vi.mocked(startFeed).mockResolvedValue(createFeedRecord({ status: "running" }));
    vi.mocked(stopFeed).mockResolvedValue(createFeedRecord({ status: "stopped" }));
    vi.mocked(restartFeed).mockResolvedValue(createFeedRecord({ status: "running" }));
  });

  afterEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
  });

  it("syncs websocket updates into feed state, activity, and runtime controls", async () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useLiveDashboard(), { wrapper });

    await waitFor(() => expect(result.current.feeds).toHaveLength(1));
    expect(result.current.derived.registeredFeeds).toBe(1);

    act(() => {
      socket.emit({
        event: "metrics_update",
        payload: {
          feed_id: "feed-1",
          metrics: {
            timestamp: 1710000000,
            people_in_zone: 3,
            arrival_rate: 0.2,
            service_rate: 0.4,
            wait_time_seconds: 8,
            queue_stable: true,
          },
        },
      });
      socket.emit({
        event: "alert_fired",
        payload: {
          feed_id: "feed-1",
          alert: {
            alert_type: "queue_backlog",
            severity: "warning",
            message: "Queue exceeded the warning threshold.",
            threshold_name: "queue_length_warning",
            current_value: 3,
            threshold_value: 5,
            frame_id: 8,
            timestamp: "2026-03-10T12:05:00Z",
          },
        },
      });
      socket.emit({
        event: "feed_status",
        payload: {
          action: "updated",
          feed_id: null,
          feed: createFeedRecord({
            status: "running",
            latest_metrics: {
              timestamp: 1710000000,
              people_in_zone: 3,
              arrival_rate: 0.2,
              service_rate: 0.4,
              wait_time_seconds: 8,
              queue_stable: true,
            },
              last_warning: "Queue exceeded the warning threshold.",
              last_warning_code: "queue_length_warning",
          }),
        },
      });
    });

    await waitFor(() => expect(result.current.feeds[0].latest_metrics?.people_in_zone).toBe(3));
    expect(result.current.feeds[0].status).toBe("running");
    expect(result.current.feeds[0].last_warning_code).toBe("queue_length_warning");
    expect(result.current.derived.peopleTotal).toBe(3);
    expect(result.current.derived.liveMonitoring.attentionFeedCount).toBe(1);
    expect(result.current.activity.some((item) => item.message === "Queue exceeded the warning threshold." && item.severity === "warning")).toBe(true);

    await act(async () => {
      await result.current.startFeedMutation.mutateAsync("feed-1");
    });

    await waitFor(() => expect(vi.mocked(startFeed)).toHaveBeenCalledWith("feed-1"));
    expect(result.current.feeds[0].status).toBe("running");
    expect(result.current.activity.some((item) => item.message === "Checkout 1 was started.")).toBe(true);

    act(() => {
      socket.onerror?.({} as Event);
    });

    expect(
      result.current.activity.some((item) =>
        item.message.includes("Live dashboard connection dropped"),
      ),
    ).toBe(true);
  });
});