import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, RotateCcw, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ZonePoint } from "@/lib/api";

interface PreviewFrameResult {
  frameSrc: string;
  sourceLabel: string;
  sourceKind: string;
}

interface ZoneSelectionDialogProps {
  open: boolean;
  file: File | null;
  sourceLabel?: string;
  sourceKind?: string;
  loadPreviewFrame?: (() => Promise<PreviewFrameResult>) | null;
  feedName: string;
  points: ZonePoint[];
  onPointsChange: (points: ZonePoint[]) => void;
  onBack: () => void;
  onContinue: () => void;
  onOpenChange: (open: boolean) => void;
  backLabel?: string;
  continueLabel?: string;
  helperText?: string;
  isContinuing?: boolean;
}

function clamp(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function loadFirstFrame(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const video = document.createElement("video");

    const cleanup = () => {
      video.pause();
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(objectUrl);
    };

    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;

    video.onloadeddata = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");
        if (!context) {
          cleanup();
          reject(new Error("Unable to prepare the zone preview."));
          return;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
        cleanup();
        resolve(dataUrl);
      } catch (error) {
        cleanup();
        reject(error instanceof Error ? error : new Error("Unable to decode the selected video."));
      }
    };

    video.onerror = () => {
      cleanup();
      reject(new Error("The selected video could not be opened in the browser."));
    };

    video.src = objectUrl;
    video.load();
  });
}

