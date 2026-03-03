import { useState, useEffect } from 'react';
import { Bell, Search, Calendar } from 'lucide-react';

const badgeConfig = {
  Dashboard: { className: 'badge-live', label: 'LIVE', dot: true },
  Analytics: { className: 'badge-analytics', label: 'ANALYTICS', dot: false },
  'Zone Editor': { className: 'badge-zone', label: 'ZONE EDITOR', dot: false },
  Heatmap: { className: 'badge-heatmap', label: 'HEATMAP', dot: false },
  Settings: { className: 'badge-settings', label: 'SETTINGS', dot: false },
};

export default function TopBar({ title = 'Dashboard' }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const badge = badgeConfig[title] || badgeConfig.Dashboard;

  return (
    <div className="h-[56px] w-full bg-surface border-b border-surface-light flex items-center justify-between px-6">
      {/* Left: title + badge */}
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-white">{title}</h1>
        <span className={`badge ${badge.className}`}>
          {badge.dot && <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />}
          {badge.label}
        </span>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-4">
        {/* Date / Time */}
        <div className="hidden md:flex items-center gap-2 text-text-muted text-xs font-mono">
          <Calendar className="w-3.5 h-3.5" />
          <span>
            {time.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
          <span className="text-accent/60">|</span>
          <span className="text-text-secondary tabular-nums">
            {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>

        {/* Separator */}
        <div className="hidden md:block w-px h-6 bg-surface-light" />

        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search..."
            className="input bg-surface-light/50 pl-9 pr-4 py-1.5 text-sm w-48 focus:w-56 transition-all duration-300"
          />
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-surface-light transition-colors group">
          <Bell className="w-5 h-5 text-text-secondary group-hover:text-white transition-colors" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-danger rounded-full animate-pulse" />
        </button>

        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-accent/15 border border-accent/20 flex items-center justify-center cursor-pointer hover:border-accent/40 transition-colors">
          <span className="text-[11px] font-bold text-accent">SA</span>
        </div>
      </div>
    </div>
  );
}
