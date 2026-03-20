import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "@/pages/Dashboard";
import type {
  BatchFeedLaunchResult,
  Caisse,
  Establishment,
  ONVIFCameraTestResult,
  ONVIFDevice,
  ONVIFStream,
  RTSPConnectionTestResult,
  VideoFeed,
} from "@/lib/api";
import {
  discoverOnvifDevices,
  launchFeedBatch,
  listCaisses,
  listEstablishments,
  resolveOnvifStreams,
  testOnvifCamera,
  testRtspConnection,
  uploadVideo,
} from "@/lib/api";
import { useLiveDashboard } from "@/hooks/use-live-dashboard";
import { toast } from "sonner";

vi.mock("@/hooks/use-live-dashboard", () => ({
  useLiveDashboard: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    discoverOnvifDevices: vi.fn(),
    launchFeedBatch: vi.fn(),
    listCaisses: vi.fn(),
    listEstablishments: vi.fn(),
    resolveOnvifStreams: vi.fn(),
    testOnvifCamera: vi.fn(),
    testRtspConnection: vi.fn(),
    uploadVideo: vi.fn(),
  };
});

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  (globalThis as typeof globalThis & { ResizeObserver: typeof MockResizeObserver }).ResizeObserver = MockResizeObserver;
}

vi.mock("recharts", () => {
  const MockContainer = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    ResponsiveContainer: MockContainer,
    LineChart: MockContainer,
    BarChart: MockContainer,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Line: () => null,
    Bar: () => null,
  };
});

vi.mock("@/components/dashboard/ZoneSelectionDialog", () => ({
  ZoneSelectionDialog: ({ open, onPointsChange, onContinue, continueLabel = "Continue to Model" }: {
    open: boolean;
    onPointsChange: (points: Array<{ x: number; y: number }>) => void;
    onContinue: () => void;
    continueLabel?: string;
  }) => {
    if (!open) {
      return null;
    }

    return (
      <div data-testid="mock-zone-dialog">
        <button
          onClick={() => {
            onPointsChange([
              { x: 0.1, y: 0.1 },
              { x: 0.5, y: 0.2 },
              { x: 0.4, y: 0.7 },
            ]);
            window.setTimeout(onContinue, 0);
          }}
          type="button"
        >
          {continueLabel}
        </button>
      </div>
    );
  },
}));

vi.mock("@/components/dashboard/ModelSelectionDialog", () => ({
  ModelSelectionDialog: ({ open, onModelChange, onConfirm }: {
    open: boolean;
    onModelChange: (value: "n" | "s" | "m" | "l" | "x") => void;
    onConfirm: () => void;
  }) => {
    if (!open) {
      return null;
    }

    return (
      <div data-testid="mock-model-dialog">
        <button
          onClick={() => {
            onModelChange("m");
            onConfirm();
          }}
          type="button"
        >
          Confirm Model
        </button>
      </div>
    );
  },
}));

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
    status: "running",
    created_at: "2026-03-10T12:00:00Z",
    updated_at: "2026-03-10T12:00:00Z",
    establishment_id: null,
    caisse_id: null,
    zone: { points: [{ x: 0.1, y: 0.1 }, { x: 0.2, y: 0.2 }, { x: 0.3, y: 0.3 }] },
    latest_metrics: null,
    last_error: null,
    last_warning: null,
    last_warning_code: null,
    ...overrides,
  };
}

