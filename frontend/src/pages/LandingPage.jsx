import { Link } from 'react-router-dom';
import { Header, Footer } from '../components/layout';
import {
  Eye,
  ArrowRight,
  Camera,
  Users,
  Brain,
  BarChart3,
  Gauge,
  Shield,
  Bell,
  Database,
  Github,
  Zap,
  Clock,
  Target,
} from 'lucide-react';

/* ── Steps data ── */
const steps = [
  {
    num: '01',
    icon: Camera,
    title: 'Video Capture',
    desc: 'Connect any RTSP/USB camera or video file. Frames are grabbed in a dedicated thread for zero-lag processing.',
  },
  {
    num: '02',
    icon: Users,
    title: 'Person Detection',
    desc: 'YOLO v11/v26 models detect people with high accuracy. Bounding boxes are filtered to your defined queue zones.',
  },
  {
    num: '03',
    icon: Brain,
    title: 'Tracking & Timing',
    desc: 'Each person is assigned a unique ID via centroid tracking. Entry/exit timestamps measure actual wait durations.',
  },
  {
    num: '04',
    icon: BarChart3,
    title: 'Queue Analytics',
    desc: 'Real-time metrics: queue length, average wait time, and Bayesian uncertainty intervals — logged and visualized.',
  },
];

/* ── Features data ── */
const features = [
  { icon: Eye, title: 'Real-Time Detection', desc: 'YOLO-powered person detection running at 30+ FPS on GPU hardware.' },
  { icon: Gauge, title: 'Wait-Time Estimation', desc: 'Accurate per-person timing with entry/exit tracking across zones.' },
  { icon: Shield, title: 'Uncertainty Quantification', desc: 'Bayesian confidence intervals so you know how reliable each estimate is.' },
  { icon: Bell, title: 'Webhook Alerts', desc: 'Instant notifications via n8n when queue thresholds are exceeded.' },
  { icon: Database, title: 'CSV & API Logging', desc: 'All metrics persisted for historical analysis and dashboarding.' },
  { icon: Camera, title: 'Multi-Zone Support', desc: 'Define multiple queue zones per camera with polygon drawing tools.' },
];

/* ── Tech logos ── */
const techStack = [
  { name: 'Python', desc: 'Core Runtime' },
  { name: 'YOLO', desc: 'Object Detection' },
  { name: 'OpenCV', desc: 'Computer Vision' },
  { name: 'FastAPI', desc: 'API Backend' },
  { name: 'React', desc: 'Frontend UI' },
  { name: 'Docker', desc: 'Deployment' },
];

