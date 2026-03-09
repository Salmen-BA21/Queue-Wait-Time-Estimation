import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  connectDashboardSocket,
  createFeed,
  DashboardSocketEvent,
  getSystemHealth,
  listFeeds,
  restartFeed,
  startFeed,
  stopFeed,
  updateZone,
  VideoFeed,
} from "@/lib/api";

const feedsQueryKey = ["feeds"] as const;
const systemHealthQueryKey = ["system-health"] as const;

export interface ActivityItem {
  id: string;
  message: string;
  severity: "info" | "warning" | "success";
  time: string;
}

function upsertFeed(existing: VideoFeed[], incoming: VideoFeed): VideoFeed[] {
  const index = existing.findIndex((feed) => feed.feed_id === incoming.feed_id);
  if (index === -1) {
    return [incoming, ...existing];
  }

  return existing.map((feed, currentIndex) => (currentIndex === index ? incoming : feed));
}

function removeFeed(existing: VideoFeed[], feedId: string): VideoFeed[] {
  return existing.filter((feed) => feed.feed_id !== feedId);
}

function toRelativeTime(isoTimestamp: string): string {
  const deltaMs = Date.now() - new Date(isoTimestamp).getTime();
  const minutes = Math.max(0, Math.round(deltaMs / 60000));
  if (minutes <= 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours} h ago`;
}

function pushActivity(
  setActivity: React.Dispatch<React.SetStateAction<ActivityItem[]>>,
  item: ActivityItem,
): void {
  setActivity((current) => [item, ...current].slice(0, 8));
}

export function useLiveDashboard() {
  const queryClient = useQueryClient();
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  const feedsQuery = useQuery({
    queryKey: feedsQueryKey,
    queryFn: listFeeds,
  });

  const systemHealthQuery = useQuery({
    queryKey: systemHealthQueryKey,
    queryFn: getSystemHealth,
    refetchInterval: 15000,
  });

  const createFeedMutation = useMutation({
    mutationFn: createFeed,
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
      pushActivity(setActivity, {
        id: `local-create-${feed.feed_id}`,
        message: `${feed.name} was added to the surveillance grid.`,
        severity: "success",
        time: "just now",
      });
    },
  });

  const updateZoneMutation = useMutation({
    mutationFn: ({ feedId, zone }: { feedId: string; zone: { points: Array<{ x: number; y: number }> } }) =>
      updateZone(feedId, zone),
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      pushActivity(setActivity, {
        id: `zone-update-${feed.feed_id}`,
        message: `Zone updated for ${feed.name}.`,
        severity: "info",
        time: "just now",
      });
    },
  });

  const startFeedMutation = useMutation({
    mutationFn: (feedId: string) => startFeed(feedId),
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
      pushActivity(setActivity, {
        id: `start-${feed.feed_id}-${Date.now()}`,
        message: `${feed.name} was started.`,
        severity: "success",
        time: "just now",
      });
    },
  });

  const stopFeedMutation = useMutation({
    mutationFn: (feedId: string) => stopFeed(feedId),
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
      pushActivity(setActivity, {
        id: `stop-${feed.feed_id}-${Date.now()}`,
        message: `${feed.name} was stopped.`,
        severity: "warning",
        time: "just now",
      });
    },
  });

  const restartFeedMutation = useMutation({
    mutationFn: (feedId: string) => restartFeed(feedId),
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
      pushActivity(setActivity, {
        id: `restart-${feed.feed_id}-${Date.now()}`,
        message: `${feed.name} was restarted.`,
        severity: "info",
        time: "just now",
      });
    },
  });

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
  }, [queryClient]);

  const feeds = feedsQuery.data ?? [];

  const derived = useMemo(() => {
    const registeredFeeds = feeds.length;
    const onlineFeeds = feeds.filter((feed) => feed.status === "running").length;
    const peopleTotal = feeds.reduce((total, feed) => total + (feed.latest_metrics?.people_in_zone ?? 0), 0);
    const feedWaitTimes = feeds
      .map((feed) => feed.latest_metrics?.wait_time_seconds)
      .filter((value): value is number => typeof value === "number");
    const averageWaitTime = feedWaitTimes.length
      ? feedWaitTimes.reduce((total, value) => total + value, 0) / feedWaitTimes.length
      : 0;

    return {
      registeredFeeds,
      onlineFeeds,
      peopleTotal,
      averageWaitTime,
      waitChartData: feeds.map((feed) => ({
        name: feed.name,
        value: feed.latest_metrics?.wait_time_seconds ?? 0,
      })),
      queueChartData: feeds.map((feed) => ({
        name: feed.name,
        count: feed.latest_metrics?.people_in_zone ?? 0,
      })),
    };
  }, [feeds]);

  const activityFeed = activity.map((item) => ({
    ...item,
    time: item.time === "just now" ? item.time : toRelativeTime(item.time),
  }));

  return {
    feeds,
    feedsQuery,
    systemHealthQuery,
    createFeedMutation,
    updateZoneMutation,
    startFeedMutation,
    stopFeedMutation,
    restartFeedMutation,
    activity: activityFeed,
    derived,
  };
}