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

export type AuthRole = "admin" | "manager";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  role: AuthRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  display_name: string;
  password: string;
}

export interface LoginResult {
  user: AuthUser;
}

export interface SessionStatus {
  authenticated: boolean;
  user: AuthUser | null;
}

export interface CreateManagerInput {
  email: string;
  display_name: string;
  password: string;
}

export interface UpdateManagerStatusInput {
  is_active: boolean;
}

export interface ResetManagerPasswordInput {
  password: string;
}

export class ApiError extends Error {
  status: number;
  url: string;
  detail: unknown;

  constructor(message: string, options: { status: number; url: string; detail?: unknown }) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.url = options.url;
    this.detail = options.detail ?? null;
  }
}

export class NetworkError extends Error {
  url: string;
  cause: unknown;

  constructor(message: string, options: { url: string; cause?: unknown }) {
    super(message);
    this.name = "NetworkError";
    this.url = options.url;
    this.cause = options.cause ?? null;
  }
}

export class ValidationError extends ApiError {
  constructor(message: string, options: { status: number; url: string; detail?: unknown }) {
    super(message, options);
    this.name = "ValidationError";
  }
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
  queue_stable: boolean;
  detections?: number[][] | null;
  render_frame_jpeg_base64?: string | null;
  backend_annotations_active?: boolean;
}

export type FeedWebRtcSourceMode = "annotated" | "direct" | "none";

export interface FeedWebRtcTransportCapability {
  enabled: boolean;
  ready: boolean;
  source_mode: FeedWebRtcSourceMode;
  path_name: string | null;
  reason: string | null;
}

export interface FeedMjpegTransportCapability {
  enabled: boolean;
  ready: boolean;
  reason: string | null;
}

export interface FeedTransportCapabilities {
  backend_annotations: boolean;
  webrtc: FeedWebRtcTransportCapability;
  mjpeg: FeedMjpegTransportCapability;
}

export interface QueueAlert {
  alert_type: string;
  severity: "warning";
  message: string;
  threshold_name: string;
  current_value: number;
  threshold_value: number;
  frame_id: number;
  timestamp: string;
}

export interface StatisticsDateRange {
  from_date: string | null;
  to_date: string | null;
}

export interface StatisticsOverview {
  date_range: StatisticsDateRange;
  avg_wait_time: number;
  peak_queue_length: number;
  stability_score: number;
  total_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  avg_people_in_zone: number;
  avg_service_rate: number;
  avg_arrival_rate: number;
}

export interface ZoneStatisticsItem {
  camera_id: string | null;
  zone_id: string | null;
  total_alerts: number;
  avg_wait_time: number;
  max_wait_time: number;
  min_wait_time: number;
  avg_people_in_zone: number;
  peak_queue_length: number;
  avg_service_rate: number;
  stability_score: number;
  critical_alerts: number;
  warning_alerts: number;
}

export interface TimeSeriesStatisticsItem {
  period: string;
  alert_count: number;
  avg_wait_time: number;
  peak_queue_length: number;
  stability_score: number;
  avg_service_rate: number;
  avg_arrival_rate: number;
}

export interface AlertDistributionItem {
  alert_type: string;
  severity: string;
  count: number;
  percentage: number;
}

export interface StatisticsFilters {
  from?: string | null;
  to?: string | null;
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
  queue_length_warning: number;
  latest_metrics: QueueMetrics | null;
  transport?: FeedTransportCapabilities | null;
  last_error: string | null;
  last_warning: string | null;
  last_warning_code: string | null;
}

function buildStatisticsQuery(filters?: StatisticsFilters): string {
  const params = new URLSearchParams();
  if (filters?.from) {
    params.set("from", filters.from);
  }
  if (filters?.to) {
    params.set("to", filters.to);
  }
  return params.toString();
}

export interface QueueThresholdUpdateInput {
  queue_length_warning: number;
}

export interface FeedSourceUpdateInput {
  source: string;
  rtsp_username?: string | null;
  rtsp_password?: string | null;
  rtsp_transport?: RTSPTransport | null;
  restart_if_running?: boolean;
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

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
          return item.msg;
        }

        return null;
      })
      .filter((value): value is string => Boolean(value));

    return messages.length > 0 ? messages.join("; ") : null;
  }

  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    return detail.message;
  }

  return null;
}

