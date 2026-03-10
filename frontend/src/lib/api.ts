export type FeedStatus = "created" | "initializing" | "running" | "stopped" | "error";
export type ModelSize = "n" | "s" | "m" | "l" | "x";
export type RTSPTransport = "tcp" | "udp";
export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";
export type BatchLaunchMode = "save_only" | "create_and_start";
export type BatchLaunchItemStatus = "created" | "started" | "failed";

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string | null;
}

export interface ZonePoint {
  x: number;
  y: number;
}

export interface ZonePolygon {
  points: ZonePoint[];
}

export interface QueueMetrics {
  timestamp: number;
  people_in_zone: number;
  arrival_rate: number;
  service_rate: number;
  wait_time_seconds: number | null;
  wait_time_ci: [number, number] | null;
  uncertainty_level: string;
  queue_stable: boolean;
}

export interface QueueAlert {
  alert_type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  threshold_name: string;
  current_value: number;
  threshold_value: number;
  frame_id: number;
  timestamp: string;
}

export interface VideoFeed {
  feed_id: string;
  name: string;
  source: string;
  preview_path: string | null;
  model_size: ModelSize;
  status: FeedStatus;
  created_at: string;
  updated_at: string;
  establishment_id: number | null;
  caisse_id: number | null;
  zone: ZonePolygon | null;
  latest_metrics: QueueMetrics | null;
  last_error: string | null;
  last_warning: string | null;
  last_warning_code: string | null;
}

export interface SystemHealth {
  status: "ok" | "degraded";
  api_version: string;
  total_feeds: number;
  active_feeds: number;
  websocket_clients: number;
  timestamp: string;
}

export interface FeedSnapshotEvent {
  event: "snapshot";
  payload: {
    feeds: VideoFeed[];
  };
}

export interface FeedStatusEvent {
  event: "feed_status";
  payload: {
    action: "created" | "updated" | "deleted";
    feed: VideoFeed | null;
    feed_id: string | null;
  };
}

export interface MetricsUpdateEvent {
  event: "metrics_update";
  payload: {
    feed_id: string;
    metrics: QueueMetrics;
  };
}

export interface AlertFiredEvent {
  event: "alert_fired";
  payload: {
    feed_id: string;
    alert: QueueAlert;
  };
}

export interface SystemWarningEvent {
  event: "system_warning";
  payload: {
    feed_id: string;
    code: string;
    message: string;
    timestamp: string;
  };
}

export type DashboardSocketEvent = FeedSnapshotEvent | FeedStatusEvent | MetricsUpdateEvent | AlertFiredEvent | SystemWarningEvent;

export interface CreateFeedInput {
  name: string;
  source: string;
  model_size?: ModelSize;
  establishment_id?: number | null;
  caisse_id?: number | null;
  rtsp_username?: string | null;
  rtsp_password?: string | null;
  rtsp_transport?: RTSPTransport | null;
}

export interface BatchRuntimeSettings {
  webhook_enabled?: boolean;
  log_level?: LogLevel;
}

export interface BatchFeedDraft extends CreateFeedInput {
  client_id: string;
  zone?: ZonePolygon | null;
}

export interface BatchFeedLaunchInput {
  feeds: BatchFeedDraft[];
  launch_mode?: BatchLaunchMode;
  runtime?: BatchRuntimeSettings;
}

export interface BatchFeedLaunchItemResult {
  client_id: string;
  status: BatchLaunchItemStatus;
  feed: VideoFeed | null;
  error: string | null;
}

export interface BatchFeedLaunchSummary {
  total: number;
  created: number;
  started: number;
  failed: number;
}

export interface BatchFeedLaunchResult {
  launch_mode: BatchLaunchMode;
  runtime: Required<BatchRuntimeSettings>;
  results: BatchFeedLaunchItemResult[];
  summary: BatchFeedLaunchSummary;
}

export interface UploadVideoResponse {
  file_name: string;
  file_path: string;
  preview_path: string;
}

export interface Establishment {
  id: number;
  name: string;
  created_at: string;
}

export interface CreateEstablishmentInput {
  name: string;
}

export interface Caisse {
  id: number;
  name: string;
  establishment_id: number;
  created_at: string;
  zone: ZonePolygon | null;
}

export interface CreateCaisseInput {
  name: string;
  zone?: ZonePolygon | null;
}

export interface RTSPConnectionTestInput {
  url: string;
  username?: string | null;
  password?: string | null;
  transport?: RTSPTransport;
}

export interface RTSPConnectionTestResult {
  connected: boolean;
  transport: RTSPTransport;
  resolution: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  error: string | null;
}

export interface RTSPSnapshotInput {
  url: string;
  username?: string | null;
  password?: string | null;
  transport?: RTSPTransport;
}

export interface RTSPSnapshotResult {
  captured: boolean;
  transport: RTSPTransport;
  resolution: string | null;
  width: number | null;
  height: number | null;
  image_data_url: string | null;
  error: string | null;
}

export interface ONVIFDevice {
  ip: string;
  name: string;
  manufacturer: string;
  model: string;
  serial: string;
  hardware: string;
  location: string;
  services: Record<string, string>;
  xaddrs: string | null;
}

export interface ONVIFDiscoveryInput {
  timeout_seconds?: number;
}

export interface ONVIFStream {
  url: string;
}

export interface ONVIFStreamResolutionInput {
  device: ONVIFDevice;
  username?: string | null;
  password?: string | null;
}

export interface ONVIFCameraTestInput extends ONVIFStreamResolutionInput {
  transport?: RTSPTransport;
}

