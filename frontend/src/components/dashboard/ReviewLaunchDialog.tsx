import { Camera, Pencil, Play, Save, Store, Trash2, Video } from "lucide-react";

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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { LogLevel, ModelSize } from "@/lib/api";

export interface ReviewLaunchItem {
  clientId: string;
  feedName: string;
  sourceMode: "rtsp" | "file" | "onvif";
  sourceLabel: string;
  sourceDetail: string;
  modelSize: ModelSize;
  zonePointCount: number;
  establishmentName?: string | null;
  caisseName?: string | null;
  hasSavedCaisseZone: boolean;
  isCurrentDraft?: boolean;
}

interface ReviewLaunchDialogProps {
  open: boolean;
  items: ReviewLaunchItem[];
  canSubmitBatch: boolean;
  logLevel: LogLevel;
  webhookEnabled: boolean;
  isSubmitting: boolean;
  stageButtonLabel?: string;
  onBack: () => void;
  onLogLevelChange: (value: LogLevel) => void;
  onWebhookEnabledChange: (enabled: boolean) => void;
  onStageCurrent?: () => void;
  onEditItem: (clientId: string) => void;
  onRemoveItem: (clientId: string) => void;
  onSave: () => void;
  onLaunch: () => void;
  onOpenChange: (open: boolean) => void;
}

