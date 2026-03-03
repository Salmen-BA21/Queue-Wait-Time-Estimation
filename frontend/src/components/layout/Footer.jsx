import { Eye, Github, Linkedin, Mail } from 'lucide-react';
import { Link } from 'react-router-dom';

const productLinks = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Analytics', to: '/analytics' },
  { label: 'Zone Editor', to: '/zone-editor' },
  { label: 'Heatmap', to: '/heatmap' },
];

const resourceLinks = ['Documentation', 'API Reference', 'GitHub', 'Support'];
const companyLinks = ['About', 'Blog', 'Contact', 'Privacy'];

export default function Footer() {
  return (
    <footer className="w-full bg-footer relative">
      {/* Gradient top border */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />

      {/* Top section */}
      <div className="max-w-7xl mx-auto px-8 md:px-16 pt-14 pb-10 grid grid-cols-1 md:grid-cols-4 gap-12">
        {/* Brand */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <Eye className="w-4 h-4 text-accent" />
            </div>
            <span className="text-lg font-bold text-white tracking-tight">
              Queue<span className="text-accent">Vision</span>
            </span>
          </div>
          <p className="text-text-muted text-sm leading-relaxed">
            AI-powered queue monitoring and wait-time estimation for smarter operations.
          </p>
          {/* Social icons */}
          <div className="flex items-center gap-3 mt-2">
            {[
              { icon: Github, href: 'https://github.com/Salmen-BA21/Queue-Wait-Time-Estimation' },
              { icon: Linkedin, href: '#' },
              { icon: Mail, href: '#' },
            ].map(({ icon: Icon, href }, i) => (
              <a
                key={i}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="w-8 h-8 rounded-lg bg-surface-light/50 flex items-center justify-center text-text-muted hover:text-accent hover:bg-accent/10 transition-all duration-200"
              >
                <Icon className="w-4 h-4" />
              </a>
            ))}
          </div>
        </div>

        {/* Product links */}
        <div>
          <h4 className="text-text-secondary text-xs font-semibold tracking-wider uppercase mb-5">
            Product
          </h4>
          <ul className="space-y-2.5">
            {productLinks.map(({ label, to }) => (
              <li key={label}>
                <Link to={to} className="text-text-muted text-sm hover:text-accent transition-colors">
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {/* Resource links */}
        <div>
          <h4 className="text-text-secondary text-xs font-semibold tracking-wider uppercase mb-5">
            Resources
          </h4>
          <ul className="space-y-2.5">
            {resourceLinks.map((item) => (
              <li key={item}>
                <a href="#" className="text-text-muted text-sm hover:text-accent transition-colors">
                  {item}
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Company links */}
        <div>
          <h4 className="text-text-secondary text-xs font-semibold tracking-wider uppercase mb-5">
            Company
          </h4>
          <ul className="space-y-2.5">
            {companyLinks.map((item) => (
              <li key={item}>
                <a href="#" className="text-text-muted text-sm hover:text-accent transition-colors">
                  {item}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-surface-light/50">
        <div className="max-w-7xl mx-auto px-8 md:px-16 py-5 flex flex-col md:flex-row items-center justify-between gap-3">
          <span className="text-text-muted text-sm">
            &copy; {new Date().getFullYear()} QueueVision. Built for PFE internship.
          </span>
          <span className="text-text-muted text-xs font-mono">
            YOLO &middot; OpenCV &middot; FastAPI &middot; React
          </span>
        </div>
      </div>
    </footer>
  );
}
