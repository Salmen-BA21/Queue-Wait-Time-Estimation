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
  getZoneStatistics,
} from "@/lib/api";

const severityColors: Record<string, string> = {
  critical: "hsl(0 84% 60%)",
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

  const overview = overviewQuery.data;
  const zoneStatistics = useMemo(() => zoneQuery.data ?? [], [zoneQuery.data]);
  const timeSeries = useMemo(() => timeQuery.data ?? [], [timeQuery.data]);
  const alertDistribution = useMemo(() => alertDistributionQuery.data ?? [], [alertDistributionQuery.data]);

  const severityBreakdown = useMemo(() => {
    const grouped = new Map<string, number>();
    for (const item of alertDistribution) {
      grouped.set(item.severity, (grouped.get(item.severity) ?? 0) + item.count);
    }

    return Array.from(grouped.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((left, right) => {
        const order = ["critical", "warning", "info"];
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

  const isLoading = overviewQuery.isLoading || zoneQuery.isLoading || timeQuery.isLoading || alertDistributionQuery.isLoading;
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
                  ]);
                }}
              >
                <RefreshCw className="mr-1 h-4 w-4" /> Refresh
              </Button>
            </div>
          </div>
        </div>

        {hasError ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-5 text-sm text-destructive">
            {errorMessage}
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
                : `${overview.critical_alerts} critical · ${overview.warning_alerts} warning`
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