function createUseLiveDashboardValue(feeds: VideoFeed[] = []) {
  return {
    feeds,
    feedsQuery: { isLoading: false, isError: false, data: feeds },
    systemHealthQuery: {
      isLoading: false,
      isError: false,
      data: {
        status: "ok",
        api_version: "test",
        total_feeds: feeds.length,
        active_feeds: feeds.filter((feed) => feed.status === "running").length,
        websocket_clients: 1,
        timestamp: "2026-03-10T12:00:00Z",
      },
    },
    createFeedMutation: { mutateAsync: vi.fn() },
    updateZoneMutation: { mutateAsync: vi.fn() },
    startFeedMutation: { mutateAsync: vi.fn() },
    stopFeedMutation: { mutateAsync: vi.fn() },
    restartFeedMutation: { mutateAsync: vi.fn() },
    deleteFeedMutation: { mutateAsync: vi.fn() },
    activity: [],
    derived: {
      registeredFeeds: feeds.length,
      onlineFeeds: feeds.filter((feed) => feed.status === "running").length,
      peopleTotal: feeds.reduce((total, feed) => total + (feed.latest_metrics?.people_in_zone ?? 0), 0),
      averageWaitTime: 0,
      liveMonitoring: {
        attentionFeedCount: feeds.filter((feed) => Boolean(feed.last_error || feed.last_warning)).length,
        feedsWithRuntimeErrors: feeds.filter((feed) => Boolean(feed.last_error)),
        feedsWithRuntimeWarnings: feeds.filter((feed) => Boolean(feed.last_warning)),
        unstableFeeds: feeds.filter((feed) => feed.latest_metrics?.queue_stable === false),
        highUncertaintyFeeds: feeds.filter((feed) => feed.latest_metrics?.uncertainty_level === "High"),
      },
      waitChartData: [],
      queueChartData: [],
    },
  };
}

function renderDashboard() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockDashboardState(feeds: VideoFeed[] = []) {
  const dashboardState = createUseLiveDashboardValue(feeds);
  vi.mocked(useLiveDashboard).mockReturnValue(dashboardState as unknown as ReturnType<typeof useLiveDashboard>);
  return dashboardState;
}

function getSetupFileInput(): HTMLInputElement {
  const fileInput = document.querySelector('input[type="file"]');
  if (!(fileInput instanceof HTMLInputElement)) {
    throw new Error("Expected file input to be present in the setup dialog.");
  }
  return fileInput;
}

function createVideoFile(name: string, contents: string): File {
  return new File([contents], name, { type: "video/mp4" });
}

async function openBatchSetup() {
  renderDashboard();
  fireEvent.click(screen.getByRole("button", { name: "Setup Batch" }));
  await screen.findByLabelText("Feed name");
}

