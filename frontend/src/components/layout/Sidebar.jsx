import { Link, useLocation } from 'react-router-dom';
import {
  Eye,
  LayoutDashboard,
  BarChart3,
  Map,
  Flame,
  Settings,
  LogOut,
  ChevronRight,
} from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/zone-editor', icon: Map, label: 'Zone Editor' },
  { to: '/heatmap', icon: Flame, label: 'Heatmap' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="w-[260px] min-w-[260px] h-screen bg-surface border-r border-surface-light flex flex-col sticky top-0">
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 px-6 py-5 border-b border-surface-light group">
        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center transition-all duration-300 group-hover:bg-accent/20">
          <Eye className="w-5 h-5 text-accent" />
        </div>
        <span className="text-lg font-bold text-white tracking-tight">
          Queue<span className="text-accent">Vision</span>
        </span>
      </Link>

      {/* Section label */}
      <div className="px-6 pt-5 pb-2">
        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-[2px]">
          Navigation
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 pb-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => {
          const isActive = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group relative ${isActive
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-secondary hover:text-white hover:bg-surface-light/50'
                }`}
            >
              {/* Active indicator bar */}
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-accent rounded-r-full" />
              )}
              <Icon className={`w-[18px] h-[18px] transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-accent' : ''}`} />
              <span className="flex-1">{label}</span>
              {isActive && (
                <ChevronRight className="w-3.5 h-3.5 text-accent/50" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="px-3 pb-3 space-y-2">
        {/* User */}
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-surface-light/30">
          <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent">
            SA
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">Salmen BA</p>
            <p className="text-[11px] text-text-muted truncate">Admin</p>
          </div>
          <LogOut className="w-4 h-4 text-text-muted hover:text-white cursor-pointer transition-colors" />
        </div>

        {/* Version badge */}
        <div className="flex items-center justify-center gap-2 py-2 text-[11px] text-text-muted font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          v1.0.0 — Phase 5
        </div>
      </div>
    </aside>
  );
}
