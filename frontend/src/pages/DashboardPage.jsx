import { Sidebar, TopBar } from '../components/layout';
import {
  Users,
  Clock,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Wifi,
  WifiOff,
  Bell,
  CheckCircle,
  ChevronRight,
  Activity,
  Webhook,
} from 'lucide-react';

/* ── KPI Stats ── */
const kpis = [
  { label: 'Avg Wait Time', value: '4.2', unit: 'min', icon: Clock, trend: '↓ 12%', trendColor: 'text-success', color: 'text-accent', bgColor: 'bg-accent/10' },
  { label: 'Queue Size', value: '12', unit: 'people', icon: Users, trend: '↑ 3%', trendColor: 'text-danger', color: 'text-purple', bgColor: 'bg-purple/10' },
  { label: 'Served / hr', value: '34', unit: 'persons', icon: TrendingUp, trend: '↑ 23%', trendColor: 'text-success', color: 'text-success', bgColor: 'bg-success/10' },
  { label: 'Uncertainty ±', value: '0.8', unit: 'min', icon: AlertTriangle, trend: 'LOW', trendColor: 'text-success', color: 'text-warning', bgColor: 'bg-warning/10' },
];

/* ── Cameras ── */
const cameras = [
  { name: 'Main Entrance', status: 'online', people: 8 },
  { name: 'Side Door', status: 'online', people: 3 },
  { name: 'Checkout Area', status: 'online', people: 12 },
  { name: 'VIP Lounge', status: 'offline', people: 0 },
];

/* ── Alerts ── */
const alerts = [
  { type: 'critical', title: 'Queue Overflow', msg: 'Main Entrance exceeded 15 people', time: '2 min ago', color: 'border-danger', bgColor: 'bg-danger/5', badge: 'bg-danger/15 text-danger' },
  { type: 'warning', title: 'High Wait Time', msg: 'Avg wait time exceeds 5 minutes', time: '8 min ago', color: 'border-warning', bgColor: 'bg-warning/5', badge: 'bg-warning/15 text-warning' },
  { type: 'resolved', title: 'Queue Normalized', msg: 'Side Door queue cleared', time: '15 min ago', color: 'border-success', bgColor: 'bg-success/5', badge: 'bg-success/15 text-success' },
];

