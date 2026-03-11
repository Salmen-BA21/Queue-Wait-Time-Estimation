import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";

import {
  AlertFiredEvent,
  connectDashboardSocket,
  DashboardSocketEvent,
  MetricsUpdateEvent,
  SystemWarningEvent,
  type VideoFeed,
} from "@/lib/api";

export const feedsQueryKey = ["feeds"] as const;
export const systemHealthQueryKey = ["system-health"] as const;

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

function updateFeedMetrics(existing: VideoFeed[], feedId: string, latestMetrics: VideoFeed["latest_metrics"]): VideoFeed[] {
  return existing.map((feed) => (feed.feed_id === feedId ? { ...feed, latest_metrics: latestMetrics } : feed));
}

function pushActivity(
  setActivity: Dispatch<SetStateAction<ActivityItem[]>>,
  item: ActivityItem,
): void {
  setActivity((current) => [item, ...current].slice(0, 8));
}

function handleMetricsUpdate(event: MetricsUpdateEvent, queryClient: QueryClient): void {
  queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) =>
    updateFeedMetrics(current, event.payload.feed_id, event.payload.metrics),
  );
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
  useEffect(() => {
    const socket = connectDashboardSocket();

    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as DashboardSocketEvent;

      if (event.event === "snapshot") {
        queryClient.setQueryData(feedsQueryKey, event.payload.feeds);
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
        handleMetricsUpdate(event, queryClient);
        return;
      }

      if (event.event === "alert_fired") {
        handleAlertFired(event, setActivity);
        return;
      }

      if (event.event === "system_warning") {
        handleSystemWarning(event, setActivity);
      }
    };

    socket.onerror = () => {
      pushActivity(setActivity, {
        id: `socket-error-${Date.now()}`,
        message: "Live dashboard connection is unavailable. Check whether the backend API is running.",
        severity: "warning",
        time: "just now",
      });
    };

    return () => {
      socket.close();
    };
  }, [queryClient, setActivity]);
}