describe("Dashboard integration", () => {
  beforeEach(() => {
    vi.mocked(listEstablishments).mockResolvedValue([] satisfies Establishment[]);
    vi.mocked(listCaisses).mockResolvedValue([] satisfies Caisse[]);
    vi.mocked(discoverOnvifDevices).mockResolvedValue([] satisfies ONVIFDevice[]);
    vi.mocked(resolveOnvifStreams).mockResolvedValue([] satisfies ONVIFStream[]);
    vi.mocked(testOnvifCamera).mockResolvedValue({
      connected: true,
      transport: "tcp",
      stream_count: 1,
      tested_stream: { url: "rtsp://camera/test" },
      streams: [{ url: "rtsp://camera/test" }],
      resolution: "1920x1080",
      width: 1920,
      height: 1080,
      fps: 25,
      error: null,
    } satisfies ONVIFCameraTestResult);
    vi.mocked(testRtspConnection).mockResolvedValue({
      connected: true,
      transport: "tcp",
      resolution: "1920x1080",
      width: 1920,
      height: 1080,
      fps: 25,
      error: null,
    } satisfies RTSPConnectionTestResult);
    vi.mocked(uploadVideo).mockResolvedValue({
      file_name: "queue.mp4",
      file_path: "/tmp/queue.mp4",
      preview_path: "/api/uploads/files/queue.mp4",
    });
    vi.mocked(launchFeedBatch).mockResolvedValue({
      launch_mode: "create_and_start",
      runtime: {
        log_level: "INFO",
        webhook_enabled: false,
      },
      results: [],
      summary: {
        total: 1,
        created: 1,
        started: 1,
        failed: 0,
      },
    } satisfies BatchFeedLaunchResult);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("stages an RTSP source and launches the batch with shared runtime settings", async () => {
    mockDashboardState([]);
    await openBatchSetup();
    fireEvent.change(screen.getByLabelText("Feed name"), { target: { value: "Checkout Upload" } });

    const fileInput = getSetupFileInput();
    fireEvent.change(fileInput, { target: { files: [createVideoFile("queue.mp4", "video-bytes")] } });

    fireEvent.click(screen.getByRole("button", { name: "Continue to Zone" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue to Model" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm Model" }));
    fireEvent.click(await screen.findByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "Create and Start Batch" }));

    await waitFor(() => expect(launchFeedBatch).toHaveBeenCalledTimes(1));
    expect(launchFeedBatch).toHaveBeenCalledWith({
      launch_mode: "create_and_start",
      runtime: {
        log_level: "INFO",
        webhook_enabled: false,
      },
      feeds: [
        expect.objectContaining({
          client_id: expect.any(String),
          name: "Checkout Upload",
          source: "/tmp/queue.mp4",
          model_size: "m",
          rtsp_transport: null,
          zone: {
            points: [
              { x: 0.1, y: 0.1 },
              { x: 0.5, y: 0.2 },
              { x: 0.4, y: 0.7 },
            ],
          },
        }),
      ],
    });
  });

  it("queues multiple local videos from one picker action and advances to the next file after staging", async () => {
    mockDashboardState([]);
    await openBatchSetup();

    const fileInput = getSetupFileInput();
    const fileA = createVideoFile("checkout-a.mp4", "video-a");
    const fileB = createVideoFile("checkout-b.mp4", "video-b");
    fireEvent.change(fileInput, { target: { files: [fileA, fileB] } });

    expect(await screen.findByText("Selected videos and streams")).toBeInTheDocument();
    expect(await screen.findByText("Selected local videos")).toBeInTheDocument();
    expect(screen.getAllByText("checkout-a.mp4").length).toBeGreaterThan(0);
    expect(screen.getByText(/Up next 1: checkout-b.mp4/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("checkout-a")).toBeInTheDocument();
    expect(screen.getByText("2 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Continue to Zone" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue to Model" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm Model" }));

    expect(await screen.findByText("Review and Launch")).toBeInTheDocument();
    expect(screen.getByText("checkout-a")).toBeInTheDocument();
    expect(screen.getByText("checkout-a.mp4")).toBeInTheDocument();
    expect(screen.getByText("checkout-b.mp4")).toBeInTheDocument();
    expect(screen.getByText("Ready for batch submit")).toBeInTheDocument();
  });

  it("keeps an uploaded local video staged when switching to ONVIF discovery and back", async () => {
    mockDashboardState([]);
    await openBatchSetup();

    const fileInput = getSetupFileInput();
    fireEvent.change(fileInput, { target: { files: [createVideoFile("queue.mp4", "video-bytes")] } });

    expect(await screen.findByText("Selected local videos")).toBeInTheDocument();
    expect(screen.getAllByText("queue.mp4").length).toBeGreaterThan(0);

    const onvifTab = screen.getByRole("tab", { name: "ONVIF Discovery" });
    fireEvent.mouseDown(onvifTab);
    fireEvent.click(onvifTab);

    expect(await screen.findByText("Discover ONVIF cameras")).toBeInTheDocument();

    const fileTab = screen.getByRole("tab", { name: "Local MP4" });
    fireEvent.mouseDown(fileTab);
    fireEvent.click(fileTab);

    expect(await screen.findByText("Selected local videos")).toBeInTheDocument();
    expect(screen.getAllByText("queue.mp4").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Continue to Zone" })).toBeEnabled();
  });

  it("lets the operator bulk-add multiple discovered ONVIF cameras into the review queue", async () => {
    mockDashboardState([]);
    vi.mocked(discoverOnvifDevices).mockResolvedValue([
      {
        ip: "192.168.1.10",
        name: "Entrance A",
        manufacturer: "Acme",
        model: "Cam 1",
        serial: "serial-a",
        hardware: "hw-a",
        location: "Front",
        services: { media: "http://192.168.1.10/onvif/media" },
        xaddrs: "http://192.168.1.10/onvif/device_service",
      },
      {
        ip: "192.168.1.11",
        name: "Entrance B",
        manufacturer: "Acme",
        model: "Cam 2",
        serial: "serial-b",
        hardware: "hw-b",
        location: "Front",
        services: { media: "http://192.168.1.11/onvif/media" },
        xaddrs: "http://192.168.1.11/onvif/device_service",
      },
    ] satisfies ONVIFDevice[]);
    vi.mocked(resolveOnvifStreams).mockImplementation(async ({ device }) => ([
      { url: `rtsp://${device.ip}/stream/main` },
    ]));
    vi.mocked(testOnvifCamera).mockImplementation(async ({ device }) => ({
      connected: true,
      transport: "tcp",
      stream_count: 1,
      tested_stream: { url: `rtsp://${device.ip}/stream/main` },
      streams: [{ url: `rtsp://${device.ip}/stream/main` }],
      resolution: "1920x1080",
      width: 1920,
      height: 1080,
      fps: 25,
      error: null,
    } satisfies ONVIFCameraTestResult));

    await openBatchSetup();
    const onvifTab = screen.getByRole("tab", { name: "ONVIF Discovery" });
    fireEvent.mouseDown(onvifTab);
    fireEvent.click(onvifTab);
    fireEvent.change(screen.getByLabelText("Feed name"), { target: { value: "Lobby" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Discover Cameras" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Discover Cameras" }));

    expect(await screen.findByRole("button", { name: /Entrance A/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Entrance B/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByText("Selected videos and streams")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add Selected Cameras" }));

    expect(await screen.findByText("Review and Launch")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create and Start Batch" }));

    await waitFor(() => expect(launchFeedBatch).toHaveBeenCalledTimes(1));
    expect(launchFeedBatch).toHaveBeenCalledWith(expect.objectContaining({
      launch_mode: "create_and_start",
      feeds: expect.arrayContaining([
        expect.objectContaining({ name: expect.stringContaining("Entrance A"), source: "rtsp://192.168.1.10/stream/main" }),
        expect.objectContaining({ name: expect.stringContaining("Entrance B"), source: "rtsp://192.168.1.11/stream/main" }),
      ]),
    }));
  });

  it("uses per-camera ONVIF credentials when bulk-adding multiple cameras", async () => {
    mockDashboardState([]);
    vi.mocked(discoverOnvifDevices).mockResolvedValue([
      {
        ip: "192.168.1.20",
        name: "Loading Dock",
        manufacturer: "Acme",
        model: "Cam 3",
        serial: "serial-c",
        hardware: "hw-c",
        location: "Warehouse",
        services: { media: "http://192.168.1.20/onvif/media" },
        xaddrs: "http://192.168.1.20/onvif/device_service",
      },
      {
        ip: "192.168.1.21",
        name: "Side Door",
        manufacturer: "Acme",
        model: "Cam 4",
        serial: "serial-d",
        hardware: "hw-d",
        location: "Warehouse",
        services: { media: "http://192.168.1.21/onvif/media" },
        xaddrs: "http://192.168.1.21/onvif/device_service",
      },
    ] satisfies ONVIFDevice[]);
    vi.mocked(resolveOnvifStreams).mockImplementation(async ({ device, username, password }) => {
      expect(username).toBeDefined();
      expect(password).toBeDefined();
      return [{ url: `rtsp://${device.ip}/stream/main` }];
    });
    vi.mocked(testOnvifCamera).mockImplementation(async ({ device, username, password }) => ({
      connected: true,
      transport: "tcp",
      stream_count: 1,
      tested_stream: { url: `rtsp://${device.ip}/stream/main` },
      streams: [{ url: `rtsp://${device.ip}/stream/main` }],
      resolution: "1920x1080",
      width: 1920,
      height: 1080,
      fps: 25,
      error: null,
    } satisfies ONVIFCameraTestResult));

    await openBatchSetup();
    const onvifTab = screen.getByRole("tab", { name: "ONVIF Discovery" });
    fireEvent.mouseDown(onvifTab);
    fireEvent.click(onvifTab);
    fireEvent.change(screen.getByLabelText("Feed name"), { target: { value: "Warehouse" } });
    fireEvent.click(screen.getByRole("button", { name: "Discover Cameras" }));

    expect(await screen.findByRole("button", { name: /Loading Dock/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Select all" }));

    fireEvent.change(screen.getByLabelText("Username for Loading Dock"), { target: { value: "dock-user" } });
    fireEvent.change(screen.getByLabelText("Password for Loading Dock"), { target: { value: "dock-pass" } });
    fireEvent.change(screen.getByLabelText("Username for Side Door"), { target: { value: "door-user" } });
    fireEvent.change(screen.getByLabelText("Password for Side Door"), { target: { value: "door-pass" } });

    fireEvent.click(screen.getByRole("button", { name: "Add Selected Cameras" }));

    await waitFor(() => expect(resolveOnvifStreams).toHaveBeenCalledTimes(2));
    expect(resolveOnvifStreams).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ username: "dock-user", password: "dock-pass" }),
    );
    expect(resolveOnvifStreams).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ username: "door-user", password: "door-pass" }),
    );
    expect(testOnvifCamera).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ username: "dock-user", password: "dock-pass" }),
    );
    expect(testOnvifCamera).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ username: "door-user", password: "door-pass" }),
    );
  });

  it("lets the operator choose which queued local video becomes active before tracing the zone", async () => {
    mockDashboardState([]);
    await openBatchSetup();

    const fileInput = getSetupFileInput();
    const fileA = createVideoFile("checkout-a.mp4", "video-a");
    const fileB = createVideoFile("checkout-b.mp4", "video-b");
    fireEvent.change(fileInput, { target: { files: [fileA, fileB] } });

    expect(await screen.findByText(/Up next 1: checkout-b.mp4/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Use This Video Now" }));

    expect(screen.getByDisplayValue("checkout-b")).toBeInTheDocument();
    expect(screen.getAllByText("checkout-b.mp4").length).toBeGreaterThan(0);
    expect(screen.getByText(/Up next 1: checkout-a.mp4/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Continue to Zone" }));
    expect(await screen.findByTestId("mock-zone-dialog")).toBeInTheDocument();
  });

  it("routes edit-zone, remove, and restart actions through the live dashboard mutations", async () => {
    const dashboardState = mockDashboardState([createFeedRecord()]);
    renderDashboard();

    fireEvent.click(screen.getByRole("button", { name: "Edit Zone" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save Zone" }));

    await waitFor(() =>
      expect(dashboardState.updateZoneMutation.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          feedId: "feed-1",
          zone: expect.objectContaining({
            points: expect.arrayContaining([
              expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
              expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
              expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
            ]),
          }),
        }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "Restart" }));

    await waitFor(() => expect(dashboardState.restartFeedMutation.mutateAsync).toHaveBeenCalledWith("feed-1"));

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove Feed" }));

    await waitFor(() => expect(dashboardState.deleteFeedMutation.mutateAsync).toHaveBeenCalledWith("feed-1"));
  });

  it("shows a worker action error when restart fails", async () => {
    const dashboardState = createUseLiveDashboardValue([createFeedRecord()]);
    dashboardState.restartFeedMutation.mutateAsync = vi.fn().mockRejectedValue(new Error("Worker start rejected"));
    vi.mocked(useLiveDashboard).mockReturnValue(dashboardState as unknown as ReturnType<typeof useLiveDashboard>);

    renderDashboard();

    fireEvent.click(screen.getByRole("button", { name: "Restart" }));

    await waitFor(() => expect(dashboardState.restartFeedMutation.mutateAsync).toHaveBeenCalledWith("feed-1"));
    expect(toast.error).toHaveBeenCalledWith("Worker start rejected");
  });
});