export default function DashboardPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-auto">
        <TopBar title="Dashboard" />

        <main className="flex-1 p-5 space-y-5">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((k, i) => (
              <div
                key={k.label}
                className="card-static p-5 flex items-start gap-4 animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className={`w-12 h-12 rounded-xl ${k.bgColor} flex items-center justify-center flex-shrink-0`}>
                  <k.icon className={`w-5 h-5 ${k.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-text-muted text-xs mb-1">{k.label}</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold font-mono">{k.value}</span>
                    <span className="text-text-muted text-xs">{k.unit}</span>
                  </div>
                  <span className={`text-xs font-semibold font-mono ${k.trendColor}`}>{k.trend}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Main content: Camera Grid + Alert Sidebar */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
            {/* Camera Grid */}
            <div className="lg:col-span-3">
              <div className="card-static overflow-hidden">
                <div className="px-5 py-3.5 border-b border-surface-light flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold">Camera Feeds</span>
                    <span className="badge badge-live">
                      <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                      LIVE
                    </span>
                  </div>
                  <button className="btn-primary text-xs py-1.5 px-4">+ Add Camera</button>
                </div>
                <div className="grid grid-cols-2 gap-px bg-surface-light">
                  {cameras.map((cam, i) => (
                    <div
                      key={cam.name}
                      className={`relative h-[240px] bg-primary flex items-center justify-center group ${cam.status === 'offline' ? 'opacity-60' : ''}`}
                    >
                      {/* Camera name overlay */}
                      <div className="absolute top-3 left-3 flex items-center gap-2 z-10">
                        <span className={`w-2 h-2 rounded-full ${cam.status === 'online' ? 'bg-success animate-pulse' : 'bg-danger'}`} />
                        <span className="text-xs font-medium text-white/80">{cam.name}</span>
                      </div>
                      {/* Person count */}
                      {cam.status === 'online' && (
                        <div className="absolute top-3 right-3 bg-primary/80 backdrop-blur-sm px-2.5 py-1 rounded-md flex items-center gap-1.5 z-10">
                          <Users className="w-3 h-3 text-accent" />
                          <span className="text-xs font-mono font-bold text-accent">{cam.people}</span>
                        </div>
                      )}
                      {/* Center content */}
                      {cam.status === 'offline' ? (
                        <div className="flex flex-col items-center gap-2">
                          <WifiOff className="w-8 h-8 text-danger/50" />
                          <span className="text-xs font-mono text-danger/70">NO SIGNAL</span>
                        </div>
                      ) : (
                        <span className="text-text-muted/30 font-mono text-xs">[ Camera {i + 1} Stream ]</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Alert Sidebar */}
            <div className="space-y-4">
              {/* Threshold Status */}
              <div className="card-static p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Threshold Status</span>
                  <span className="badge badge-live text-[10px] py-0.5 px-2">ACTIVE</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between text-text-secondary">
                    <span>Max Wait Time</span>
                    <span className="font-mono text-white">5 min</span>
                  </div>
                  <div className="flex justify-between text-text-secondary">
                    <span>Max Queue Size</span>
                    <span className="font-mono text-white">15 persons</span>
                  </div>
                </div>
              </div>

              {/* Alerts */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider px-1">Recent Alerts</span>
                {alerts.map((a, i) => (
                  <div
                    key={i}
                    className={`card-static p-3.5 border-l-2 ${a.color} animate-slide-in-right`}
                    style={{ animationDelay: `${i * 100}ms` }}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className={`text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded ${a.badge}`}>
                        {a.type}
                      </span>
                      <span className="text-[10px] text-text-muted">{a.time}</span>
                    </div>
                    <p className="text-xs font-semibold mt-1.5">{a.title}</p>
                    <p className="text-[11px] text-text-muted mt-0.5">{a.msg}</p>
                  </div>
                ))}
              </div>

              {/* Webhook Status */}
              <div className="card-static p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Webhook className="w-4 h-4 text-success" />
                  <span className="text-xs font-semibold">n8n Connected</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-success ml-auto" />
                </div>
                <p className="text-[11px] text-text-muted font-mono">Last ping: 12s ago</p>
              </div>
            </div>
          </div>

          {/* Metrics Strip */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Wait Time Chart */}
            <div className="card-static p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold">Wait Time Trend</h3>
                <span className="text-[10px] font-mono text-text-muted">Last 60 min</span>
              </div>
              <div className="h-44 flex items-end gap-1 px-2">
                {/* SVG mini line chart */}
                <svg viewBox="0 0 400 120" className="w-full h-full" preserveAspectRatio="none">
                  {/* Grid lines */}
                  <line x1="0" y1="30" x2="400" y2="30" stroke="#334155" strokeWidth="0.5" strokeDasharray="4" />
                  <line x1="0" y1="60" x2="400" y2="60" stroke="#334155" strokeWidth="0.5" strokeDasharray="4" />
                  <line x1="0" y1="90" x2="400" y2="90" stroke="#334155" strokeWidth="0.5" strokeDasharray="4" />
                  {/* Area fill */}
                  <path d="M0,80 L40,70 L80,75 L120,50 L160,60 L200,40 L240,55 L280,35 L320,45 L360,30 L400,38 L400,120 L0,120 Z"
                    fill="url(#cyanGrad)" />
                  {/* Line */}
                  <path d="M0,80 L40,70 L80,75 L120,50 L160,60 L200,40 L240,55 L280,35 L320,45 L360,30 L400,38"
                    fill="none" stroke="#22D3EE" strokeWidth="2" />
                  {/* Dots */}
                  {[[0, 80], [40, 70], [80, 75], [120, 50], [160, 60], [200, 40], [240, 55], [280, 35], [320, 45], [360, 30], [400, 38]].map(([x, y], i) => (
                    <circle key={i} cx={x} cy={y} r="3" fill="#22D3EE" />
                  ))}
                  <defs>
                    <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.2" />
                      <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </div>

            {/* Queue Size Chart */}
            <div className="card-static p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold">Queue Size by Camera</h3>
                <span className="text-[10px] font-mono text-text-muted">Current</span>
              </div>
              <div className="space-y-3">
                {cameras.filter(c => c.status === 'online').map((cam) => (
                  <div key={cam.name} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-secondary">{cam.name}</span>
                      <span className="font-mono font-semibold text-accent">{cam.people}</span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${Math.min((cam.people / 15) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