/* ── Stats ── */
const stats = [
  { value: '30+', label: 'FPS Processing', icon: Zap },
  { value: '99.2%', label: 'Detection Accuracy', icon: Target },
  { value: '<50ms', label: 'Latency', icon: Clock },
  { value: '24/7', label: 'Monitoring', icon: Eye },
];

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen bg-primary">
      <Header />

      {/* ══ Hero ══ */}
      <section className="gradient-bg-hero flex flex-col items-center text-center px-8 pt-20 pb-24 gap-7 relative overflow-hidden">
        {/* Background glow orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple/5 rounded-full blur-3xl" />

        {/* Badge */}
        <span className="animate-fade-in-up inline-flex items-center gap-2 bg-surface-light/50 border border-accent/20 rounded-full px-5 py-2 text-xs font-mono text-accent backdrop-blur-sm">
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
          Computer Vision + Bayesian AI
        </span>

        <h1 className="animate-fade-in-up delay-100 text-5xl md:text-6xl lg:text-7xl font-bold leading-[1.08] max-w-[900px] tracking-tight">
          Intelligent Queue{' '}
          <span className="text-accent text-glow-cyan">Monitoring</span>
        </h1>

        <p className="animate-fade-in-up delay-200 text-text-secondary text-lg md:text-xl max-w-[750px] leading-relaxed">
          Real-time wait-time estimation powered by computer vision. Detect people, track movement,
          and estimate wait times with Bayesian uncertainty quantification — from any camera feed.
        </p>

        {/* CTA buttons */}
        <div className="animate-fade-in-up delay-300 flex items-center gap-4 mt-2">
          <Link to="/dashboard" className="btn-primary text-sm">
            Start Monitoring <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="https://github.com/Salmen-BA21/Queue-Wait-Time-Estimation"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost text-sm"
          >
            <Github className="w-4 h-4" /> View on GitHub
          </a>
        </div>

        {/* Dashboard preview */}
        <div className="animate-fade-in-up delay-500 mt-10 w-full max-w-[1000px] relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-accent/20 via-purple/10 to-accent/20 rounded-2xl blur-lg opacity-50 group-hover:opacity-80 transition-opacity duration-500" />
          <div className="relative rounded-xl overflow-hidden border border-surface-light/50 shadow-2xl">
            <img
              src="/dashboard-preview.png"
              alt="QueueVision Dashboard Preview"
              className="w-full h-auto object-cover"
            />
            {/* Overlay gradient */}
            <div className="absolute inset-0 bg-gradient-to-t from-primary/60 via-transparent to-transparent" />
          </div>
        </div>
      </section>

      {/* ══ Stats Bar ══ */}
      <section className="bg-surface border-y border-surface-light">
        <div className="max-w-6xl mx-auto px-8 py-8 grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map((s, i) => (
            <div
              key={s.label}
              className={`animate-fade-in-up flex items-center gap-4 ${i < 3 ? 'md:border-r md:border-surface-light' : ''} md:pr-6`}
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <s.icon className="w-5 h-5 text-accent" />
              </div>
              <div>
                <p className="text-2xl font-bold font-mono text-white">{s.value}</p>
                <p className="text-text-muted text-xs">{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ══ How It Works ══ */}
      <section id="how-it-works" className="flex flex-col items-center px-8 py-24 gap-12 gradient-bg-subtle">
        <div className="text-center space-y-4">
          <span className="text-accent text-xs font-mono font-semibold tracking-[3px] uppercase">
            How It Works
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-center leading-tight">
            From Camera Feed to<br />Actionable Insights
          </h2>
          <p className="text-text-secondary text-lg max-w-[700px] mx-auto leading-relaxed">
            Four-stage pipeline processes video in real time to deliver accurate queue metrics with confidence intervals.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full max-w-6xl">
          {steps.map((s, i) => (
            <div
              key={s.num}
              className="card p-6 flex flex-col gap-4 animate-fade-in-up relative group"
              style={{ animationDelay: `${i * 150}ms` }}
            >
              {/* Step number */}
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-mono text-sm font-bold group-hover:bg-accent/20 transition-colors">
                  {s.num}
                </div>
                <s.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="text-lg font-semibold">{s.title}</h3>
              <p className="text-text-secondary text-sm leading-relaxed">{s.desc}</p>

              {/* Connector arrow */}
              {i < 3 && (
                <div className="hidden lg:block absolute -right-4 top-1/2 -translate-y-1/2 text-accent/30 z-10">
                  <ArrowRight className="w-5 h-5" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ══ Features ══ */}
      <section id="features" className="flex flex-col items-center bg-surface px-8 py-24 gap-12">
        <div className="text-center space-y-4">
          <span className="text-accent text-xs font-mono font-semibold tracking-[3px] uppercase">
            Features
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-center leading-tight">
            Everything You Need for<br />Queue Intelligence
          </h2>
          <p className="text-text-secondary text-lg max-w-[680px] mx-auto">
            A complete pipeline from video capture to actionable insights, built with production-grade tools.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-6xl">
          {features.map((f, i) => (
            <div
              key={f.title}
              className="card bg-primary p-6 flex flex-col gap-4 animate-fade-in-up"
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="w-12 h-12 rounded-xl bg-accent/10 border border-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
                <f.icon className="w-5 h-5 text-accent" />
              </div>
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="text-text-secondary text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ══ Tech Stack ══ */}
      <section id="tech-stack" className="flex flex-col items-center px-8 py-24 gap-12">
        <div className="text-center space-y-4">
          <span className="text-accent text-xs font-mono font-semibold tracking-[3px] uppercase">
            Tech Stack
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-center">Built With Industry-Leading Tools</h2>
        </div>

        <div className="flex flex-wrap justify-center gap-5">
          {techStack.map((t, i) => (
            <div
              key={t.name}
              className="card px-8 py-6 text-center min-w-[140px] animate-fade-in-up"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <span className="text-white font-semibold block">{t.name}</span>
              <span className="text-text-muted text-xs mt-1 block">{t.desc}</span>
            </div>
          ))}
        </div>
      </section>

      <Footer />
    </div>
  );
}
