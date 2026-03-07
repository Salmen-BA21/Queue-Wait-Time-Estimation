export type FeedStatus = "created" | "initializing" | "running" | "stopped" | "error";

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

export interface VideoFeed {
  feed_id: string;
  name: string;
  source: string;
  status: FeedStatus;
  created_at: string;
  updated_at: string;
  establishment_id: number | null;
  caisse_id: number | null;
  zone: ZonePolygon | null;
  latest_metrics: QueueMetrics | null;
  last_error: string | null;
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

export type DashboardSocketEvent = FeedSnapshotEvent | FeedStatusEvent;

export interface CreateFeedInput {
  name: string;
  source: string;
  establishment_id?: number | null;
  caisse_id?: number | null;
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "http://localhost:8000";

function buildUrl(path: string): string {
  return new URL(path, apiBaseUrl).toString();
}

function buildWebSocketUrl(path: string): string {
  const url = new URL(path, apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildUrl(path);
  let response: Response;

  try {
    response = await fetch(url, {
      headers: {
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

export function connectDashboardSocket(): WebSocket {
  return new WebSocket(buildWebSocketUrl("/ws/metrics"));
}