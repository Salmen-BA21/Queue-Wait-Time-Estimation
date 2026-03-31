import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";

import {
  AlertFiredEvent,
  connectDashboardSocket,
  DashboardSocketEvent,
  listFeeds,
  MetricsUpdateEvent,
  SystemWarningEvent,
  type VideoFeed,
} from "@/lib/api";

export const feedsQueryKey = ["feeds"] as const;
export const systemHealthQueryKey = ["system-health"] as const;

const SOCKET_RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000, 30000] as const;
const METRICS_FLUSH_INTERVAL_MS = 120;
const SOCKET_HEARTBEAT_INTERVAL_MS = 10000;
const METRICS_STALE_THRESHOLD_MS = 2000;
const FALLBACK_POLL_INTERVAL_MS = 800;

export interface ActivityItem {
  id: string;
  message: string;
  severity: "info" | "warning" | "success" | "critical";
  time: string;
}

export function upsertFeed(existing: VideoFeed[], incoming: VideoFeed): VideoFeed[] {
  const index = existing.findIndex((feed) => feed.feed_id === incoming.feed_id);
  if (index === -1) {
    return [incoming, ...existing];
  }

  return existing.map((feed, currentIndex) => (currentIndex === index ? incoming : feed));
}

export function removeFeed(existing: VideoFeed[], feedId: string): VideoFeed[] {
  return existing.filter((feed) => feed.feed_id !== feedId);
}

function applyMetricsBatch(
  existing: VideoFeed[],
  updatesByFeedId: Map<string, VideoFeed["latest_metrics"]>,
): VideoFeed[] {
  if (existing.length === 0 || updatesByFeedId.size === 0) {
    return existing;
  }

  let changed = false;
  const next = existing.map((feed) => {
    const latestMetrics = updatesByFeedId.get(feed.feed_id);
    if (!latestMetrics) {
      return feed;
    }
    changed = true;
    return { ...feed, latest_metrics: latestMetrics };
  });

  return changed ? next : existing;
}

function pushActivity(
  setActivity: Dispatch<SetStateAction<ActivityItem[]>>,
  item: ActivityItem,
): void {
  setActivity((current) => [item, ...current].slice(0, 8));
}

function handleAlertFired(event: AlertFiredEvent, setActivity: Dispatch<SetStateAction<ActivityItem[]>>): void {
  const { alert, feed_id: feedId } = event.payload;
  pushActivity(setActivity, {
    id: `alert-${feedId}-${alert.alert_type}-${alert.frame_id}`,
    message: alert.message,
    severity: alert.severity,
    time: alert.timestamp,
  });
}

function handleSystemWarning(event: SystemWarningEvent, setActivity: Dispatch<SetStateAction<ActivityItem[]>>): void {
  pushActivity(setActivity, {
    id: `warning-${event.payload.feed_id}-${event.payload.code}-${event.payload.timestamp}`,
    message: event.payload.message,
    severity: "warning",
    time: event.payload.timestamp,
  });
}

/**
 * Subscribes the dashboard to websocket updates and fans incoming events into the query cache and activity stream.
 */
