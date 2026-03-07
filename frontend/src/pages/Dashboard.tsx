import { FormEvent, useMemo, useState } from "react";
import {
  Camera, Users, Clock, AlertTriangle, Activity, Wifi, WifiOff, Plus, Radio,
} from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { KpiCard } from "@/components/ui/kpi-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { toast } from "sonner";
import { useLiveDashboard } from "@/hooks/use-live-dashboard";

function mapFeedStatus(status: "created" | "initializing" | "running" | "stopped" | "error") {
  if (status === "running") {
    return "online" as const;
  }
  if (status === "stopped") {
    return "offline" as const;
  }
  return "warning" as const;
}

function formatWaitTime(waitTimeSeconds: number): string {
  if (waitTimeSeconds < 60) {
    return `${waitTimeSeconds.toFixed(1)}s`;
  }
  return `${(waitTimeSeconds / 60).toFixed(1)}m`;
}

export default function Dashboard() {
  const [showAddCamera, setShowAddCamera] = useState(false);
  const [feedName, setFeedName] = useState("");
  const [feedSource, setFeedSource] = useState("");
  const [sourceMode, setSourceMode] = useState<"rtsp" | "file">("file");
  const {
    feeds,
    feedsQuery,
    systemHealthQuery,
    createFeedMutation,
    activity,
    derived,
  } = useLiveDashboard();

  const systemHealth = systemHealthQuery.data;
  const sourcePlaceholder = sourceMode === "file"
    ? "C:/Users/ELITE/Desktop/Queue-Wait-Time-Estimation/sample-video.mp4"
    : "rtsp://192.168.1.10/stream";

  const emptyState = useMemo(
    () => !feedsQuery.isLoading && feeds.length === 0,
    [feeds.length, feedsQuery.isLoading],
  );

  const handleCreateFeed = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await createFeedMutation.mutateAsync({
        name: feedName,
        source: feedSource,
      });
      toast.success("Feed registered successfully.");
      setFeedName("");
      setFeedSource("");
      setSourceMode("file");
      setShowAddCamera(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to register feed.");
    }
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="text-sm text-muted-foreground">Real-time surveillance wall for all configured queue feeds</p>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => setShowAddCamera(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add Feed
            </Button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in-up">
          <KpiCard
            title="Registered Feeds"
            value={derived.registeredFeeds}
            icon={Camera}
            subtitle={systemHealth ? `${systemHealth.websocket_clients} dashboard clients connected` : "Waiting for backend API"}
          />
          <KpiCard title="Running Feeds" value={derived.onlineFeeds} icon={Radio} subtitle="Worker status becomes live in the next backend slice" />
          <KpiCard title="People In Queue" value={derived.peopleTotal} icon={Users} />
          <KpiCard
            title="Average Wait"
            value={formatWaitTime(derived.averageWaitTime)}
            icon={Clock}
            subtitle={systemHealth ? `API ${systemHealth.status}` : "No API heartbeat yet"}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Camera grid */}
            <div>
              <h2 className="text-sm font-semibold text-foreground mb-3">Surveillance Wall</h2>
              {emptyState && (
                <div className="rounded-lg border border-dashed border-border bg-card/60 p-8 text-center">
                  <Camera className="mx-auto h-10 w-10 text-primary/50" />
                  <p className="mt-3 text-sm font-medium text-foreground">No feeds configured yet</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Add your first RTSP or local source to populate the surveillance wall.
                  </p>
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {feeds.map((feed) => {
                  const uiStatus = mapFeedStatus(feed.status);
                  const peopleInZone = feed.latest_metrics?.people_in_zone ?? 0;
                  const waitTimeSeconds = feed.latest_metrics?.wait_time_seconds;

                  return (
                  <div
                    key={feed.feed_id}
                    className="group rounded-lg border border-border bg-card overflow-hidden transition-all hover:glow-border"
                  >
                    {/* Feed panel */}
                    <div className="relative aspect-video bg-background/80 flex items-center justify-center">
                      <div className="text-center space-y-2">
                        {uiStatus === "offline" ? (
                          <WifiOff className="h-8 w-8 text-muted-foreground/30 mx-auto" />
                        ) : (
                          <Wifi className="h-8 w-8 text-primary/30 mx-auto animate-glow-pulse" />
                        )}
                        <p className="text-xs text-muted-foreground/50 font-mono">SOURCE: {feed.source}</p>
                        <p className="text-[11px] text-muted-foreground">
                          Live video transport is the next slice. This tile already tracks feed state and queue metrics.
                        </p>
                      </div>
                      {/* Overlays */}
                      <div className="absolute top-2 left-2">
                        <StatusBadge status={uiStatus} label={feed.status} />
                      </div>
                      {uiStatus !== "offline" && (
                        <div className="absolute top-2 right-2 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground flex items-center gap-1">
                          <Users className="h-3 w-3 text-primary" />
                          {peopleInZone}
                        </div>
                      )}
                      {waitTimeSeconds !== null && waitTimeSeconds !== undefined && (
                        <div className="absolute bottom-2 right-2 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground">
                          {formatWaitTime(waitTimeSeconds)}
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-foreground">{feed.name}</p>
                          <p className="text-xs text-muted-foreground font-mono truncate">{feed.source}</p>
                        </div>
                        <div className="text-right text-xs text-muted-foreground">
                          <p>{feed.zone?.points.length ?? 0} zone points</p>
                          <p>{feed.last_error ?? "No runtime error"}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  );
                })}
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-foreground mb-4">Current Wait Time by Feed</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={derived.waitChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                    <XAxis dataKey="name" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                    <YAxis tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: "hsl(217 48% 10%)", border: "1px solid hsl(215 25% 20%)", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "hsl(215 16% 57%)" }}
                    />
                    <Line type="monotone" dataKey="value" stroke="hsl(187 82% 53%)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-foreground mb-4">Queue Size by Feed</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={derived.queueChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                    <XAxis dataKey="name" tick={{ fill: "hsl(215 16% 57%)", fontSize: 10 }} axisLine={false} />
                    <YAxis tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: "hsl(217 48% 10%)", border: "1px solid hsl(215 25% 20%)", borderRadius: 8, fontSize: 12 }}
                    />
                    <Bar dataKey="count" fill="hsl(187 82% 53%)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Alerts panel */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Recent Activity
            </h2>
            <div className="space-y-2">
              {activity.length === 0 && (
                <div className="rounded-lg border border-border bg-card p-3 text-sm">
                  <p className="text-foreground text-xs leading-relaxed">No live feed activity yet.</p>
                  <p className="text-[10px] text-muted-foreground mt-1.5 font-mono">Waiting for the first WebSocket event</p>
                </div>
              )}
              {activity.map((alert) => (
                <div
                  key={alert.id}
                  className="rounded-lg border border-border bg-card p-3 text-sm transition-all hover:bg-accent/50"
                >
                  <p className="text-foreground text-xs leading-relaxed">{alert.message}</p>
                  <p className="text-[10px] text-muted-foreground mt-1.5 font-mono">{alert.time}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Add Camera Modal */}
        <Dialog open={showAddCamera} onOpenChange={setShowAddCamera}>
          <DialogContent className="sm:max-w-lg bg-card border-border">
            <DialogHeader>
              <DialogTitle className="text-foreground">Add Feed</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Register either an RTSP camera or a local MP4 file path in the backend feed registry.
              </DialogDescription>
            </DialogHeader>
            <form className="space-y-4" onSubmit={handleCreateFeed}>
              <div className="space-y-2">
                <span className="text-sm font-medium text-foreground">Source type</span>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant={sourceMode === "file" ? "default" : "outline"}
                    onClick={() => setSourceMode("file")}
                  >
                    Local MP4
                  </Button>
                  <Button
                    type="button"
                    variant={sourceMode === "rtsp" ? "default" : "outline"}
                    onClick={() => setSourceMode("rtsp")}
                  >
                    RTSP Camera
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground" htmlFor="feed-name">Feed name</label>
                <Input
                  id="feed-name"
                  value={feedName}
                  onChange={(event) => setFeedName(event.target.value)}
                  placeholder="Checkout 1"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground" htmlFor="feed-source">Source</label>
                <Input
                  id="feed-source"
                  value={feedSource}
                  onChange={(event) => setFeedSource(event.target.value)}
                  placeholder={sourcePlaceholder}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {sourceMode === "file"
                    ? "Use a file path that the backend machine can open, for example C:/videos/test-queue.mp4."
                    : "Use your camera RTSP URL, for example rtsp://192.168.1.10/stream."}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                This first slice registers feeds and exposes them to the web dashboard. MP4 paths are valid for testing feed registration now. Live video transport and worker-driven metrics will be added in the next backend slice.
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setShowAddCamera(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createFeedMutation.isPending}>
                  {createFeedMutation.isPending ? "Adding..." : "Add Feed"}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
