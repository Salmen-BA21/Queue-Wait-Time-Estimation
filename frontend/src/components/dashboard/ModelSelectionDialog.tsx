import { Cpu, Rabbit, ScanSearch, ShieldCheck, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ModelSize } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ModelSelectionDialogProps {
  open: boolean;
  feedName: string;
  sourceMode: "rtsp" | "file" | "onvif";
  zonePointCount: number;
  establishmentName?: string | null;
  caisseName?: string | null;
  selectedModel: ModelSize;
  isSubmitting: boolean;
  sourceOptions?: Array<{
    key: string;
    label: string;
  }>;
  selectedSourceKey?: string;
  onBack: () => void;
  onConfirm: () => void;
  onModelChange: (model: ModelSize) => void;
  onSelectedSourceChange?: (sourceKey: string) => void;
  onOpenChange: (open: boolean) => void;
}

const MODEL_OPTIONS: Array<{
  value: ModelSize;
  label: string;
  description: string;
  note: string;
  icon: typeof Rabbit;
}> = [
  {
    value: "n",
    label: "Nano",
    description: "Fastest setup for quick validation and lightweight machines.",
    note: "Best for rapid iteration",
    icon: Rabbit,
  },
  {
    value: "s",
    label: "Small",
    description: "Balanced choice when you want better detection quality without a large hit.",
    note: "Good default for development",
    icon: Zap,
  },
  {
    value: "m",
    label: "Medium",
    description: "More accurate across crowded scenes with a moderate compute budget.",
    note: "Solid for denser queues",
    icon: Cpu,
  },
  {
    value: "l",
    label: "Large",
    description: "Higher accuracy for harder scenes when your GPU budget allows it.",
    note: "Heavier runtime cost",
    icon: ScanSearch,
  },
  {
    value: "x",
    label: "X-Large",
    description: "Maximum accuracy target for controlled, powerful environments.",
    note: "Slowest option",
    icon: ShieldCheck,
  },
];

export function ModelSelectionDialog({
  open,
  feedName,
  sourceMode,
  zonePointCount,
  establishmentName,
  caisseName,
  selectedModel,
  isSubmitting,
  sourceOptions = [],
  selectedSourceKey,
  onBack,
  onConfirm,
  onModelChange,
  onSelectedSourceChange,
  onOpenChange,
}: ModelSelectionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border bg-card sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-foreground">Choose Model</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Finalize {feedName || "your feed"} with the YOLO model size you want to run.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {sourceOptions.length > 1 && onSelectedSourceChange && selectedSourceKey ? (
            <div className="grid gap-2 rounded-xl border border-border bg-background/40 p-4 sm:max-w-sm">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground/70">Selected sources</span>
              <Select onValueChange={onSelectedSourceChange} value={selectedSourceKey}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a source" />
                </SelectTrigger>
                <SelectContent>
                  {sourceOptions.map((option) => (
                    <SelectItem key={option.key} value={option.key}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Switch sources here to assign a different YOLO model to each selected video or stream.</p>
            </div>
          ) : null}

          <div className="grid gap-3 rounded-xl border border-border bg-background/40 p-4 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Source Type</p>
              <p className="mt-1 font-medium text-foreground">
                {sourceMode === "file" ? "Uploaded video" : sourceMode === "onvif" ? "ONVIF camera" : "RTSP camera"}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Feed Name</p>
              <p className="mt-1 font-medium text-foreground">{feedName || "Untitled feed"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Zone Points</p>
              <p className="mt-1 font-medium text-foreground">{zonePointCount > 0 ? zonePointCount : "Configured later"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Establishment</p>
              <p className="mt-1 font-medium text-foreground">{establishmentName ?? "Not assigned"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Caisse</p>
              <p className="mt-1 font-medium text-foreground">{caisseName ?? "Not assigned"}</p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {MODEL_OPTIONS.map((option) => {
              const Icon = option.icon;
              const isSelected = selectedModel === option.value;

              return (
                <button
                  key={option.value}
                  className={cn(
                    "rounded-xl border p-4 text-left transition-colors",
                    isSelected
                      ? "border-primary bg-primary/10 shadow-[0_0_0_1px_rgba(34,211,238,0.35)]"
                      : "border-border bg-background/40 hover:border-primary/50 hover:bg-background/70",
                  )}
                  onClick={() => onModelChange(option.value)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">
                        {option.value.toUpperCase()} · {option.label}
                      </p>
                      <p className="mt-1 text-xs text-primary">{option.note}</p>
                    </div>
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{option.description}</p>
                </button>
              );
            })}
          </div>
        </div>

        <DialogFooter>
          <Button onClick={onBack} type="button" variant="outline">
            Back
          </Button>
          <Button onClick={onConfirm} type="button" disabled={isSubmitting}>
            {isSubmitting ? "Preparing Review..." : "Continue to Review"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}