function getSourceModeLabel(sourceMode: ReviewLaunchItem["sourceMode"]): string {
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
  items,
  canSubmitBatch,
  logLevel,
  webhookEnabled,
  isSubmitting,
  stageButtonLabel = "Add To Batch",
  onBack,
  onLogLevelChange,
  onWebhookEnabledChange,
  onStageCurrent,
  onEditItem,
  onRemoveItem,
  onSave,
  onLaunch,
  onOpenChange,
}: ReviewLaunchDialogProps) {
  const currentDraft = items.find((item) => item.isCurrentDraft) ?? null;
  const stagedItems = items.filter((item) => !item.isCurrentDraft);
  const selectedCount = items.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-foreground">Review and Launch</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Review the staged sources, edit or remove individual drafts, then save or launch the full batch from one place.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-3 rounded-xl border border-border bg-background/40 p-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Queue Size</p>
              <p className="mt-1 font-medium text-foreground">{selectedCount} source{selectedCount === 1 ? "" : "s"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Currently Prepared</p>
              <p className="mt-1 font-medium text-foreground">{selectedCount} source{selectedCount === 1 ? "" : "s"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Launch Gate</p>
              <p className="mt-1 font-medium text-foreground">{canSubmitBatch ? "Ready for batch submit" : "Add at least one source"}</p>
            </div>
          </div>

          {currentDraft && (
            <div className="space-y-3 rounded-xl border border-primary/40 bg-primary/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Current draft</p>
                  <p className="text-xs text-muted-foreground">This source is configured but not yet staged with the rest of the batch.</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{getSourceModeLabel(currentDraft.sourceMode)}</Badge>
                  <Badge variant="outline">YOLO {currentDraft.modelSize.toUpperCase()}</Badge>
                  {currentDraft.hasSavedCaisseZone && <Badge variant="outline">Saved caisse zone</Badge>}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-border bg-background/40 p-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary">
                      {currentDraft.sourceMode === "file" ? <Video className="h-5 w-5" /> : <Camera className="h-5 w-5" />}
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">Source summary</p>
                      <p className="text-sm text-muted-foreground">{currentDraft.sourceLabel}</p>
                      <p className="text-xs text-muted-foreground">{currentDraft.sourceDetail}</p>
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
                      <p className="text-sm text-muted-foreground">{currentDraft.establishmentName ?? "No establishment assigned"}</p>
                      <p className="text-xs text-muted-foreground">{currentDraft.caisseName ?? "No caisse assigned"}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 rounded-xl border border-border bg-background/40 p-4 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Feed Name</p>
                  <p className="mt-1 font-medium text-foreground">{currentDraft.feedName || "Untitled feed"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Model Size</p>
                  <p className="mt-1 font-medium text-foreground">YOLO {currentDraft.modelSize.toUpperCase()}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Zone State</p>
                  <p className="mt-1 font-medium text-foreground">{currentDraft.zonePointCount > 0 ? `${currentDraft.zonePointCount} points` : currentDraft.hasSavedCaisseZone ? "Saved caisse zone" : "Configure later"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/70">Batch Action</p>
                  <p className="mt-1 font-medium text-foreground">Stage now or submit with batch</p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div className="rounded-xl border border-border bg-background/40 p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Global launch settings</p>
                  <p className="text-xs text-muted-foreground">
                    These settings apply to every feed in this batch and are not configured per source.
                  </p>
                </div>
                <Badge variant="outline">Shared across batch</Badge>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-foreground">Worker log level</Label>
                  <Select value={logLevel} onValueChange={(value) => onLogLevelChange(value as LogLevel)} disabled={isSubmitting}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select log level" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DEBUG">DEBUG</SelectItem>
                      <SelectItem value="INFO">INFO</SelectItem>
                      <SelectItem value="WARNING">WARNING</SelectItem>
                      <SelectItem value="ERROR">ERROR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between rounded-lg border border-border bg-background/50 px-4 py-3">
                  <div className="space-y-1 pr-4">
                    <p className="text-sm font-medium text-foreground">Webhook delivery</p>
                    <p className="text-xs text-muted-foreground">
                      Disable this to prevent all feeds in the batch from sending queue metrics to the configured webhook.
                    </p>
                  </div>
                  <Switch checked={webhookEnabled} onCheckedChange={onWebhookEnabledChange} disabled={isSubmitting} />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">Staged feeds</p>
                <p className="text-xs text-muted-foreground">Edit or remove pending sources before the batch is submitted.</p>
              </div>
              <Badge variant="outline">{stagedItems.length} staged</Badge>
            </div>

            {stagedItems.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border bg-background/50 p-4 text-sm text-muted-foreground">
                No feeds are staged yet. Stage the current draft or go back to add sources before launching the batch.
              </div>
            ) : (
              <div className="grid gap-3">
                {stagedItems.map((item) => (
                  <div key={item.clientId} className="rounded-xl border border-border bg-background/40 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-foreground">{item.feedName}</p>
                          <Badge variant="outline">{getSourceModeLabel(item.sourceMode)}</Badge>
                          <Badge variant="outline">YOLO {item.modelSize.toUpperCase()}</Badge>
                          {item.hasSavedCaisseZone && <Badge variant="outline">Saved caisse zone</Badge>}
                        </div>
                        <p className="text-sm text-muted-foreground">{item.sourceLabel}</p>
                        <p className="text-xs text-muted-foreground">{item.sourceDetail}</p>
                        <p className="text-xs text-muted-foreground">
                          {item.establishmentName ?? "No establishment"} · {item.caisseName ?? "No caisse"} · {item.zonePointCount > 0 ? `${item.zonePointCount} zone points` : "Zone optional"}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <Button onClick={() => onEditItem(item.clientId)} size="sm" type="button" variant="outline" disabled={isSubmitting}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </Button>
                        <Button onClick={() => onRemoveItem(item.clientId)} size="sm" type="button" variant="outline" disabled={isSubmitting}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Remove
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
            Saving keeps every batch item in the dashboard with status `created`. Launching immediately creates each feed and then starts its analysis worker, matching the desktop multi-source review step more closely.
          </div>
          {!canSubmitBatch && (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-100">
              Add at least one staged source before saving or launching the batch.
            </div>
          )}
        </div>

        <DialogFooter>
          <Button onClick={onBack} type="button" variant="outline" disabled={isSubmitting}>
            Back
          </Button>
          {onStageCurrent && currentDraft && (
            <Button onClick={onStageCurrent} type="button" variant="outline" disabled={isSubmitting}>
              <Save className="mr-2 h-4 w-4" />
              {stageButtonLabel}
            </Button>
          )}
          <Button onClick={onSave} type="button" variant="outline" disabled={isSubmitting || !canSubmitBatch || items.length === 0}>
            <Save className="mr-2 h-4 w-4" />
            {isSubmitting ? "Saving..." : "Save Batch"}
          </Button>
          <Button onClick={onLaunch} type="button" disabled={isSubmitting || !canSubmitBatch || items.length === 0}>
            <Play className="mr-2 h-4 w-4" />
            {isSubmitting ? "Launching..." : "Create and Start Batch"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}