export function ZoneSelectionDialog({
  open,
  file,
  sourceLabel,
  sourceKind,
  loadPreviewFrame,
  feedName,
  points,
  onPointsChange,
  onBack,
  onContinue,
  onOpenChange,
  backLabel = "Back",
  continueLabel = "Continue to Model",
  helperText = "Use the same workflow as the desktop GUI: capture a representative frame, draw the queue polygon, then continue to choose the model.",
  isContinuing = false,
}: ZoneSelectionDialogProps) {
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resolvedSourceLabel, setResolvedSourceLabel] = useState<string>(sourceLabel ?? file?.name ?? "No source selected");
  const [resolvedSourceKind, setResolvedSourceKind] = useState<string>(sourceKind ?? (file ? "Selected file" : "Camera source"));

  const reloadPreview = async () => {
    if (!open) {
      return;
    }

    setIsLoading(true);
    setPreviewError(null);

    try {
      if (file) {
        const src = await loadFirstFrame(file);
        setFrameSrc(src);
        setResolvedSourceLabel(sourceLabel ?? file.name);
        setResolvedSourceKind(sourceKind ?? "Selected file");
        return;
      }

      if (loadPreviewFrame) {
        const result = await loadPreviewFrame();
        setFrameSrc(result.frameSrc);
        setResolvedSourceLabel(result.sourceLabel);
        setResolvedSourceKind(result.sourceKind);
        return;
      }

      setFrameSrc(null);
      setResolvedSourceLabel(sourceLabel ?? "No source selected");
      setResolvedSourceKind(sourceKind ?? "Source preview");
      setPreviewError("No source is available for zone selection.");
    } catch (error) {
      setFrameSrc(null);
      setPreviewError(error instanceof Error ? error.message : "Unable to load the preview frame.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!open || (!file && !loadPreviewFrame)) {
      setFrameSrc(null);
      setPreviewError(null);
      setIsLoading(false);
      setResolvedSourceLabel(sourceLabel ?? file?.name ?? "No source selected");
      setResolvedSourceKind(sourceKind ?? (file ? "Selected file" : "Camera source"));
      return undefined;
    }

    let cancelled = false;
    void (async () => {
      setIsLoading(true);
      setPreviewError(null);

      try {
        if (file) {
          const src = await loadFirstFrame(file);
          if (!cancelled) {
            setFrameSrc(src);
            setResolvedSourceLabel(sourceLabel ?? file.name);
            setResolvedSourceKind(sourceKind ?? "Selected file");
          }
        } else if (loadPreviewFrame) {
          const result = await loadPreviewFrame();
          if (!cancelled) {
            setFrameSrc(result.frameSrc);
            setResolvedSourceLabel(result.sourceLabel);
            setResolvedSourceKind(result.sourceKind);
          }
        }
      } catch (error) {
        if (!cancelled) {
          setPreviewError(error instanceof Error ? error.message : "Unable to load the preview frame.");
          setFrameSrc(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [file, loadPreviewFrame, open, sourceKind, sourceLabel]);

  const handlePreviewClick = (event: React.MouseEvent<HTMLImageElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = clamp((event.clientX - bounds.left) / bounds.width);
    const y = clamp((event.clientY - bounds.top) / bounds.height);

    onPointsChange([
      ...points,
      {
        x: Number(x.toFixed(4)),
        y: Number(y.toFixed(4)),
      },
    ]);
  };

  const removeLastPoint = () => {
    onPointsChange(points.slice(0, -1));
  };

  const resetPoints = () => {
    onPointsChange([]);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="text-foreground">Select Queue Zone</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Click around the queue area for {feedName || resolvedSourceLabel || file?.name || "this feed"}. A minimum of 3 points is required.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background/40 p-3 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{resolvedSourceKind}:</span>
            <span className="font-mono text-xs">{resolvedSourceLabel}</span>
            <span className="rounded-full bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
              {points.length} point{points.length === 1 ? "" : "s"}
            </span>
          </div>

          <div className="rounded-xl border border-border bg-background/30 p-4">
            {isLoading && (
              <div className="flex min-h-[320px] items-center justify-center text-sm text-muted-foreground">
                Loading the first frame for zone selection...
              </div>
            )}

            {!isLoading && previewError && (
              <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-center text-sm text-destructive">
                <AlertTriangle className="h-8 w-8" />
                <p>{previewError}</p>
                {loadPreviewFrame && (
                  <Button onClick={() => void reloadPreview()} type="button" variant="outline">
                    <Loader2 className="mr-2 h-4 w-4" />
                    Retry Snapshot
                  </Button>
                )}
              </div>
            )}

            {!isLoading && !previewError && frameSrc && (
              <div className="overflow-auto">
                <div className="relative inline-block max-w-full">
                  <img
                    alt="Queue zone preview"
                    className="block max-h-[60vh] max-w-full rounded-lg border border-border object-contain"
                    onClick={handlePreviewClick}
                    src={frameSrc}
                  />
                  <svg
                    className="pointer-events-none absolute inset-0 h-full w-full"
                    preserveAspectRatio="none"
                    viewBox="0 0 1 1"
                  >
                    {points.length >= 2 && (
                      <polyline
                        fill="none"
                        points={points.map((point) => `${point.x},${point.y}`).join(" ")}
                        stroke="#22d3ee"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="0.006"
                      />
                    )}
                    {points.length >= 3 && (
                      <polygon
                        fill="rgba(34, 211, 238, 0.22)"
                        points={points.map((point) => `${point.x},${point.y}`).join(" ")}
                        stroke="#22d3ee"
                        strokeLinejoin="round"
                        strokeWidth="0.006"
                      />
                    )}
                    {points.map((point, index) => (
                      <g key={`${point.x}-${point.y}-${index}`}>
                        <circle
                          cx={point.x}
                          cy={point.y}
                          fill="#f8fafc"
                          r="0.012"
                          stroke="#22d3ee"
                          strokeWidth="0.006"
                        />
                        <text
                          fill="#f8fafc"
                          fontSize="0.04"
                          fontWeight="700"
                          x={Math.min(point.x + 0.018, 0.94)}
                          y={Math.max(point.y - 0.018, 0.06)}
                        >
                          {index + 1}
                        </text>
                      </g>
                    ))}
                  </svg>
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={removeLastPoint} type="button" variant="outline" disabled={points.length === 0}>
              <Undo2 className="mr-2 h-4 w-4" />
              Remove Last Point
            </Button>
            <Button onClick={resetPoints} type="button" variant="outline" disabled={points.length === 0}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset Zone
            </Button>
          </div>

          <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">{helperText}</div>
        </div>

        <DialogFooter>
          <Button onClick={onBack} type="button" variant="outline">
            {backLabel}
          </Button>
          <Button onClick={onContinue} type="button" disabled={points.length < 3 || isLoading || !frameSrc || isContinuing}>
            {continueLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}