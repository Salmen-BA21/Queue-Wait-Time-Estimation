import { Eye, BarChart3, Camera, Zap, ArrowRight, Shield, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

const features = [
  {
    icon: Camera,
    title: "Real-Time Monitoring",
    description: "Track queue activity across multiple camera feeds with live person detection and counting.",
  },
  {
    icon: BarChart3,
    title: "AI-Powered Analytics",
    description: "Get predictive wait times, trend analysis, and actionable insights powered by computer vision.",
  },
  {
    icon: Zap,
    title: "Zone Configuration",
    description: "Define queue zones with polygon drawing tools and get per-zone metrics instantly.",
  },
  {
    icon: Shield,
    title: "Smart Alerts",
    description: "Automated notifications when thresholds are exceeded. Integrate with n8n webhooks.",
  },
  {
    icon: Clock,
    title: "Wait Time Estimation",
    description: "ML-based wait time predictions with confidence intervals for better customer experience.",
  },
  {
    icon: Eye,
    title: "Multi-Camera Support",
    description: "Monitor unlimited camera feeds simultaneously with a unified dashboard view.",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-border/50 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 glow-border">
            <Eye className="h-5 w-5 text-primary" />
          </div>
          <span className="text-lg font-bold tracking-tight text-foreground">QueueVision</span>
        </div>
        <Button onClick={() => navigate("/dashboard")} size="sm">
          Open Dashboard <ArrowRight className="h-4 w-4 ml-1" />
        </Button>
      </nav>

      {/* Hero */}
      <section className="relative px-6 pt-24 pb-20 max-w-7xl mx-auto text-center">
        {/* Glow bg */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary/5 rounded-full blur-[120px] pointer-events-none" />

        <div className="relative space-y-6 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-glow-pulse" />
            AI-Powered Queue Intelligence
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-foreground leading-[1.1]">
            See Your Queues
            <br />
            <span className="text-primary">Like Never Before</span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg text-muted-foreground">
            Computer vision meets queue management. Monitor wait times, track people flow, and get AI-driven insights — all in real time.
          </p>

          <div className="flex items-center justify-center gap-4 pt-4">
            <Button size="lg" onClick={() => navigate("/dashboard")} className="glow-cyan">
              Launch Dashboard <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
            <Button variant="outline" size="lg" onClick={() => navigate("/analytics")}>
              View Analytics
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div
          className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6 animate-fade-in-up"
          style={{ animationDelay: "0.2s", opacity: 0 }}
        >
          {[
            { label: "Cameras Active", value: "24" },
            { label: "People Tracked", value: "1.2K" },
            { label: "Avg Wait Time", value: "4.2m" },
            { label: "Alerts Today", value: "7" },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg border border-border bg-card/50 p-5 glass">
              <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-20 max-w-7xl mx-auto">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold text-foreground">Everything You Need</h2>
          <p className="mt-3 text-muted-foreground">Powerful tools for intelligent queue management</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((feature, i) => (
            <div
              key={feature.title}
              className="group rounded-lg border border-border bg-card p-6 transition-all hover:glow-border hover:-translate-y-0.5 animate-fade-in-up"
              style={{ animationDelay: `${i * 0.1}s`, opacity: 0 }}
            >
              <div className="mb-4 inline-flex rounded-lg bg-primary/10 p-2.5">
                <feature.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-base font-semibold text-foreground mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 px-6 py-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-muted-foreground">
          <span>© 2026 QueueVision. AI-powered queue monitoring.</span>
          <span className="font-mono">v1.0.0</span>
        </div>
      </footer>
    </div>
  );
}
