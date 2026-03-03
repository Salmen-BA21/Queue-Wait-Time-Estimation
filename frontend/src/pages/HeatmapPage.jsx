import { useState } from 'react';
import { Sidebar, TopBar } from '../components/layout';
import {
  ChevronDown,
  Users,
  Clock,
  Flame,
  Activity,
} from 'lucide-react';

/* ── Zone density data ── */
const zoneDensity = [
  { name: 'Main Queue', percent: 87, color: '--color-accent' },
  { name: 'Side Entrance', percent: 52, color: '--color-accent' },
  { name: 'Exit Area', percent: 18, color: '--color-accent' },
];

/* ── Live stats ── */
const liveStats = [
  { icon: Users, value: '24', label: 'People Detected', color: 'text-accent' },
  { icon: Clock, value: '3.2', label: 'Avg Dwell (min)', color: 'text-warning' },
  { icon: Flame, value: '34%', label: 'Hotspot Area', color: 'text-danger' },
];

/* ── Peak congestion ── */
const congestion = [
  { period: 'AM Rush', time: '08:00 – 10:00', color: 'bg-success', dotColor: 'bg-success' },
  { period: 'Lunch Peak', time: '12:00 – 14:00', color: 'bg-warning', dotColor: 'bg-warning' },
  { period: 'Evening Rush', time: '17:00 – 19:00', color: 'bg-danger', dotColor: 'bg-danger' },
];

const viewModes = ['Density', 'Paths', 'Dwell'];

export default function HeatmapPage() {
  const [activeView, setActiveView] = useState(0);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-auto">
        <TopBar title="Heatmap" />

        <main className="flex-1 p-5 flex gap-5">
          {/* Left: Heatmap canvas */}
          <div className="flex-1 flex flex-col gap-4">
            {/* Canvas card */}
            <div className="card-static flex-1 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-surface-light flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold">Heatmap Visualization</span>
                  <span className="badge badge-heatmap text-[10px]">HEATMAP</span>
                </div>
                <div className="flex items-center gap-3">
                  {/* Camera selector */}
                  <div className="relative">
                    <select className="input text-xs py-1.5 pl-3 pr-8 appearance-none cursor-pointer bg-surface-light/50 w-44">
                      <option>Main Entrance</option>
                      <option>Side Door</option>
                      <option>Checkout Area</option>
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-text-muted absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>

                  {/* View toggle */}
                  <div className="flex bg-surface-light rounded-lg p-0.5">
                    {viewModes.map((mode, i) => (
                      <button
                        key={mode}
                        onClick={() => setActiveView(i)}
                        className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-all ${activeView === i
                            ? 'bg-accent text-primary'
                            : 'text-text-secondary hover:text-white'
                          }`}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Heatmap image */}
              <div className="relative h-[460px] bg-primary/50">
                <img
                  src="/heatmap-preview.png"
                  alt="Heatmap Visualization"
                  className="w-full h-full object-cover opacity-90"
                />
                {/* Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-primary/40 via-transparent to-transparent" />
              </div>
            </div>

            {/* Gradient Legend */}
            <div className="card-static px-5 py-3 flex items-center gap-4">
              <span className="text-xs text-text-muted font-medium">Low</span>
              <div className="flex-1 h-3 rounded-full overflow-hidden" style={{
                background: 'linear-gradient(90deg, #3B82F6, #22D3EE, #10B981, #F59E0B, #EF4444)'
              }} />
              <span className="text-xs text-text-muted font-medium">High</span>
            </div>
          </div>

          {/* Right: Stats panel */}
          <div className="w-[280px] space-y-4">
            {/* Zone Density */}
            <div className="card-static p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Zone Density</h3>
              <div className="space-y-4">
                {zoneDensity.map((z) => (
                  <div key={z.name} className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-secondary">{z.name}</span>
                      <span className="font-mono font-bold text-accent">{z.percent}%</span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${z.percent}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Statistics */}
            <div className="card-static p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Live Statistics</h3>
              <div className="space-y-3">
                {liveStats.map((s) => (
                  <div key={s.label} className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-surface-light flex items-center justify-center">
                      <s.icon className={`w-4 h-4 ${s.color}`} />
                    </div>
                    <div>
                      <p className="text-lg font-bold font-mono">{s.value}</p>
                      <p className="text-[10px] text-text-muted">{s.label}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Peak Congestion */}
            <div className="card-static p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Peak Congestion</h3>
              <div className="space-y-2.5">
                {congestion.map((c) => (
                  <div key={c.period} className="flex items-center gap-3 p-2.5 rounded-lg bg-surface-light/30">
                    <span className={`w-2.5 h-2.5 rounded-full ${c.dotColor}`} />
                    <div className="flex-1">
                      <p className="text-xs font-semibold">{c.period}</p>
                      <p className="text-[10px] text-text-muted font-mono">{c.time}</p>
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
