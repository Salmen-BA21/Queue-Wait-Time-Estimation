import { memo } from "react";
import { AlertTriangle } from "lucide-react";

interface AttentionItem {
  id: string;
  title: string;
  detail: string;
  tone: "critical" | "warning";
}

/**
 * Displays the feeds that currently require operator attention.
 */
function AttentionPanelComponent({ items }: { items: AttentionItem[] }) {
  return (
    <div>
      <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <AlertTriangle className="h-4 w-4 text-primary" />
        Attention Required
      </h2>
      <div className="mt-2 space-y-2">
        {items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-3 text-sm">
            <p className="text-xs leading-relaxed text-foreground">No feeds currently require immediate operator action.</p>
            <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">Stable queue metrics and worker states across the wall</p>
          </div>
        ) : (
          items.map((item) => (
            <div
              key={item.id}
              className={`rounded-lg border p-3 text-sm ${item.tone === "critical" ? "border-destructive/40 bg-destructive/10" : "border-amber-500/40 bg-amber-500/10"}`}
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className={`mt-0.5 h-4 w-4 ${item.tone === "critical" ? "text-destructive" : "text-amber-300"}`} />
                <div className="space-y-1">
                  <p className={`text-xs font-semibold ${item.tone === "critical" ? "text-destructive" : "text-amber-100"}`}>{item.title}</p>
                  <p className={`text-xs leading-relaxed ${item.tone === "critical" ? "text-destructive/90" : "text-amber-50"}`}>{item.detail}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export const AttentionPanel = memo(AttentionPanelComponent);