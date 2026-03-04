import { useState } from "react";
import {
  Camera, Users, Clock, AlertTriangle, Activity, Wifi, WifiOff, Plus, Eye,
} from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { KpiCard } from "@/components/ui/kpi-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const waitTimeData = [
  { time: "09:00", value: 3.2 },
  { time: "10:00", value: 5.1 },
  { time: "11:00", value: 7.8 },
  { time: "12:00", value: 12.3 },
  { time: "13:00", value: 9.5 },
  { time: "14:00", value: 6.2 },
  { time: "15:00", value: 4.8 },
  { time: "16:00", value: 8.1 },
];

const queueSizeData = [
  { camera: "Entrance A", count: 12 },
  { camera: "Entrance B", count: 8 },
  { camera: "Checkout 1", count: 15 },
  { camera: "Checkout 2", count: 6 },
];

const cameras = [
  { id: 1, name: "Entrance A", status: "online" as const, people: 12, location: "Main Lobby" },
  { id: 2, name: "Entrance B", status: "online" as const, people: 8, location: "Side Entrance" },
  { id: 3, name: "Checkout 1", status: "warning" as const, people: 15, location: "Floor 1" },
  { id: 4, name: "Checkout 2", status: "offline" as const, people: 0, location: "Floor 1" },
];

const alerts = [
  { id: 1, message: "Queue threshold exceeded at Checkout 1", time: "2 min ago", severity: "danger" },
  { id: 2, message: "Camera Checkout 2 went offline", time: "5 min ago", severity: "warning" },
  { id: 3, message: "Avg wait time rising at Entrance A", time: "12 min ago", severity: "info" },
  { id: 4, message: "Peak queue detected at Entrance B", time: "18 min ago", severity: "warning" },
  { id: 5, message: "Zone 3 recalibrated successfully", time: "25 min ago", severity: "success" },
];

export default function Dashboard() {
  const [showAllCameras, setShowAllCameras] = useState(false);

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="text-sm text-muted-foreground">Real-time queue monitoring overview</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowAllCameras(true)}>
              <Eye className="h-4 w-4 mr-1" />
              See All Cameras
            </Button>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" />
              Add Camera
            </Button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in-up">
          <KpiCard title="Active Cameras" value="3/4" icon={Camera} subtitle="1 offline" />
          <KpiCard title="Total People" value={35} icon={Users} trend={{ value: 12, positive: true }} />
          <KpiCard title="Avg Wait Time" value="6.4m" icon={Clock} trend={{ value: 8, positive: false }} />
          <KpiCard title="Active Alerts" value={3} icon={AlertTriangle} subtitle="1 critical" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Camera grid */}
            <div>
              <h2 className="text-sm font-semibold text-foreground mb-3">Camera Feeds</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {cameras.map((cam) => (
                  <div
                    key={cam.id}
                    className="group rounded-lg border border-border bg-card overflow-hidden transition-all hover:glow-border"
                  >
                    {/* Mock feed */}
                    <div className="relative aspect-video bg-background/80 flex items-center justify-center">
                      <div className="text-center space-y-2">
                        {cam.status === "offline" ? (
                          <WifiOff className="h-8 w-8 text-muted-foreground/30 mx-auto" />
                        ) : (
                          <Wifi className="h-8 w-8 text-primary/30 mx-auto animate-glow-pulse" />
                        )}
                        <p className="text-xs text-muted-foreground/50 font-mono">FEED: {cam.name}</p>
                      </div>
                      {/* Overlays */}
                      <div className="absolute top-2 left-2">
                        <StatusBadge status={cam.status} />
                      </div>
                      {cam.status !== "offline" && (
                        <div className="absolute top-2 right-2 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground flex items-center gap-1">
                          <Users className="h-3 w-3 text-primary" />
                          {cam.people}
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <p className="text-sm font-medium text-foreground">{cam.name}</p>
                      <p className="text-xs text-muted-foreground">{cam.location}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-foreground mb-4">Wait Time Trend</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={waitTimeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                    <XAxis dataKey="time" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
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
                <h3 className="text-sm font-semibold text-foreground mb-4">Queue Size by Camera</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={queueSizeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                    <XAxis dataKey="camera" tick={{ fill: "hsl(215 16% 57%)", fontSize: 10 }} axisLine={false} />
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
              Recent Alerts
            </h2>
            <div className="space-y-2">
              {alerts.map((alert) => (
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

        {/* All Cameras Modal */}
        <Dialog open={showAllCameras} onOpenChange={setShowAllCameras}>
          <DialogContent className="sm:max-w-2xl bg-card border-border">
            <DialogHeader>
              <DialogTitle className="text-foreground">All Cameras</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Overview of all connected camera feeds
              </DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[60vh] overflow-y-auto pr-1">
              {cameras.map((cam) => (
                <div
                  key={cam.id}
                  className="rounded-lg border border-border bg-background p-4 flex items-center gap-4"
                >
                  <div className="h-10 w-10 rounded-md bg-primary/10 flex items-center justify-center">
                    {cam.status === "offline" ? (
                      <WifiOff className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <Wifi className="h-5 w-5 text-primary" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">{cam.name}</p>
                    <p className="text-xs text-muted-foreground">{cam.location}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {cam.status !== "offline" && (
                      <span className="text-xs font-mono text-foreground flex items-center gap-1">
                        <Users className="h-3 w-3 text-primary" />
                        {cam.people}
                      </span>
                    )}
                    <StatusBadge status={cam.status} />
                  </div>
                </div>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
