import { AppLayout } from "@/components/layout/AppLayout";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { Clock, Users, TrendingUp, AlertTriangle, Download } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { format } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const trendData = [
  { date: "Mon", waitTime: 4.2, volume: 120 },
  { date: "Tue", waitTime: 5.8, volume: 145 },
  { date: "Wed", waitTime: 7.1, volume: 190 },
  { date: "Thu", waitTime: 6.3, volume: 165 },
  { date: "Fri", waitTime: 8.9, volume: 220 },
  { date: "Sat", waitTime: 11.2, volume: 310 },
  { date: "Sun", waitTime: 3.5, volume: 85 },
];

const cameraPerformance = [
  { camera: "Entrance A", avgWait: 5.2, served: 342 },
  { camera: "Entrance B", avgWait: 3.8, served: 289 },
  { camera: "Checkout 1", avgWait: 8.1, served: 456 },
  { camera: "Checkout 2", avgWait: 4.5, served: 198 },
];

export default function Analytics() {
  const [date, setDate] = useState<Date>();

  const exportCSV = () => {
    const headers = "Date,Wait Time (min),Volume\n";
    const rows = trendData.map((d) => `${d.date},${d.waitTime},${d.volume}`).join("\n");
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "queuevision-analytics.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
            <p className="text-sm text-muted-foreground">Historical analysis and performance metrics</p>
          </div>
          <div className="flex items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className={cn("justify-start text-left font-normal", !date && "text-muted-foreground")}>
                  <CalendarIcon className="h-4 w-4" />
                  {date ? format(date, "PPP") : "Pick date"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar mode="single" selected={date} onSelect={setDate} className="p-3 pointer-events-auto" />
              </PopoverContent>
            </Popover>
            <Button variant="outline" size="sm" onClick={exportCSV}>
              <Download className="h-4 w-4 mr-1" /> Export CSV
            </Button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in-up">
          <KpiCard title="Avg Wait Time" value="6.1m" icon={Clock} trend={{ value: 5, positive: false }} />
          <KpiCard title="Peak Queue Size" value={28} icon={Users} trend={{ value: 15, positive: true }} />
          <KpiCard title="Total Served" value="1,285" icon={TrendingUp} trend={{ value: 8, positive: true }} />
          <KpiCard title="Active Alerts" value="2.4%" icon={AlertTriangle} subtitle="Weekly average" />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-lg border border-border bg-card p-5">
            <h3 className="text-sm font-semibold text-foreground mb-4">Wait Time Over Time</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                <XAxis dataKey="date" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <YAxis tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <Tooltip contentStyle={{ background: "hsl(217 48% 10%)", border: "1px solid hsl(215 25% 20%)", borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="waitTime" stroke="hsl(187 82% 53%)" strokeWidth={2} dot={{ fill: "hsl(187 82% 53%)", r: 3 }} name="Wait Time (min)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-border bg-card p-5">
            <h3 className="text-sm font-semibold text-foreground mb-4">Queue Volume Over Time</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(215 25% 20%)" />
                <XAxis dataKey="date" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <YAxis tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} axisLine={false} />
                <Tooltip contentStyle={{ background: "hsl(217 48% 10%)", border: "1px solid hsl(215 25% 20%)", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="volume" fill="hsl(258 73% 76%)" radius={[4, 4, 0, 0]} name="People" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Camera performance table */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Camera Performance</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left py-2 font-medium">Camera</th>
                  <th className="text-right py-2 font-medium">Avg Wait</th>
                  <th className="text-right py-2 font-medium">Total Served</th>
                </tr>
              </thead>
              <tbody>
                {cameraPerformance.map((cam) => (
                  <tr key={cam.camera} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                    <td className="py-3 text-foreground font-medium">{cam.camera}</td>
                    <td className="py-3 text-right font-mono text-muted-foreground">{cam.avgWait}m</td>
                    <td className="py-3 text-right font-mono text-muted-foreground">{cam.served}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
