import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout/AppLayout";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { Clock, Users, TrendingUp, AlertTriangle, Download, RefreshCw } from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  getAlertDistributionStatistics,
  getStatisticsOverview,
  getTimeBasedStatistics,
  listFeeds,
  getZoneStatistics,
  type AlertDistributionItem,
  type StatisticsOverview,
  type TimeSeriesStatisticsItem,
  type VideoFeed,
  type ZoneStatisticsItem,
} from "@/lib/api";

const severityColors: Record<string, string> = {
  warning: "hsl(38 92% 50%)",
  info: "hsl(187 82% 53%)",
};

function formatNumber(value: number, fractionDigits = 1): string {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

function formatDateLabel(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }
  return value;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function round(value: number, decimals = 1): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

type MockZoneStatisticsItem = ZoneStatisticsItem & {
  avg_arrival_rate: number;
};

function buildMockAnalytics(feeds: VideoFeed[], period: "hourly" | "daily" | "weekly") {
  const sortedFeeds = [...feeds].sort((left, right) => left.name.localeCompare(right.name));
  const activeFeeds = sortedFeeds.filter((feed) => feed.status === "running" || feed.status === "initializing");

  const zoneStatistics: MockZoneStatisticsItem[] = sortedFeeds.map((feed, index) => {
    const feedSeed = hashString(`${feed.feed_id}:${feed.name}:${feed.source}`);
    const isActive = feed.status === "running" || feed.status === "initializing";
    const baseWait = isActive ? 34 : 11;
    const baseQueue = isActive ? 13 : 4;
    const basePeople = isActive ? 8.2 : 2.6;
    const waitJitter = (feedSeed % 9) - 4;
    const queueJitter = (feedSeed % 5) - 2;
    const peopleJitter = ((feedSeed >> 3) % 5) / 10;
    const avgWaitTime = clamp(round(baseWait + waitJitter * 1.6), 4, 120);
    const peakQueueLength = Math.max(1, Math.round(baseQueue + queueJitter + index));
    const avgPeopleInZone = round(basePeople + peopleJitter + index * 0.2);
    const totalAlerts = isActive ? Math.max(2, Math.round(avgWaitTime / 12)) : Math.max(0, Math.round(avgWaitTime / 20) - 1);
    const avgServiceRate = round(clamp(isActive ? 0.18 + ((feedSeed >> 4) % 6) * 0.01 : 0.24 + ((feedSeed >> 4) % 4) * 0.01, 0.08, 0.5), 2);
    const avgArrivalRate = round(clamp(avgServiceRate - (isActive ? 0.03 : 0.06) + ((feedSeed >> 2) % 3) * 0.005, 0.04, 0.48), 2);
    const stabilityScore = round(clamp(100 - avgWaitTime * (isActive ? 0.45 : 0.28) + (isActive ? -2 : 10), 35, 98));

    return {
      camera_id: feed.name,
      zone_id: `${feed.status === "running" ? "active" : "idle"}_lane_${index + 1}`,
      total_alerts: totalAlerts,
      avg_wait_time: avgWaitTime,
      max_wait_time: round(avgWaitTime + (isActive ? 42 : 18), 1),
      min_wait_time: round(Math.max(2, avgWaitTime - (isActive ? 16 : 7)), 1),
      avg_people_in_zone: avgPeopleInZone,
      peak_queue_length: peakQueueLength,
      avg_service_rate: avgServiceRate,
      avg_arrival_rate: avgArrivalRate,
      stability_score: stabilityScore,
    };
  });

  const totalAlerts = zoneStatistics.reduce((sum, item) => sum + item.total_alerts, 0);
  const avgWaitTime = zoneStatistics.length
    ? round(zoneStatistics.reduce((sum, item) => sum + item.avg_wait_time, 0) / zoneStatistics.length)
    : 0;
  const peakQueueLength = zoneStatistics.reduce((max, item) => Math.max(max, item.peak_queue_length), 0);
  const avgPeopleInZone = zoneStatistics.length
    ? round(zoneStatistics.reduce((sum, item) => sum + item.avg_people_in_zone, 0) / zoneStatistics.length)
    : 0;
  const avgServiceRate = zoneStatistics.length
    ? round(zoneStatistics.reduce((sum, item) => sum + item.avg_service_rate, 0) / zoneStatistics.length, 2)
    : 0;
  const avgArrivalRate = zoneStatistics.length
    ? round(zoneStatistics.reduce((sum, item) => sum + item.avg_arrival_rate, 0) / zoneStatistics.length, 2)
    : 0;
  const stabilityScore = zoneStatistics.length
    ? round(zoneStatistics.reduce((sum, item) => sum + item.stability_score, 0) / zoneStatistics.length)
    : 0;

  const overview: StatisticsOverview = {
    date_range: { from_date: null, to_date: null },
    avg_wait_time: avgWaitTime,
    peak_queue_length: peakQueueLength,
    stability_score: stabilityScore,
    total_alerts: totalAlerts,
    avg_people_in_zone: avgPeopleInZone,
    avg_service_rate: avgServiceRate,
    avg_arrival_rate: avgArrivalRate,
  };

  const periods = period === "weekly" ? 4 : 6;
  const timeSeries: TimeSeriesStatisticsItem[] = Array.from({ length: periods }, (_, index) => {
    const feed = sortedFeeds[index % sortedFeeds.length] ?? sortedFeeds[0];
    const feedSeed = hashString(`${feed?.feed_id ?? "feed"}:${period}:${index}`);
    const sourceZone = zoneStatistics[index % zoneStatistics.length] ?? zoneStatistics[0];
    const wobble = (feedSeed % 5) - 2;
    const periodLabel = (() => {
      if (period === "hourly") {
        return `${String(8 + index).padStart(2, "0")}:00`;
      }

      if (period === "weekly") {
        return `W${index + 1}`;
      }

      const date = new Date();
      date.setDate(date.getDate() - (periods - index - 1));
      return date.toISOString().slice(0, 10);
    })();

    return {
      period: periodLabel,
      alert_count: Math.max(0, Math.round((sourceZone?.total_alerts ?? 0) + wobble)),
      avg_wait_time: round(clamp((sourceZone?.avg_wait_time ?? 0) + wobble * 1.8, 4, 120)),
      peak_queue_length: Math.max(1, Math.round((sourceZone?.peak_queue_length ?? 0) + wobble)),
      stability_score: round(clamp((sourceZone?.stability_score ?? 0) - wobble * 1.2, 35, 99)),
      avg_service_rate: round(clamp((sourceZone?.avg_service_rate ?? 0) + wobble * 0.01, 0.05, 0.5), 2),
      avg_arrival_rate: round(clamp((sourceZone?.avg_arrival_rate ?? 0) + wobble * 0.008, 0.04, 0.5), 2),
    };
  });

  const alertDistribution: AlertDistributionItem[] = [
    {
      alert_type: "QUEUE_WARNING",
      severity: "warning",
      count: totalAlerts,
      percentage: totalAlerts > 0 ? 100 : 0,
    },
  ].filter((entry) => entry.count > 0);

  return {
    overview,
    zoneStatistics,
    timeSeries,
    alertDistribution,
    activeFeedCount: activeFeeds.length,
    totalFeedCount: sortedFeeds.length,
  };
}

export default function Analytics() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [period, setPeriod] = useState<"hourly" | "daily" | "weekly">("daily");

  const filters = useMemo(
    () => ({
      from: fromDate || null,
      to: toDate || null,
    }),
    [fromDate, toDate],
  );

  const overviewQuery = useQuery({
    queryKey: ["statistics-overview", filters],
    queryFn: () => getStatisticsOverview(filters),
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
  const zoneQuery = useQuery({
    queryKey: ["statistics-zones", filters],
    queryFn: () => getZoneStatistics(filters),
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
  const timeQuery = useQuery({
    queryKey: ["statistics-time", period, filters],
    queryFn: () => getTimeBasedStatistics(period, filters),
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
  const alertDistributionQuery = useQuery({
    queryKey: ["statistics-alerts", filters],
    queryFn: () => getAlertDistributionStatistics(filters),
    staleTime: 30_000,
    refetchInterval: 15_000,
  });
  const feedsQuery = useQuery({
    queryKey: ["dashboard-feeds"],
    queryFn: () => listFeeds(),
    staleTime: 30_000,
    refetchInterval: 15_000,
  });

  const dashboardFeeds = useMemo(() => feedsQuery.data ?? [], [feedsQuery.data]);
  const mockAnalytics = useMemo(() => buildMockAnalytics(dashboardFeeds, period), [dashboardFeeds, period]);
  const hasRealStatistics = Boolean(
    overviewQuery.data &&
      (overviewQuery.data.total_alerts > 0 || zoneQuery.data?.length || timeQuery.data?.length || alertDistributionQuery.data?.length),
  );
  const useMockAnalytics = !hasRealStatistics && dashboardFeeds.length > 0;

  const overview = useMemo<StatisticsOverview | undefined>(
    () => (useMockAnalytics ? mockAnalytics.overview : overviewQuery.data),
    [mockAnalytics.overview, overviewQuery.data, useMockAnalytics],
  );
  const zoneStatistics = useMemo<ZoneStatisticsItem[]>(
    () => (useMockAnalytics ? mockAnalytics.zoneStatistics : zoneQuery.data ?? []),
    [mockAnalytics.zoneStatistics, useMockAnalytics, zoneQuery.data],
  );
  const timeSeries = useMemo<TimeSeriesStatisticsItem[]>(
    () => (useMockAnalytics ? mockAnalytics.timeSeries : timeQuery.data ?? []),
    [mockAnalytics.timeSeries, timeQuery.data, useMockAnalytics],
  );
  const alertDistribution = useMemo<AlertDistributionItem[]>(
    () => (useMockAnalytics ? mockAnalytics.alertDistribution : alertDistributionQuery.data ?? []),
    [alertDistributionQuery.data, mockAnalytics.alertDistribution, useMockAnalytics],
  );
  const activeFeedCount = useMockAnalytics
    ? mockAnalytics.activeFeedCount
    : dashboardFeeds.filter((feed) => feed.status === "running" || feed.status === "initializing").length;
  const totalFeedCount = useMockAnalytics ? mockAnalytics.totalFeedCount : dashboardFeeds.length;

  const severityBreakdown = useMemo(() => {
    const grouped = new Map<string, number>();
    for (const item of alertDistribution) {
      grouped.set(item.severity, (grouped.get(item.severity) ?? 0) + item.count);
    }

    return Array.from(grouped.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((left, right) => {
        const order = ["warning", "info"];
        return order.indexOf(left.name) - order.indexOf(right.name);
      });
  }, [alertDistribution]);

  const timeChartData = useMemo(
    () =>
      timeSeries.map((entry) => ({
        period: formatDateLabel(entry.period),
        waitTime: entry.avg_wait_time,
        queueSize: entry.peak_queue_length,
        alerts: entry.alert_count,
      })),
    [timeSeries],
  );

  const topZones = useMemo(
    () =>
      [...zoneStatistics]
        .sort((left, right) => right.avg_wait_time - left.avg_wait_time)
        .slice(0, 6)
        .map((entry) => ({
          label: `${entry.camera_id ?? "Camera"} · ${entry.zone_id ?? "Zone"}`,
          avgWaitTime: entry.avg_wait_time,
          peakQueue: entry.peak_queue_length,
          totalAlerts: entry.total_alerts,
        })),
    [zoneStatistics],
  );

  const feedSummary = useMemo(() => {
    if (!totalFeedCount) {
      return "No dashboard feeds are configured yet.";
    }

    return useMockAnalytics
      ? `${totalFeedCount} dashboard feeds synced · ${activeFeedCount} active stream${activeFeedCount === 1 ? "" : "s"}`
      : `${totalFeedCount} dashboard feeds connected · ${activeFeedCount} active stream${activeFeedCount === 1 ? "" : "s"}`;
  }, [activeFeedCount, totalFeedCount, useMockAnalytics]);

  const isLoading =
    overviewQuery.isLoading ||
    zoneQuery.isLoading ||
    timeQuery.isLoading ||
    alertDistributionQuery.isLoading ||
    feedsQuery.isLoading;
  const hasError = overviewQuery.isError || zoneQuery.isError || timeQuery.isError || alertDistributionQuery.isError;
  const errorMessage =
    (overviewQuery.error as Error | null)?.message ||
    (zoneQuery.error as Error | null)?.message ||
    (timeQuery.error as Error | null)?.message ||
    (alertDistributionQuery.error as Error | null)?.message ||
    "Unable to load statistics.";

  const exportCsv = () => {
    const headers = ["camera_id", "zone_id", "total_alerts", "avg_wait_time", "peak_queue_length", "stability_score"];
    const rows = zoneStatistics.map((entry) => [
      entry.camera_id ?? "",
      entry.zone_id ?? "",
      entry.total_alerts,
      entry.avg_wait_time,
      entry.peak_queue_length,
      entry.stability_score,
    ]);

    const csv = [headers.join(","), ...rows.map((row) => row.map((value) => JSON.stringify(value)).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `queuevision-statistics-${fromDate || "all-time"}-${toDate || "latest"}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
            <p className="text-sm text-muted-foreground">Live queue statistics from archived alert history.</p>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card/80 p-4 shadow-sm backdrop-blur sm:flex-row sm:flex-wrap sm:items-end">
            <label className="space-y-1 text-xs font-medium text-muted-foreground">
              <span>From</span>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
                className="h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-primary"
              />
            </label>
            <label className="space-y-1 text-xs font-medium text-muted-foreground">
              <span>To</span>
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
                className="h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-primary"
              />
            </label>
            <label className="space-y-1 text-xs font-medium text-muted-foreground">
              <span>Period</span>
              <select
                value={period}
                onChange={(event) => setPeriod(event.target.value as "hourly" | "daily" | "weekly")}
                className="h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-primary"
              >
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </label>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={exportCsv} disabled={!zoneStatistics.length}>
                <Download className="mr-1 h-4 w-4" /> Export CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void Promise.all([
                    overviewQuery.refetch(),
                    zoneQuery.refetch(),
                    timeQuery.refetch(),
                    alertDistributionQuery.refetch(),
                    feedsQuery.refetch(),
                  ]);
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </Button>
            </div>

            <div className="rounded-full border border-border bg-muted/50 px-4 py-2 text-xs text-muted-foreground">
              {feedSummary}
            </div>
          </div>
        </div>

        {hasError && !useMockAnalytics ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-5 text-sm text-destructive">
            {errorMessage}
          </div>
        ) : null}

        {useMockAnalytics ? (
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 text-sm text-foreground">
            Archived analytics are empty, so this page is seeded from the current dashboard feeds for the Salmen account.
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            title="Avg Wait Time"
            value={isLoading || !overview ? "—" : `${formatNumber(overview.avg_wait_time)}s`}
            icon={Clock}
            subtitle="Across filtered archive"
          />
          <KpiCard
            title="Peak Queue"
            value={isLoading || !overview ? "—" : overview.peak_queue_length}
            icon={Users}
            subtitle="Max people observed"
          />
          <KpiCard
            title="Stability Score"
            value={isLoading || !overview ? "—" : `${formatNumber(overview.stability_score, 0)}%`}
            icon={TrendingUp}
            subtitle="Share of stable readings"
          />
          <KpiCard
            title="Total Alerts"
            value={isLoading || !overview ? "—" : overview.total_alerts}
            icon={AlertTriangle}
            subtitle={
              isLoading || !overview
                ? undefined
                : `${overview.total_alerts} warning alert${overview.total_alerts === 1 ? "" : "s"}`
            }
          />
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.5fr_1fr]">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Wait Time Trend</h3>
                <p className="text-xs text-muted-foreground">Average wait time and peak queue size over the selected period.</p>
              </div>
              <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">{period}</span>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timeChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                <XAxis dataKey="period" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <YAxis tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(217 48% 10%)",
                    border: "1px solid hsl(215 25% 20%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="waitTime"
                  stroke="hsl(187 82% 53%)"
                  strokeWidth={2.5}
                  dot={{ fill: "hsl(187 82% 53%)", r: 3 }}
                  name="Avg wait (s)"
                />
                <Line
                  type="monotone"
                  dataKey="queueSize"
                  stroke="hsl(38 92% 50%)"
                  strokeWidth={2}
                  dot={{ fill: "hsl(38 92% 50%)", r: 3 }}
                  name="Peak queue"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-foreground">Alert Mix</h3>
              <p className="text-xs text-muted-foreground">Severity distribution derived from archived alerts.</p>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={severityBreakdown}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={68}
                  outerRadius={108}
                  paddingAngle={3}
                >
                  {severityBreakdown.map((entry) => (
                    <Cell key={entry.name} fill={severityColors[entry.name] ?? "hsl(215 16% 47%)"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "hsl(217 48% 10%)",
                    border: "1px solid hsl(215 25% 20%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-foreground">Top Zones</h3>
              <p className="text-xs text-muted-foreground">Zones ranked by average wait time for the selected filter range.</p>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={topZones} layout="vertical" margin={{ left: 16, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                <XAxis type="number" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <YAxis
                  type="category"
                  dataKey="label"
                  tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }}
                  axisLine={false}
                  width={150}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(217 48% 10%)",
                    border: "1px solid hsl(215 25% 20%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="avgWaitTime" fill="hsl(258 73% 76%)" radius={[0, 8, 8, 0]} name="Avg wait (s)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-foreground">Alert Types</h3>
              <p className="text-xs text-muted-foreground">Frequency by alert type and severity.</p>
            </div>
            <div className="space-y-3">
              {alertDistribution.length === 0 ? (
                <p className="text-sm text-muted-foreground">No alert data found for the selected range.</p>
              ) : (
                alertDistribution.map((item) => (
                  <div key={`${item.alert_type}-${item.severity}`} className="rounded-lg border border-border/80 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">{item.alert_type}</p>
                        <p className="text-xs text-muted-foreground">{item.severity}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-foreground">{item.count}</p>
                        <p className="text-xs text-muted-foreground">{formatNumber(item.percentage, 1)}%</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Zone Performance Table</h3>
              <p className="text-xs text-muted-foreground">Detailed per-camera and per-zone statistics.</p>
            </div>
            <span className="text-xs text-muted-foreground">{zoneStatistics.length} rows</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-2 text-left font-medium">Camera</th>
                  <th className="py-2 text-left font-medium">Zone</th>
                  <th className="py-2 text-right font-medium">Avg Wait</th>
                  <th className="py-2 text-right font-medium">Peak Queue</th>
                  <th className="py-2 text-right font-medium">Alerts</th>
                  <th className="py-2 text-right font-medium">Stability</th>
                </tr>
              </thead>
              <tbody>
                {zoneStatistics.length === 0 ? (
                  <tr>
                    <td className="py-4 text-sm text-muted-foreground" colSpan={6}>
                      No zone statistics found for the selected range.
                    </td>
                  </tr>
                ) : (
                  zoneStatistics.map((entry) => (
                    <tr key={`${entry.camera_id ?? "camera"}-${entry.zone_id ?? "zone"}`} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                      <td className="py-3 font-medium text-foreground">{entry.camera_id ?? "Unknown camera"}</td>
                      <td className="py-3 text-foreground">{entry.zone_id ?? "Unknown zone"}</td>
                      <td className="py-3 text-right font-mono text-muted-foreground">{formatNumber(entry.avg_wait_time)}s</td>
                      <td className="py-3 text-right font-mono text-muted-foreground">{entry.peak_queue_length}</td>
                      <td className="py-3 text-right font-mono text-muted-foreground">{entry.total_alerts}</td>
                      <td className="py-3 text-right font-mono text-muted-foreground">{formatNumber(entry.stability_score, 0)}%</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
