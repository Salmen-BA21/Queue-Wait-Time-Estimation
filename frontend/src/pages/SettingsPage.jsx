import { useState } from 'react';
import { Sidebar, TopBar } from '../components/layout';
import {
  Settings as SettingsIcon,
  Brain,
  Bell,
  Webhook,
  Database,
  Map,
  ChevronDown,
  Save,
} from 'lucide-react';

/* ── Nav items ── */
const navSections = [
  { icon: SettingsIcon, label: 'General', id: 'general' },
  { icon: Brain, label: 'Model & Detection', id: 'model' },
  { icon: Bell, label: 'Alerts & Thresholds', id: 'alerts' },
  { icon: Webhook, label: 'Webhooks', id: 'webhooks' },
  { icon: Database, label: 'Data & Export', id: 'data' },
  { icon: Map, label: 'Zones', id: 'zones' },
];

/* ── Toggle Component ── */
function Toggle({ active = true }) {
  const [on, setOn] = useState(active);
  return (
    <div
      className={`toggle ${on ? 'active' : 'inactive'}`}
      onClick={() => setOn(!on)}
    >
      <div className="toggle-knob" />
    </div>
  );
}

export default function SettingsPage() {
  const [activeNav, setActiveNav] = useState('general');

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-auto">
        <TopBar title="Settings" />

        <main className="flex-1 flex">
          {/* Settings nav */}
          <div className="w-[220px] border-r border-surface-light p-4 space-y-1">
            {navSections.map((s) => {
              const isActive = activeNav === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setActiveNav(s.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all text-left relative ${isActive
                      ? 'bg-accent/10 text-accent'
                      : 'text-text-secondary hover:text-white hover:bg-surface-light/50'
                    }`}
                >
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-accent rounded-r-full" />
                  )}
                  <s.icon className="w-4 h-4" />
                  {s.label}
                </button>
              );
            })}
          </div>

          {/* Settings content */}
          <div className="flex-1 p-6 max-w-3xl">
            {/* Header row */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-xl font-semibold">General Settings</h2>
                <p className="text-sm text-text-muted mt-1">Manage your application preferences</p>
              </div>
              <button className="btn-primary text-sm">
                <Save className="w-4 h-4" /> Save Changes
              </button>
            </div>

            <div className="space-y-8">
              {/* ── Application ── */}
              <div className="space-y-5">
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-semibold text-text-muted uppercase tracking-[2px]">Application</span>
                  <div className="flex-1 h-px bg-surface-light" />
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Application Name</label>
                      <span className="text-[11px] text-text-muted">Display name for your instance</span>
                    </div>
                    <input type="text" defaultValue="QueueVision" className="input w-56 text-sm" />
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Refresh Rate</label>
                      <span className="text-[11px] text-text-muted">Processing frames per second</span>
                    </div>
                    <div className="relative w-56">
                      <select className="input text-sm appearance-none pr-10 cursor-pointer">
                        <option>30 FPS</option>
                        <option>25 FPS</option>
                        <option>15 FPS</option>
                        <option>10 FPS</option>
                      </select>
                      <ChevronDown className="w-4 h-4 text-text-muted absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Dark Mode</label>
                      <span className="text-[11px] text-text-muted">Always enabled for QueueVision</span>
                    </div>
                    <Toggle active={true} />
                  </div>
                </div>
              </div>

              {/* ── Model & Detection ── */}
              <div className="space-y-5">
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-semibold text-text-muted uppercase tracking-[2px]">Model & Detection</span>
                  <div className="flex-1 h-px bg-surface-light" />
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">YOLO Model</label>
                      <span className="text-[11px] text-text-muted">Select detection model variant</span>
                    </div>
                    <div className="relative w-56">
                      <select className="input text-sm appearance-none pr-10 cursor-pointer">
                        <option>yolo26n (Nano)</option>
                        <option>yolo26s (Small)</option>
                        <option>yolo26m (Medium)</option>
                        <option>yolo26l (Large)</option>
                        <option>yolo26x (XLarge)</option>
                      </select>
                      <ChevronDown className="w-4 h-4 text-text-muted absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Confidence Threshold</label>
                      <span className="text-[11px] text-text-muted">Minimum detection confidence</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        defaultValue="0.45"
                        className="w-28 accent-accent h-1.5"
                      />
                      <span className="text-xs font-mono text-accent w-10 text-right">0.45</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">ByteTrack Max Age</label>
                      <span className="text-[11px] text-text-muted">Frames to keep lost tracks</span>
                    </div>
                    <input type="number" defaultValue="30" className="input w-24 text-sm text-center" />
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Enable Uncertainty</label>
                      <span className="text-[11px] text-text-muted">Bayesian confidence intervals</span>
                    </div>
                    <Toggle active={true} />
                  </div>
                </div>
              </div>

              {/* ── Webhooks ── */}
              <div className="space-y-5">
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-semibold text-text-muted uppercase tracking-[2px]">Webhooks</span>
                  <div className="flex-1 h-px bg-surface-light" />
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">n8n Webhook URL</label>
                      <span className="text-[11px] text-text-muted">Notification endpoint</span>
                    </div>
                    <input
                      type="text"
                      placeholder="https://n8n.example.com/webhook/..."
                      className="input w-72 text-sm"
                    />
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Enable Webhook</label>
                      <span className="text-[11px] text-text-muted">Send alerts to n8n</span>
                    </div>
                    <Toggle active={true} />
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">CSV Logging</label>
                      <span className="text-[11px] text-text-muted">Log metrics to CSV files</span>
                    </div>
                    <Toggle active={false} />
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <div>
                      <label className="text-sm text-text-secondary font-medium block">Export Directory</label>
                      <span className="text-[11px] text-text-muted">Path for exported data</span>
                    </div>
                    <input type="text" defaultValue="./data" className="input w-56 text-sm font-mono" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
