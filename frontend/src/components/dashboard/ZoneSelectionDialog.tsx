import { ReactNode, useCallback, useEffect, useState } from "react";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ZonePoint } from "@/lib/api";

interface PreviewFrameResult {
  frameSrc: string;
  sourceLabel: string;
  sourceKind: string;
}

interface ZoneSelectionDialogProps {
  open: boolean;
  file: File | null;
  fileOptions?: Array<{
    key: string;
    label: string;
  }>;
  selectedFileKey?: string;
  sourceLabel?: string;
  sourceKind?: string;
  loadPreviewFrame?: (() => Promise<PreviewFrameResult>) | null;
  feedName: string;
  points: ZonePoint[];
  onPointsChange: (points: ZonePoint[]) => void;
  onSelectedFileChange?: (fileKey: string) => void;
  onBack: () => void;
  onContinue: () => void;
  onOpenChange: (open: boolean) => void;
  backLabel?: string;
  continueLabel?: string;
  helperText?: string;
  isContinuing?: boolean;
  metadataContent?: ReactNode;
}

function clamp(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function createAbortError(): Error {
  const error = new Error("Preview load aborted.");
  error.name = "AbortError";
  return error;
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function loadFirstFrame(file: File, signal?: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(createAbortError());
      return;
    }

    let objectUrl = "";
    let video: HTMLVideoElement;
    let settled = false;

    try {
      objectUrl = URL.createObjectURL(file);
      video = document.createElement("video");
    } catch (error) {
      reject(error instanceof Error ? error : new Error("Unable to prepare the selected video."));
      return;
    }

    const finalize = (callback: () => void) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      callback();
    };

    const cleanup = () => {
      video.onloadeddata = null;
      video.onerror = null;
      signal?.removeEventListener("abort", handleAbort);
      try {
        video.pause();
        video.removeAttribute("src");
        video.load();
      } catch {
        return;
      } finally {
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
      }
    };

    const handleAbort = () => {
      finalize(() => reject(createAbortError()));
    };

    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;

    video.onloadeddata = () => {
      try {
        if (signal?.aborted) {
          handleAbort();
          return;
        }

        if (video.videoWidth <= 0 || video.videoHeight <= 0) {
          finalize(() => reject(new Error("Unable to read the selected video frame.")));
          return;
        }

        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");
        if (!context) {
          finalize(() => reject(new Error("Unable to prepare the zone preview.")));
          return;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
        finalize(() => resolve(dataUrl));
      } catch (error) {
        finalize(() => reject(error instanceof Error ? error : new Error("Unable to decode the selected video.")));
      }
    };

    video.onerror = () => {
      finalize(() => reject(new Error("The selected video could not be opened in the browser.")));
    };

    signal?.addEventListener("abort", handleAbort, { once: true });

    video.src = objectUrl;
    video.load();
  });
}

export function ZoneSelectionDialog({
  open,
  file,
  fileOptions = [],
  selectedFileKey,
  sourceLabel,
  sourceKind,
  loadPreviewFrame,
  feedName,
  points,
  onPointsChange,
  onSelectedFileChange,
  onBack,
  onContinue,
  onOpenChange,
  backLabel = "Back",
  continueLabel = "Continue to Model",
  helperText = "Use the same workflow as the desktop GUI: capture a representative frame, draw the queue polygon, then continue to choose the model.",
  isContinuing = false,
  metadataContent,
}: ZoneSelectionDialogProps) {
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resolvedSourceLabel, setResolvedSourceLabel] = useState<string>(sourceLabel ?? file?.name ?? "No source selected");
  const [resolvedSourceKind, setResolvedSourceKind] = useState<string>(sourceKind ?? (file ? "Selected file" : "Camera source"));

  const loadPreview = useCallback(async (signal?: AbortSignal): Promise<PreviewFrameResult> => {
    if (file) {
      const frameSrc = await loadFirstFrame(file, signal);
      return {
        frameSrc,
        sourceLabel: sourceLabel ?? file.name,
        sourceKind: sourceKind ?? "Selected file",
      };
    }

    if (loadPreviewFrame) {
      return loadPreviewFrame();
    }

    throw new Error("No source is available for zone selection.");
  }, [file, loadPreviewFrame, sourceKind, sourceLabel]);

  const applyPreviewResult = useCallback((result: PreviewFrameResult) => {
    setFrameSrc(result.frameSrc);
    setResolvedSourceLabel(result.sourceLabel);
    setResolvedSourceKind(result.sourceKind);
  }, []);

  const reloadPreview = useCallback(async () => {
    if (!open) {
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setPreviewError(null);

    try {
      const result = await loadPreview(controller.signal);
      applyPreviewResult(result);
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }
      setFrameSrc(null);
      setPreviewError(error instanceof Error ? error.message : "Unable to load the preview frame.");
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, [applyPreviewResult, loadPreview, open]);

  useEffect(() => {
    if (!open || (!file && !loadPreviewFrame)) {
      setFrameSrc(null);
      setPreviewError(null);
      setIsLoading(false);
      setResolvedSourceLabel(sourceLabel ?? file?.name ?? "No source selected");
      setResolvedSourceKind(sourceKind ?? (file ? "Selected file" : "Camera source"));
      return undefined;
    }

    const controller = new AbortController();
    void (async () => {
      setIsLoading(true);
      setPreviewError(null);

      try {
        const result = await loadPreview(controller.signal);
        if (!controller.signal.aborted) {
          applyPreviewResult(result);
        }
      } catch (error) {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setPreviewError(error instanceof Error ? error.message : "Unable to load the preview frame.");
          setFrameSrc(null);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [applyPreviewResult, file, loadPreview, loadPreviewFrame, open, sourceKind, sourceLabel]);

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
          {fileOptions.length > 1 && onSelectedFileChange && selectedFileKey ? (
            <div className="grid gap-2 rounded-lg border border-border bg-background/40 p-3 sm:max-w-sm">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground/70">Selected videos</span>
              <Select onValueChange={onSelectedFileChange} value={selectedFileKey}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a local video" />
                </SelectTrigger>
                <SelectContent>
                  {fileOptions.map((option) => (
                    <SelectItem key={option.key} value={option.key}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Switch videos here to load a different frame while keeping each selected video's traced zone.</p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background/40 p-3 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{resolvedSourceKind}:</span>
            <span className="font-mono text-xs">{resolvedSourceLabel}</span>
            <span className="rounded-full bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
              {points.length} point{points.length === 1 ? "" : "s"}
            </span>
          </div>

          {metadataContent}

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