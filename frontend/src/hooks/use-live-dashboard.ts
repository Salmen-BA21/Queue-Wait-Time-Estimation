import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createFeed,
  deleteFeed,
  getSystemHealth,
  listFeeds,
  restartFeed,
  startFeed,
  stopFeed,
  updateFeedThresholds,
  updateZone,
  VideoFeed,
} from "@/lib/api";
import {
  ActivityItem,
  feedsQueryKey,
  removeFeed,
  systemHealthQueryKey,
  upsertFeed,
  useDashboardWebsocket,
} from "@/hooks/use-dashboard-websocket";

const statisticsQueryKeys = [
  ["statistics-overview"],
  ["statistics-zones"],
  ["statistics-time"],
  ["statistics-alerts"],
] as const;

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

function pushActivity(setActivity: React.Dispatch<React.SetStateAction<ActivityItem[]>>, item: ActivityItem): void {
  setActivity((current) => [item, ...current].slice(0, 8));
}

export function useLiveDashboard() {
  const queryClient = useQueryClient();
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  const invalidateStatisticsQueries = () => {
    for (const queryKey of statisticsQueryKeys) {
      void queryClient.invalidateQueries({ queryKey });
    }
  };

  useDashboardWebsocket({ queryClient, setActivity });

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
      invalidateStatisticsQueries();
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
      invalidateStatisticsQueries();
      pushActivity(setActivity, {
        id: `zone-update-${feed.feed_id}`,
        message: `Zone updated for ${feed.name}.`,
        severity: "info",
        time: "just now",
      });
    },
  });

  const updateThresholdMutation = useMutation({
    mutationFn: ({
      feedId,
      queueLengthWarning,
    }: {
      feedId: string;
      queueLengthWarning: number;
    }) => updateFeedThresholds(feedId, {
      queue_length_warning: queueLengthWarning,
    }),
    onSuccess: (feed) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => upsertFeed(current, feed));
      invalidateStatisticsQueries();
      pushActivity(setActivity, {
        id: `threshold-update-${feed.feed_id}`,
        message: `Queue thresholds updated for ${feed.name}.`,
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

  const deleteFeedMutation = useMutation({
    mutationFn: (feedId: string) => deleteFeed(feedId),
    onSuccess: ({ feed_id: feedId }) => {
      queryClient.setQueryData<VideoFeed[]>(feedsQueryKey, (current = []) => removeFeed(current, feedId));
      void queryClient.invalidateQueries({ queryKey: systemHealthQueryKey });
      invalidateStatisticsQueries();
      pushActivity(setActivity, {
        id: `delete-${feedId}-${Date.now()}`,
        message: "A feed was removed from the surveillance wall.",
        severity: "warning",
        time: "just now",
      });
    },
  });

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
      liveMonitoring: {
        attentionFeedCount: feeds.filter(
          (feed) =>
            feed.status === "error"
            || Boolean(feed.last_error)
            || Boolean(feed.last_warning),
        ).length,
        feedsWithRuntimeErrors: feeds.filter((feed) => feed.status === "error" || Boolean(feed.last_error)),
        feedsWithRuntimeWarnings: feeds.filter((feed) => Boolean(feed.last_warning)),
      },
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
    updateThresholdMutation,
    startFeedMutation,
    stopFeedMutation,
    restartFeedMutation,
    deleteFeedMutation,
    activity: activityFeed,
    derived,
  };
}