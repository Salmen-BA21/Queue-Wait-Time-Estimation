import { Link } from 'react-router-dom';
import { Eye } from 'lucide-react';

export default function Header() {
  return (
    <header className="w-full flex items-center justify-between px-8 md:px-15 py-4 glass-strong sticky top-0 z-50 animate-fade-in-down">
      {/* Gradient bottom border */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />

      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 group">
        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center group-hover:glow-cyan transition-all duration-300">
          <Eye className="w-5 h-5 text-accent" />
        </div>
        <span className="text-xl font-bold text-white tracking-tight">
          Queue<span className="text-accent">Vision</span>
        </span>
      </Link>

      {/* Nav Links */}
      <nav className="hidden md:flex items-center gap-8">
        {[
          { href: '#how-it-works', label: 'How It Works' },
          { href: '#features', label: 'Features' },
          { href: '#tech-stack', label: 'Tech Stack' },
        ].map(({ href, label }) => (
          <a
            key={href}
            href={href}
            className="text-text-secondary hover:text-white transition-colors text-sm font-medium relative group"
          >
            {label}
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-accent rounded-full transition-all duration-300 group-hover:w-full" />
          </a>
        ))}
        <Link
          to="/dashboard"
          className="text-text-secondary hover:text-white transition-colors text-sm font-medium relative group"
        >
          Dashboard
          <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-accent rounded-full transition-all duration-300 group-hover:w-full" />
        </Link>
      </nav>

      {/* CTA */}
      <Link
        to="/dashboard"
        className="btn-primary text-sm"
      >
        Open Dashboard
      </Link>
    </header>
  );
}
