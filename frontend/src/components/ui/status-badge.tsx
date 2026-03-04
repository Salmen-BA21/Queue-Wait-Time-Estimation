import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: "online" | "offline" | "warning";
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium",
        status === "online" && "bg-success/15 text-success",
        status === "offline" && "bg-destructive/15 text-destructive",
        status === "warning" && "bg-warning/15 text-warning",
        className
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "online" && "bg-success animate-glow-pulse",
          status === "offline" && "bg-destructive",
          status === "warning" && "bg-warning animate-glow-pulse"
        )}
      />
      {label || status}
    </div>
  );
}