export interface ONVIFCameraTestResult {
  connected: boolean;
  transport: RTSPTransport;
  stream_count: number;
  tested_stream: ONVIFStream | null;
  streams: ONVIFStream[];
  resolution: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  error: string | null;
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "http://localhost:8000";

function buildUrl(path: string): string {
  return new URL(path, apiBaseUrl).toString();
}

export function resolveApiUrl(path: string): string {
  return buildUrl(path);
}

function buildWebSocketUrl(path: string): string {
  const url = new URL(path, apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildUrl(path);
  let response: Response;
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;

  try {
    response = await fetch(url, {
      headers: isFormData
        ? init?.headers
        : {
            "Content-Type": "application/json",
            ...(init?.headers ?? {}),
          },
      ...init,
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Unknown network error";
    throw new Error(
      `Unable to reach the backend at ${url}. Check that the FastAPI server is running and that CORS allows this frontend origin. Original error: ${reason}`,
    );
  }

  const payload = (await response.json()) as ApiResponse<T> | { detail?: string };

  if (!response.ok) {
    throw new Error("detail" in payload && payload.detail ? payload.detail : `Request failed with status ${response.status}`);
  }

  if (!("data" in payload)) {
    throw new Error("Malformed API response.");
  }

  return payload.data;
}

export function listFeeds(): Promise<VideoFeed[]> {
  return fetchApi<VideoFeed[]>("/api/feeds");
}

export function getSystemHealth(): Promise<SystemHealth> {
  return fetchApi<SystemHealth>("/api/system/health");
}

export function createFeed(input: CreateFeedInput): Promise<VideoFeed> {
  return fetchApi<VideoFeed>("/api/feeds", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function launchFeedBatch(input: BatchFeedLaunchInput): Promise<BatchFeedLaunchResult> {
  return fetchApi<BatchFeedLaunchResult>("/api/feeds/batch-launch", {
    method: "POST",
    body: JSON.stringify({
      launch_mode: input.launch_mode ?? "create_and_start",
      runtime: {
        webhook_enabled: input.runtime?.webhook_enabled ?? true,
        log_level: input.runtime?.log_level ?? "INFO",
      },
      feeds: input.feeds,
    }),
  });
}

export function startFeed(feedId: string): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/start`, {
    method: "POST",
  });
}

export function stopFeed(feedId: string): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/stop`, {
    method: "POST",
  });
}

export function restartFeed(feedId: string): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/restart`, {
    method: "POST",
  });
}

export function deleteFeed(feedId: string): Promise<{ feed_id: string }> {
  return fetchApi<{ feed_id: string }>(`/api/feeds/${feedId}`, {
    method: "DELETE",
  });
}

export function listEstablishments(): Promise<Establishment[]> {
  return fetchApi<Establishment[]>("/api/establishments");
}

export function createEstablishment(input: CreateEstablishmentInput): Promise<Establishment> {
  return fetchApi<Establishment>("/api/establishments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCaisses(establishmentId: number): Promise<Caisse[]> {
  return fetchApi<Caisse[]>(`/api/establishments/${establishmentId}/caisses`);
}

export function createCaisse(establishmentId: number, input: CreateCaisseInput): Promise<Caisse> {
  return fetchApi<Caisse>(`/api/establishments/${establishmentId}/caisses`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function testRtspConnection(input: RTSPConnectionTestInput): Promise<RTSPConnectionTestResult> {
  return fetchApi<RTSPConnectionTestResult>("/api/sources/rtsp/test", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      transport: input.transport ?? "tcp",
    }),
  });
}

export function captureRtspSnapshot(input: RTSPSnapshotInput): Promise<RTSPSnapshotResult> {
  return fetchApi<RTSPSnapshotResult>("/api/sources/rtsp/snapshot", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      transport: input.transport ?? "tcp",
    }),
  });
}

export interface FeedSnapshotResult {
  feed_id: string;
  source: string;
  captured: boolean;
  resolution: string | null;
  width: number | null;
  height: number | null;
  image_data_url: string | null;
  error: string | null;
}

export function getFeedSnapshot(feedId: string): Promise<FeedSnapshotResult> {
  return fetchApi<FeedSnapshotResult>(`/api/feeds/${feedId}/snapshot`);
}

export function discoverOnvifDevices(input?: ONVIFDiscoveryInput): Promise<ONVIFDevice[]> {
  return fetchApi<ONVIFDevice[]>("/api/sources/onvif/discover", {
    method: "POST",
    body: JSON.stringify({
      timeout_seconds: input?.timeout_seconds ?? 5,
    }),
  });
}

export function resolveOnvifStreams(input: ONVIFStreamResolutionInput): Promise<ONVIFStream[]> {
  return fetchApi<ONVIFStream[]>("/api/sources/onvif/streams", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function testOnvifCamera(input: ONVIFCameraTestInput): Promise<ONVIFCameraTestResult> {
  return fetchApi<ONVIFCameraTestResult>("/api/sources/onvif/test", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      transport: input.transport ?? "tcp",
    }),
  });
}

export function uploadVideo(file: File): Promise<UploadVideoResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return fetchApi<UploadVideoResponse>("/api/uploads/video", {
    method: "POST",
    body: formData,
  });
}

export function updateZone(feedId: string, zone: ZonePolygon): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/zone`, {
    method: "POST",
    body: JSON.stringify({ zone }),
  });
}

export function connectDashboardSocket(): WebSocket {
  return new WebSocket(buildWebSocketUrl("/ws/metrics"));
}