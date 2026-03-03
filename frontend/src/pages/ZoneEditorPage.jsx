import { useState } from 'react';
import { Sidebar, TopBar } from '../components/layout';
import {
  Hexagon,
  Square,
  Move,
  Save,
  Undo2,
  X,
  ChevronDown,
  MousePointer2,
  Info,
} from 'lucide-react';

/* ── Polygon vertices (mock) ── */
const vertices = [
  { id: 'P1', x: 120, y: 80 },
  { id: 'P2', x: 580, y: 80 },
  { id: 'P3', x: 620, y: 400 },
  { id: 'P4', x: 100, y: 400 },
];

const tools = [
  { icon: Hexagon, label: 'Polygon', active: true },
  { icon: Square, label: 'Rectangle', active: false },
  { icon: Move, label: 'Move', active: false },
];

export default function ZoneEditorPage() {
  const [activeTool, setActiveTool] = useState(0);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-auto">
        <TopBar title="Zone Editor" />

        <main className="flex-1 p-5 flex gap-5">
          {/* Left: Canvas + Toolbar */}
          <div className="flex-1 flex flex-col gap-4">
            {/* Canvas */}
            <div className="card-static flex-1 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-surface-light flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold">Main Entrance — Camera 1</span>
                  <span className="badge badge-zone text-[10px]">ZONE EDITOR</span>
                </div>
              </div>
              {/* Drawing area */}
              <div className="relative h-[460px] bg-primary/50 flex items-center justify-center">
                {/* SVG zone overlay */}
                <svg className="absolute inset-0 w-full h-full" viewBox="0 0 800 460" preserveAspectRatio="xMidYMid meet">
                  {/* Zone polygon */}
                  <polygon
                    points="120,60 580,60 620,380 100,380"
                    fill="rgba(34, 211, 238, 0.08)"
                    stroke="#22D3EE"
                    strokeWidth="2"
                    strokeDasharray="8 4"
                  />
                  {/* Corner handles */}
                  {[
                    [120, 60], [580, 60], [620, 380], [100, 380],
                  ].map(([cx, cy], i) => (
                    <g key={i}>
                      <circle cx={cx} cy={cy} r="8" fill="rgba(34, 211, 238, 0.2)" stroke="#22D3EE" strokeWidth="2" />
                      <circle cx={cx} cy={cy} r="3" fill="#22D3EE" />
                    </g>
                  ))}
                  {/* Zone label */}
                  <text x="350" y="230" fill="#22D3EE" fontSize="14" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">
                    Queue Zone A
                  </text>
                </svg>
                <span className="text-text-muted/20 font-mono text-xs z-0">[ Camera Feed ]</span>
              </div>
            </div>

            {/* Toolbar + Instructions */}
            <div className="flex gap-4">
              {/* Drawing toolbar */}
              <div className="card-static px-2 py-2 flex items-center gap-1">
                {tools.map((t, i) => (
                  <button
                    key={t.label}
                    onClick={() => setActiveTool(i)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${activeTool === i
                        ? 'bg-accent text-primary'
                        : 'text-text-secondary hover:text-white hover:bg-surface-light/50'
                      }`}
                  >
                    <t.icon className="w-4 h-4" />
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Instructions */}
              <div className="card-static flex-1 px-4 py-2.5 flex items-center gap-3">
                <Info className="w-4 h-4 text-accent flex-shrink-0" />
                <span className="text-xs text-text-secondary">
                  Click on the canvas to place vertices. Close the polygon by clicking the first point.
                  Drag handles to adjust.
                </span>
              </div>
            </div>
          </div>

          {/* Right: Properties Panel */}
          <div className="w-[300px] card-static flex flex-col">
            <div className="px-5 py-3.5 border-b border-surface-light">
              <span className="text-sm font-semibold">Properties</span>
            </div>

            <div className="p-5 space-y-5 flex-1">
              {/* Zone Name */}
              <div className="space-y-2">
                <label className="text-xs text-text-muted font-medium uppercase tracking-wider">Zone Name</label>
                <input
                  type="text"
                  defaultValue="Queue Zone A"
                  className="input text-sm"
                />
              </div>

              {/* Vertices */}
              <div className="space-y-2">
                <label className="text-xs text-text-muted font-medium uppercase tracking-wider">Polygon Vertices</label>
                <div className="space-y-1.5">
                  {vertices.map((v) => (
                    <div key={v.id} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-surface-light/30">
                      <span className="w-2 h-2 rounded-full bg-accent" />
                      <span className="text-xs font-mono font-semibold text-accent w-6">{v.id}</span>
                      <span className="text-xs font-mono text-text-secondary">
                        ({v.x}, {v.y})
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Trigger Anchor */}
              <div className="space-y-2">
                <label className="text-xs text-text-muted font-medium uppercase tracking-wider">Trigger Anchor</label>
                <div className="relative">
                  <select className="input text-sm appearance-none pr-10 cursor-pointer">
                    <option>Entry Edge</option>
                    <option>Exit Edge</option>
                    <option>Center Point</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-text-muted absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-5 border-t border-surface-light space-y-2">
              <button className="btn-primary w-full justify-center text-sm">
                <Save className="w-4 h-4" /> Save Zone
              </button>
              <div className="flex gap-2">
                <button className="btn-ghost flex-1 justify-center text-xs py-2">
                  <Undo2 className="w-3.5 h-3.5" /> Undo
                </button>
                <button className="btn-ghost flex-1 justify-center text-xs py-2">
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
