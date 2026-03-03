import { Sidebar, TopBar } from '../components/layout';
import {
  Clock,
  Users,
  TrendingUp,
  AlertTriangle,
  Download,
  Calendar,
  ArrowDown,
  ArrowUp,
  AlertCircle,
  CheckCircle,
  Info,
} from 'lucide-react';

/* ── KPI data ── */
const kpis = [
  { label: 'Avg Wait Time', value: '4.2', unit: 'min', icon: Clock, trend: '↓ 12%', positive: true, color: 'text-accent', bg: 'bg-accent/10' },
  { label: 'Peak Queue', value: '18', unit: 'people', icon: Users, trend: '↑ 8%', positive: false, color: 'text-danger', bg: 'bg-danger/10' },
  { label: 'Total Served', value: '2,847', unit: 'persons', icon: TrendingUp, trend: '↑ 23%', positive: true, color: 'text-success', bg: 'bg-success/10' },
  { label: 'Avg Uncertainty', value: '±0.8', unit: '', icon: AlertTriangle, trend: 'LOW', positive: true, color: 'text-purple', bg: 'bg-purple/10' },
];

/* ── Cameras for bar chart ── */
const cameraData = [
  { name: 'Main Entrance', value: 45, max: 60 },
  { name: 'Side Door', value: 28, max: 60 },
  { name: 'Checkout', value: 52, max: 60 },
  { name: 'VIP Lounge', value: 12, max: 60 },
];

/* ── Peak hours heatmap data ── */
const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const periods = ['Morning', 'Afternoon', 'Evening'];
const heatmapData = [
  [0.3, 0.5, 0.7, 0.6, 0.8, 0.4, 0.2], // Morning
  [0.6, 0.8, 0.9, 0.7, 0.9, 0.6, 0.3], // Afternoon
  [0.5, 0.6, 0.7, 0.9, 0.7, 0.5, 0.2], // Evening
];

/* ── Alerts ── */
const recentAlerts = [
  { type: 'CRITICAL', msg: 'Queue overflow at Main Entrance', time: '14:32', badge: 'bg-danger/15 text-danger', icon: AlertCircle },
  { type: 'WARNING', msg: 'High wait time at Checkout', time: '13:45', badge: 'bg-warning/15 text-warning', icon: AlertTriangle },
  { type: 'INFO', msg: 'New camera source added', time: '12:10', badge: 'bg-accent/15 text-accent', icon: Info },
  { type: 'RESOLVED', msg: 'Side Door queue normalized', time: '11:58', badge: 'bg-success/15 text-success', icon: CheckCircle },
];

export default function AnalyticsPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-auto">
        <TopBar title="Analytics" />

        <main className="flex-1 p-5 space-y-5">
          {/* Top action bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Calendar className="w-4 h-4 text-text-muted" />
              <span className="text-sm text-text-secondary font-mono">Feb 20 – Feb 27, 2026</span>
            </div>
            <button className="btn-ghost text-xs py-2 px-4">
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
          </div>

          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((k, i) => (
              <div
                key={k.label}
                className="card-static p-5 animate-fade-in-up"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-text-muted text-xs">{k.label}</span>
                  <div className={`w-8 h-8 rounded-lg ${k.bg} flex items-center justify-center`}>
                    <k.icon className={`w-4 h-4 ${k.color}`} />
                  </div>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold font-mono">{k.value}</span>
                  <span className="text-text-muted text-xs">{k.unit}</span>
                </div>
                <div className="flex items-center gap-1 mt-2">
                  {k.trend !== 'LOW' ? (
                    k.positive ? <ArrowDown className="w-3 h-3 text-success" /> : <ArrowUp className="w-3 h-3 text-danger" />
                  ) : null}
                  <span className={`text-xs font-mono font-semibold ${k.positive ? 'text-success' : 'text-danger'}`}>
                    {k.trend}
                  </span>
                  {k.trend !== 'LOW' && <span className="text-text-muted text-[10px]">vs prev period</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Wait Time Trend */}
            <div className="card-static p-5">
              <h3 className="text-sm font-semibold mb-4">Wait Time Trend</h3>
              <div className="h-52">
                <svg viewBox="0 0 400 140" className="w-full h-full" preserveAspectRatio="none">
                  {/* Grid */}
                  {[35, 70, 105].map(y => (
                    <line key={y} x1="0" y1={y} x2="400" y2={y} stroke="#334155" strokeWidth="0.5" strokeDasharray="4" />
                  ))}
                  {/* CI band (purple) */}
                  <path d="M0,65 L50,55 L100,60 L150,40 L200,45 L250,30 L300,40 L350,25 L400,30
                           L400,100 L350,85 L300,90 L250,80 L200,90 L150,80 L100,95 L50,85 L0,95 Z"
                    fill="rgba(167, 139, 250, 0.12)" />
                  {/* Line */}
                  <path d="M0,80 L50,70 L100,77 L150,58 L200,65 L250,52 L300,62 L350,50 L400,58"
                    fill="none" stroke="#A78BFA" strokeWidth="2" />
                  {/* Dots */}
                  {[[0, 80], [50, 70], [100, 77], [150, 58], [200, 65], [250, 52], [300, 62], [350, 50], [400, 58]].map(([x, y], i) => (
                    <circle key={i} cx={x} cy={y} r="3" fill="#A78BFA" />
                  ))}
                </svg>
              </div>
            </div>

            {/* Queue Size by Camera */}
            <div className="card-static p-5">
              <h3 className="text-sm font-semibold mb-4">Queue Size by Camera</h3>
              <div className="space-y-4 mt-2">
                {cameraData.map((cam) => (
                  <div key={cam.name} className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-text-secondary">{cam.name}</span>
                      <span className="font-mono font-semibold text-accent">{cam.value}</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${(cam.value / cam.max) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Peak Hours Heatmap */}
            <div className="card-static p-5">
              <h3 className="text-sm font-semibold mb-4">Peak Hours</h3>
              <div className="space-y-1">
                {/* Day headers */}
                <div className="grid gap-1" style={{ gridTemplateColumns: '80px repeat(7, 1fr)' }}>
                  <div />
                  {days.map(d => (
                    <div key={d} className="text-center text-[10px] text-text-muted font-mono py-1">{d}</div>
                  ))}
                </div>
                {/* Heatmap rows */}
                {periods.map((period, pi) => (
                  <div key={period} className="grid gap-1" style={{ gridTemplateColumns: '80px repeat(7, 1fr)' }}>
                    <div className="text-xs text-text-muted flex items-center">{period}</div>
                    {heatmapData[pi].map((val, di) => (
                      <div
                        key={di}
                        className="h-10 rounded-md flex items-center justify-center text-[10px] font-mono"
                        style={{
                          backgroundColor: `rgba(34, 211, 238, ${val * 0.35})`,
                          color: val > 0.6 ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)',
                        }}
                      >
                        {Math.round(val * 100)}%
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Alerts */}
            <div className="card-static p-5">
              <h3 className="text-sm font-semibold mb-4">Recent Alerts</h3>
              <div className="space-y-2.5">
                {recentAlerts.map((a, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 rounded-lg bg-surface-light/30 animate-fade-in-up"
                    style={{ animationDelay: `${i * 80}ms` }}
                  >
                    <a.icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${a.badge.split(' ')[1]}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded ${a.badge}`}>
                          {a.type}
                        </span>
                        <span className="text-[10px] text-text-muted font-mono ml-auto">{a.time}</span>
                      </div>
                      <p className="text-xs text-text-secondary">{a.msg}</p>
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