async function parseResponsePayload<T>(response: Response): Promise<ApiResponse<T> | { detail?: unknown } | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return (await response.json()) as ApiResponse<T> | { detail?: unknown };
  } catch {
    return null;
  }
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildUrl(path);
  let response: Response;
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;

  try {
    response = await fetch(url, {
      credentials: "include",
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
    throw new NetworkError(
      `Unable to reach the backend at ${url}. Check that the FastAPI server is running and that CORS allows this frontend origin. Original error: ${reason}`,
      { url, cause: error },
    );
  }

  const payload = await parseResponsePayload<T>(response);

  if (!response.ok) {
    const detail = payload && "detail" in payload ? payload.detail : null;
    const message = formatApiDetail(detail) ?? `Request failed with status ${response.status}`;

    if (response.status === 400 || response.status === 422) {
      throw new ValidationError(message, {
        status: response.status,
        url,
        detail,
      });
    }

    throw new ApiError(message, {
      status: response.status,
      url,
      detail,
    });
  }

  if (!payload || !("data" in payload)) {
    throw new ApiError("Malformed API response.", {
      status: response.status,
      url,
      detail: payload,
    });
  }

  return payload.data;
}

export function login(input: LoginInput): Promise<LoginResult> {
  return fetchApi<LoginResult>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function register(input: RegisterInput): Promise<LoginResult> {
  return fetchApi<LoginResult>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function refreshSession(): Promise<LoginResult> {
  return fetchApi<LoginResult>("/api/auth/refresh", {
    method: "POST",
  });
}

export function logout(): Promise<{ logged_out: boolean }> {
  return fetchApi<{ logged_out: boolean }>("/api/auth/logout", {
    method: "POST",
  });
}

export function getCurrentSession(): Promise<SessionStatus> {
  return fetchApi<SessionStatus>("/api/auth/me");
}

export function listManagers(): Promise<AuthUser[]> {
  return fetchApi<AuthUser[]>("/api/admin/managers");
}

export function createManager(input: CreateManagerInput): Promise<AuthUser> {
  return fetchApi<AuthUser>("/api/admin/managers", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateManagerStatus(userId: number, input: UpdateManagerStatusInput): Promise<AuthUser> {
  return fetchApi<AuthUser>(`/api/admin/managers/${userId}/status`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function resetManagerPassword(userId: number, input: ResetManagerPasswordInput): Promise<{ password_reset: boolean }> {
  return fetchApi<{ password_reset: boolean }>(`/api/admin/managers/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listFeeds(): Promise<VideoFeed[]> {
  return fetchApi<VideoFeed[]>("/api/feeds");
}

export function getSystemHealth(): Promise<SystemHealth> {
  return fetchApi<SystemHealth>("/api/system/health");
}

export function getStatisticsOverview(filters?: StatisticsFilters): Promise<StatisticsOverview> {
  const query = buildStatisticsQuery(filters);
  return fetchApi<StatisticsOverview>(query ? `/api/statistics/overview?${query}` : "/api/statistics/overview");
}

export function getZoneStatistics(filters?: StatisticsFilters): Promise<ZoneStatisticsItem[]> {
  const query = buildStatisticsQuery(filters);
  return fetchApi<ZoneStatisticsItem[]>(query ? `/api/statistics/by-zone?${query}` : "/api/statistics/by-zone");
}

export function getTimeBasedStatistics(
  period: "hourly" | "daily" | "weekly" = "daily",
  filters?: StatisticsFilters,
): Promise<TimeSeriesStatisticsItem[]> {
  const query = buildStatisticsQuery(filters);
  const baseQuery = `period=${encodeURIComponent(period)}`;
  const fullQuery = query ? `${baseQuery}&${query}` : baseQuery;
  return fetchApi<TimeSeriesStatisticsItem[]>(`/api/statistics/by-time?${fullQuery}`);
}

export function getAlertDistributionStatistics(filters?: StatisticsFilters): Promise<AlertDistributionItem[]> {
  const query = buildStatisticsQuery(filters);
  return fetchApi<AlertDistributionItem[]>(query ? `/api/statistics/alerts?${query}` : "/api/statistics/alerts");
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

export type WebRTCSessionType = "offer" | "answer";

export interface WebRTCSessionDescription {
  type: WebRTCSessionType;
  sdp: string;
}

export interface FeedWebRtcOfferInput {
  offer: WebRTCSessionDescription;
}

export interface FeedWebRtcOfferResult {
  answer: WebRTCSessionDescription;
}

export function getFeedSnapshot(feedId: string): Promise<FeedSnapshotResult> {
  return fetchApi<FeedSnapshotResult>(`/api/feeds/${feedId}/snapshot`);
}

export function submitFeedWebRtcOffer(feedId: string, input: FeedWebRtcOfferInput): Promise<FeedWebRtcOfferResult> {
  return fetchApi<FeedWebRtcOfferResult>(`/api/feeds/${feedId}/webrtc/offer`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getFeedTransportCapabilities(feedId: string): Promise<FeedTransportCapabilities> {
  return fetchApi<FeedTransportCapabilities>(`/api/feeds/${feedId}/transport`);
}

export function getFeedMjpegStreamUrl(feedId: string): string {
  return buildUrl(`/api/feeds/${feedId}/stream`);
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

export function updateFeedThresholds(feedId: string, input: QueueThresholdUpdateInput): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/thresholds`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateFeedSource(feedId: string, input: FeedSourceUpdateInput): Promise<VideoFeed> {
  return fetchApi<VideoFeed>(`/api/feeds/${feedId}/source`, {
    method: "POST",
    body: JSON.stringify({
      ...input,
      restart_if_running: input.restart_if_running ?? true,
    }),
  });
}

export function connectDashboardSocket(): WebSocket {
  return new WebSocket(buildWebSocketUrl("/ws/metrics"));
}
