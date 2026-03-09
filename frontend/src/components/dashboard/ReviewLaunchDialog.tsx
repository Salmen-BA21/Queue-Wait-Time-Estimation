import { Camera, Play, Save, Store, Video } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ModelSize } from "@/lib/api";

interface ReviewLaunchDialogProps {
  open: boolean;
  feedName: string;
  sourceMode: "rtsp" | "file" | "onvif";
  sourceLabel: string;
  sourceDetail: string;
  modelSize: ModelSize;
  zonePointCount: number;
  establishmentName?: string | null;
  caisseName?: string | null;
  hasSavedCaisseZone: boolean;
  isSubmitting: boolean;
  onBack: () => void;
  onSave: () => void;
  onLaunch: () => void;
  onOpenChange: (open: boolean) => void;
}

function getSourceModeLabel(sourceMode: ReviewLaunchDialogProps["sourceMode"]): string {
  if (sourceMode === "file") {
    return "Uploaded video";
  }
  if (sourceMode === "onvif") {
    return "ONVIF camera";
  }
  return "RTSP camera";
}

export function ReviewLaunchDialog({
  open,
  feedName,
  sourceMode,
  sourceLabel,
  sourceDetail,
  modelSize,
  zonePointCount,
  establishmentName,
  caisseName,
  hasSavedCaisseZone,
  isSubmitting,
  onBack,
  onSave,
  onLaunch,
  onOpenChange,
}: ReviewLaunchDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-foreground">Review and Launch</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Check the full feed configuration before saving it to the dashboard or launching the worker immediately.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{getSourceModeLabel(sourceMode)}</Badge>
            <Badge variant="outline">YOLO {modelSize.toUpperCase()}</Badge>
            {hasSavedCaisseZone && <Badge variant="outline">Saved caisse zone</Badge>}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-background/40 p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2 text-primary">
                  {sourceMode === "file" ? <Video className="h-5 w-5" /> : <Camera className="h-5 w-5" />}
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Source summary</p>
                  <p className="text-sm text-muted-foreground">{sourceLabel}</p>
                  <p className="text-xs text-muted-foreground">{sourceDetail}</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-background/40 p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2 text-primary">
                  <Store className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Metadata</p>
                  <p className="text-sm text-muted-foreground">{establishmentName ?? "No establishment assigned"}</p>
                  <p className="text-xs text-muted-foreground">{caisseName ?? "No caisse assigned"}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 rounded-xl border border-border bg-background/40 p-4 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Feed Name</p>
              <p className="mt-1 font-medium text-foreground">{feedName || "Untitled feed"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Model Size</p>
              <p className="mt-1 font-medium text-foreground">YOLO {modelSize.toUpperCase()}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Zone State</p>
              <p className="mt-1 font-medium text-foreground">{zonePointCount > 0 ? `${zonePointCount} points` : hasSavedCaisseZone ? "Saved caisse zone" : "Configure later"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Launch Mode</p>
              <p className="mt-1 font-medium text-foreground">Save only or start now</p>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
            Saving keeps the feed in the dashboard with status `created`. Launching immediately creates the feed and then starts the analysis worker from the web app, matching the desktop review step more closely.
          </div>
        </div>

        <DialogFooter>
          <Button onClick={onBack} type="button" variant="outline" disabled={isSubmitting}>
            Back
          </Button>
          <Button onClick={onSave} type="button" variant="outline" disabled={isSubmitting}>
            <Save className="mr-2 h-4 w-4" />
            {isSubmitting ? "Saving..." : "Save Feed"}
          </Button>
          <Button onClick={onLaunch} type="button" disabled={isSubmitting}>
            <Play className="mr-2 h-4 w-4" />
            {isSubmitting ? "Launching..." : "Create and Start"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}