export function useDashboardWebsocket({
  queryClient,
  setActivity,
}: {
  queryClient: QueryClient;
  setActivity: Dispatch<SetStateAction<ActivityItem[]>>;
}) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const metricsFlushTimerRef = useRef<number | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const staleWatchdogTimerRef = useRef<number | null>(null);
  const fallbackPollTimerRef = useRef<number | null>(null);
  const fallbackPollInFlightRef = useRef(false);
  const fallbackActiveRef = useRef(false);
  const fallbackNoticeShownRef = useRef(false);
  const lastMetricsAtRef = useRef<number>(Date.now());
  const pendingMetricsRef = useRef<Map<string, VideoFeed["latest_metrics"]>>(new Map());
  const unmountedRef = useRef(false);
  const offlineWarningShownRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;

    function clearReconnectTimer(): void {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }

    function clearHeartbeatTimer(): void {
      if (heartbeatTimerRef.current !== null) {
        window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    }

    function clearStaleWatchdogTimer(): void {
      if (staleWatchdogTimerRef.current !== null) {
        window.clearInterval(staleWatchdogTimerRef.current);
        staleWatchdogTimerRef.current = null;
      }
    }

    function clearFallbackPollingTimer(): void {
      if (fallbackPollTimerRef.current !== null) {
        window.clearInterval(fallbackPollTimerRef.current);
        fallbackPollTimerRef.current = null;
      }
      fallbackActiveRef.current = false;
      fallbackPollInFlightRef.current = false;
    }

    function hasRunningFeeds(): boolean {
      const feeds = queryClient.getQueryData<VideoFeed[]>(feedsQueryKey) ?? [];
      return feeds.some((feed) => feed.status === "running" || feed.status === "initializing");
    }

    function stopFallbackPolling(): void {
      clearFallbackPollingTimer();
    }

    function startFallbackPolling(): void {
      if (fallbackActiveRef.current || unmountedRef.current) {
        return;
      }

      if (!hasRunningFeeds()) {
        return;
      }

      fallbackActiveRef.current = true;

      if (!fallbackNoticeShownRef.current) {
        pushActivity(setActivity, {
          id: `fallback-polling-${Date.now()}`,
          message: "Live websocket is delayed. Using automatic polling fallback.",
          severity: "warning",
          time: "just now",
        });
        fallbackNoticeShownRef.current = true;
      }

      fallbackPollTimerRef.current = window.setInterval(async () => {
        if (unmountedRef.current || fallbackPollInFlightRef.current) {
          return;
        }

        if (!hasRunningFeeds()) {
          stopFallbackPolling();
          return;
        }

        fallbackPollInFlightRef.current = true;
        try {
          const feeds = await listFeeds();
          if (unmountedRef.current) {
            return;
          }

          queryClient.setQueryData(feedsQueryKey, feeds);

          // Keep the UI alive during websocket degradation by treating successful
          // fallback snapshots as fresh feed activity.
          if (feeds.some((feed) => feed.latest_metrics)) {
            lastMetricsAtRef.current = Date.now();
          }
        } catch {
          // Keep retrying while fallback mode is active.
        } finally {
          fallbackPollInFlightRef.current = false;
        }
      }, FALLBACK_POLL_INTERVAL_MS);
    }

    function ensureStaleWatchdogLoop(): void {
      if (staleWatchdogTimerRef.current !== null) {
        return;
      }

      staleWatchdogTimerRef.current = window.setInterval(() => {
        if (unmountedRef.current) {
          return;
        }

        if (!hasRunningFeeds()) {
          stopFallbackPolling();
          return;
        }

        const socketReady = socketRef.current?.readyState === WebSocket.OPEN;
        const staleForMs = Date.now() - lastMetricsAtRef.current;
        const stale = staleForMs > METRICS_STALE_THRESHOLD_MS;

        if (!socketReady || stale) {
          startFallbackPolling();
          return;
        }

        stopFallbackPolling();
      }, 1000);
    }

    function flushPendingMetrics(): void {
      if (pendingMetricsRef.current.size === 0) {
        return;
      }

      const updates = new Map(pendingMetricsRef.current);
      pendingMetricsRef.current.clear();

      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => applyMetricsBatch(current, updates));
    }

    function ensureMetricsFlushLoop(): void {
      if (metricsFlushTimerRef.current !== null) {
        return;
      }

      metricsFlushTimerRef.current = window.setInterval(() => {
        flushPendingMetrics();
      }, METRICS_FLUSH_INTERVAL_MS);
    }

    function scheduleReconnect(): void {
      if (unmountedRef.current || reconnectTimerRef.current !== null) {
        return;
      }

      const delay = SOCKET_RECONNECT_DELAYS_MS[
        Math.min(reconnectAttemptRef.current, SOCKET_RECONNECT_DELAYS_MS.length - 1)
      ];
      reconnectAttemptRef.current += 1;

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    }

    function handleSocketMessage(message: MessageEvent<string>): void {
      const event = JSON.parse(message.data) as DashboardSocketEvent;

      if (event.event === "snapshot") {
        queryClient.setQueryData(feedsQueryKey, event.payload.feeds);
        if (event.payload.feeds.some((feed) => feed.latest_metrics)) {
          lastMetricsAtRef.current = Date.now();
        }
        return;
      }

      if (event.event === "feed_status") {
        const { action, feed, feed_id: feedId } = event.payload;

        if (action === "deleted" && feedId) {
          queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => removeFeed(current, feedId));
          pushActivity(setActivity, {
            id: `deleted-${feedId}-${Date.now()}`,
            message: "A feed was removed from the surveillance wall.",
            severity: "warning",
            time: "just now",
          });
        }

        if ((action === "created" || action === "updated") && feed) {
          queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
          pushActivity(setActivity, {
            id: `${action}-${feed.feed_id}-${Date.now()}`,
            message: action === "created"
              ? `${feed.name} is now available in the surveillance wall.`
              : `${feed.name} was updated.`,
            severity: action === "created" ? "success" : "info",
            time: "just now",
          });
        }

        void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
        return;
      }

      if (event.event === "metrics_update") {
        const metricsEvent = event as MetricsUpdateEvent;
        lastMetricsAtRef.current = Date.now();
        pendingMetricsRef.current.set(metricsEvent.payload.feed_id, metricsEvent.payload.metrics);
        ensureMetricsFlushLoop();
        if (fallbackActiveRef.current) {
          stopFallbackPolling();
          pushActivity(setActivity, {
            id: `websocket-recovered-${Date.now()}`,
            message: "Live websocket recovered. Returning to real-time stream.",
            severity: "success",
            time: "just now",
          });
        }
        return;
      }

      if (event.event === "alert_fired") {
        handleAlertFired(event as AlertFiredEvent, setActivity);
        return;
      }

      if (event.event === "system_warning") {
        handleSystemWarning(event as SystemWarningEvent, setActivity);
      }
    }

    function connect(): void {
      if (unmountedRef.current) {
        return;
      }

      const socket = connectDashboardSocket();
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        offlineWarningShownRef.current = false;
        lastMetricsAtRef.current = Date.now();

        clearHeartbeatTimer();
        heartbeatTimerRef.current = window.setInterval(() => {
          if (socket.readyState !== WebSocket.OPEN) {
            return;
          }
          socket.send("ping");
        }, SOCKET_HEARTBEAT_INTERVAL_MS);
      };

      socket.onmessage = handleSocketMessage;

      socket.onerror = () => {
        socket.close();
      };

      socket.onclose = () => {
        clearHeartbeatTimer();
        startFallbackPolling();

        if (unmountedRef.current) {
          return;
        }

        if (!offlineWarningShownRef.current) {
          pushActivity(setActivity, {
            id: `socket-offline-${Date.now()}`,
            message: "Live dashboard connection dropped. Reconnecting automatically.",
            severity: "warning",
            time: "just now",
          });
          offlineWarningShownRef.current = true;
        }

        scheduleReconnect();
      };
    }

    connect();
    ensureStaleWatchdogLoop();

    return () => {
      unmountedRef.current = true;
      clearReconnectTimer();

      if (metricsFlushTimerRef.current !== null) {
        window.clearInterval(metricsFlushTimerRef.current);
        metricsFlushTimerRef.current = null;
      }

      clearHeartbeatTimer();
      clearStaleWatchdogTimer();
      clearFallbackPollingTimer();

      flushPendingMetrics();

      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [queryClient, setActivity]);
}