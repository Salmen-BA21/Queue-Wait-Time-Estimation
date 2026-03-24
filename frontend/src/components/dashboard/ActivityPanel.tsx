import { memo } from "react";
import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";

import type { ActivityItem } from "@/hooks/use-live-dashboard";

function getActivityCardClassName(severity: "info" | "warning" | "success" | "critical"): string {
  if (severity === "critical") {
    return "border-destructive/40 bg-destructive/10";
  }
  if (severity === "warning") {
    return "border-amber-500/40 bg-amber-500/10";
  }
  if (severity === "success") {
    return "border-emerald-500/30 bg-emerald-500/10";
  }
  return "border-border bg-card";
}

function getActivityTextClassName(severity: "info" | "warning" | "success" | "critical"): string {
  if (severity === "critical") {
    return "text-destructive";
  }
  if (severity === "warning") {
    return "text-amber-100";
  }
  if (severity === "success") {
    return "text-emerald-100";
  }
  return "text-foreground";
}

/**
 * Displays the recent dashboard activity stream.
 */
function ActivityPanelComponent({ activity }: { activity: ActivityItem[] }) {
  return (
    <div>
      <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Activity className="h-4 w-4 text-primary" />
        Recent Activity
      </h2>
      <div className="space-y-2">
        {activity.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-3 text-sm">
            <p className="text-xs leading-relaxed text-foreground">No live feed activity yet.</p>
            <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">Waiting for the first WebSocket event</p>
          </div>
        )}
        {activity.map((item) => (
          <div
            key={item.id}
            className={`rounded-lg border p-3 text-sm transition-all hover:bg-accent/50 ${getActivityCardClassName(item.severity)}`}
          >
            <div className="flex items-start gap-2">
              {item.severity === "critical" ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
              ) : item.severity === "warning" ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
              ) : item.severity === "success" ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
              ) : (
                <Activity className="mt-0.5 h-4 w-4 text-primary" />
              )}
              <div>
                <p className={`text-xs leading-relaxed ${getActivityTextClassName(item.severity)}`}>{item.message}</p>
                <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">{item.time}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export const ActivityPanel = memo(ActivityPanelComponent);