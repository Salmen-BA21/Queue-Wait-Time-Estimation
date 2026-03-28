import { memo, useEffect, useState } from "react";
import { AlertTriangle, Camera, Loader2, Play, RotateCcw, Square, Trash2, Wifi, WifiOff, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/status-badge";
import { getFeedSnapshot, resolveApiUrl, type VideoFeed } from "@/lib/api";

export type FeedGridAction = "start" | "stop" | "restart" | "delete";

function mapFeedStatus(status: "created" | "initializing" | "running" | "stopped" | "error") {
  if (status === "running") {
    return "online" as const;
  }
  if (status === "stopped") {
    return "offline" as const;
  }
  return "warning" as const;
}

function formatWaitTime(waitTimeSeconds: number): string {
  if (waitTimeSeconds < 60) {
    return `${waitTimeSeconds.toFixed(1)}s`;
  }
  return `${(waitTimeSeconds / 60).toFixed(1)}m`;
}

function formatRatePerMinute(rate: number): string {
  const perMinute = rate * 60;
  return `${perMinute >= 10 ? perMinute.toFixed(1) : perMinute.toFixed(2)}/min`;
}

function FeedThresholdEditor({
  feed,
  isSaving,
  onSave,
}: {
  feed: VideoFeed;
  isSaving: boolean;
  onSave: (feedId: string, queueLengthWarning: number) => Promise<void>;
}) {
  const [warningValue, setWarningValue] = useState(String(feed.queue_length_warning));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setWarningValue(String(feed.queue_length_warning));
    setError(null);
  }, [feed.feed_id, feed.queue_length_warning]);

  const handleSave = async () => {
    const warning = Number.parseInt(warningValue, 10);

    if (!Number.isFinite(warning)) {
      setError("Enter a whole number for the threshold.");
      return;
    }

    if (warning < 0) {
      setError("Threshold must be zero or greater.");
      return;
    }

    setError(null);
    await onSave(feed.feed_id, warning);
  };

  return (
    <div className="mt-3 rounded-lg border border-border bg-background/50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground/70">Queue thresholds</p>
          <p className="text-xs text-muted-foreground">Update the per-feed people-in-line limits used by the detector.</p>
        </div>
        <Button onClick={handleSave} size="sm" type="button" variant="secondary" disabled={isSaving}>
          {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Save
        </Button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>Warning</span>
          <Input
            min={0}
            inputMode="numeric"
            type="number"
            value={warningValue}
            onChange={(event) => setWarningValue(event.target.value)}
          />
        </label>
      </div>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}

function shouldUseSnapshotTransport(feed: VideoFeed): boolean {
  const source = feed.source.trim().toLowerCase();
  return source.startsWith("rtsp://") || /^\d+$/.test(source);
}

function FeedTransportSurface({
  feed,
  uiStatus,
  peopleInZone,
  waitTimeSeconds,
  detections,
  isStopping,
  onOpenViewer,
}: {
  feed: VideoFeed;
  uiStatus: "online" | "offline" | "warning";
  peopleInZone: number;
  waitTimeSeconds: number | undefined | null;
  detections?: number[][] | null;
  isStopping: boolean;
  onOpenViewer?: () => void;
}) {
  const [playbackFailed, setPlaybackFailed] = useState(false);
  const [videoDims, setVideoDims] = useState<{ width: number; height: number } | null>(null);
  const [liveFrameUrl, setLiveFrameUrl] = useState<string | null>(null);
  const usesSnapshotTransport = shouldUseSnapshotTransport(feed);

  useEffect(() => {
    setPlaybackFailed(false);
  }, [feed.preview_path]);

  const transportActive = uiStatus !== "offline" && !isStopping;

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    if (!usesSnapshotTransport || !transportActive || (feed.status !== "running" && feed.status !== "initializing")) {
      setLiveFrameUrl(null);
      return;
    }

    const refreshSnapshot = async () => {
      if (inFlight || cancelled) {
        return;
      }

      inFlight = true;
      try {
        const snapshot = await getFeedSnapshot(feed.feed_id);
        if (!cancelled && snapshot.captured && snapshot.image_data_url) {
          setLiveFrameUrl(snapshot.image_data_url);
        }
      } catch {
        // Keep the last known frame or fallback preview without interrupting the feed card.
      } finally {
        inFlight = false;
      }
    };

    void refreshSnapshot();
    const intervalId = window.setInterval(() => {
      void refreshSnapshot();
    }, 800);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [feed.feed_id, feed.status, transportActive, usesSnapshotTransport]);

  const previewUrl = feed.preview_path ? resolveApiUrl(feed.preview_path) : null;
  const showLiveFrame = usesSnapshotTransport && transportActive && Boolean(liveFrameUrl) && !playbackFailed;
  const showPreview = transportActive && !showLiveFrame && Boolean(previewUrl) && !playbackFailed;
  const zonePoints = feed.zone?.points ?? [];
  const zonePolygonPoints = videoDims
    ? zonePoints
        .map((point) => `${point.x * videoDims.width},${point.y * videoDims.height}`)
        .join(" ")
    : "";

  const onVideoLoad = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    setVideoDims({ width: video.videoWidth, height: video.videoHeight });
  };

  const onImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const image = e.currentTarget;
    setVideoDims({ width: image.naturalWidth, height: image.naturalHeight });
  };

  return (
    <button
      type="button"
      onClick={onOpenViewer}
      className="relative flex aspect-video w-full items-center justify-center overflow-hidden bg-background/80 text-left"
      disabled={!onOpenViewer}
      aria-label={onOpenViewer ? `Open ${feed.name} in expanded view` : undefined}
    >
      {showLiveFrame ? (
        <>
          <img
            key={liveFrameUrl}
            className="h-full w-full object-cover"
            src={liveFrameUrl ?? undefined}
            alt={`${feed.name} live frame`}
            onLoad={onImageLoad}
            onError={() => setPlaybackFailed(true)}
          />
          {/* Tracking overlays (zone polygon + person boxes) */}
          {videoDims && (zonePolygonPoints || (uiStatus === "online" && detections?.length)) && (
            <svg
              className="absolute inset-0 h-full w-full pointer-events-none"
              viewBox={`0 0 ${videoDims.width} ${videoDims.height}`}
              preserveAspectRatio="xMidYMid slice"
            >
              {zonePolygonPoints && (
                <>
                  <polygon
                    points={zonePolygonPoints}
                    className="fill-cyan-400/10 stroke-cyan-300"
                    strokeWidth={3}
                    vectorEffect="non-scaling-stroke"
                  />
                  <polyline
                    points={zonePolygonPoints}
                    className="stroke-cyan-100/70"
                    strokeWidth={1}
                    fill="none"
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}

              {uiStatus === "online" && detections?.map((det, idx) => {
                const [x1, y1, x2, y2] = det;
                return (
                  <rect
                    key={idx}
                    x={x1}
                    y={y1}
                    width={x2 - x1}
                    height={y2 - y1}
                    className="fill-primary/10 stroke-primary stroke-[2]"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>
          )}
        </>
      ) : showPreview ? (
        <>
          <video
            key={previewUrl}
            className="h-full w-full object-cover"
            src={previewUrl}
            autoPlay
            loop
            muted
            playsInline
            preload="metadata"
            onLoadedMetadata={onVideoLoad}
            onError={() => setPlaybackFailed(true)}
          />
          {/* Tracking overlays (zone polygon + person boxes) */}
          {videoDims && (zonePolygonPoints || (uiStatus === "online" && detections?.length)) && (
            <svg
              className="absolute inset-0 h-full w-full pointer-events-none"
              viewBox={`0 0 ${videoDims.width} ${videoDims.height}`}
              preserveAspectRatio="xMidYMid slice"
            >
              {zonePolygonPoints && (
                <>
                  <polygon
                    points={zonePolygonPoints}
                    className="fill-cyan-400/10 stroke-cyan-300"
                    strokeWidth={3}
                    vectorEffect="non-scaling-stroke"
                  />
                  <polyline
                    points={zonePolygonPoints}
                    className="stroke-cyan-100/70"
                    strokeWidth={1}
                    fill="none"
                    vectorEffect="non-scaling-stroke"
                  />
                </>
              )}

              {uiStatus === "online" && detections?.map((det, idx) => {
                const [x1, y1, x2, y2] = det;
                return (
                  <rect
                    key={idx}
                    x={x1}
                    y={y1}
                    width={x2 - x1}
                    height={y2 - y1}
                    className="fill-primary/10 stroke-primary stroke-[2]"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>
          )}
        </>
      ) : (
        <div className="space-y-2 px-4 text-center">
          {uiStatus === "offline" ? (
            <WifiOff className="mx-auto h-8 w-8 text-muted-foreground/30" />
          ) : (
            <Wifi className="mx-auto h-8 w-8 animate-glow-pulse text-primary/30" />
          )}
          <p className="font-mono text-xs text-muted-foreground/50">SOURCE: {feed.source}</p>
          <p className="text-[11px] text-muted-foreground">
            {feed.preview_path
              ? "The uploaded video preview could not be loaded from the backend."
              : "Live transport will appear here once the worker pipeline is connected."}
          </p>
        </div>
      )}
      <div className="absolute left-2 top-2">
        <StatusBadge status={uiStatus} label={feed.status} />
      </div>
      <div className="absolute right-2 top-2 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground">
        Model {feed.model_size.toUpperCase()}
      </div>
      {uiStatus !== "offline" && (
        <div className="absolute right-2 top-10 flex items-center gap-1 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground">
          <Users className="h-3 w-3 text-primary" />
          {peopleInZone}
        </div>
      )}
      {waitTimeSeconds !== null && waitTimeSeconds !== undefined && (
        <div className="absolute bottom-2 right-2 rounded bg-background/80 px-2 py-0.5 text-xs font-mono text-foreground">
          {formatWaitTime(waitTimeSeconds)}
        </div>
      )}
    </button>
  );
}

/**
 * Renders the live surveillance wall feed cards and feed-level actions.
 */
function FeedGridComponent({
  feeds,
  emptyState,
  activeFeedAction,
  onEditZone,
  onFeedAction,
  onSaveThresholds,
  isSavingThresholds,
}: {
  feeds: VideoFeed[];
  emptyState: boolean;
  activeFeedAction: { feedId: string; action: FeedGridAction } | null;
  onEditZone: (feed: VideoFeed) => void;
  onFeedAction: (feed: VideoFeed, action: FeedGridAction) => void;
  onSaveThresholds: (feedId: string, queueLengthWarning: number) => Promise<void>;
  isSavingThresholds: boolean;
}) {
  const [expandedFeedId, setExpandedFeedId] = useState<string | null>(null);
  const expandedFeed = feeds.find((feed) => feed.feed_id === expandedFeedId) ?? null;

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-foreground">Surveillance Wall</h2>
      {emptyState && (
        <div className="rounded-lg border border-dashed border-border bg-card/60 p-8 text-center">
          <Camera className="mx-auto h-10 w-10 text-primary/50" />
          <p className="mt-3 text-sm font-medium text-foreground">No feeds configured yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload an MP4 or discover an ONVIF source to start the queue workflow.
          </p>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {feeds.map((feed) => {
          const uiStatus = mapFeedStatus(feed.status);
          const peopleInZone = feed.latest_metrics?.people_in_zone ?? 0;
          const wait_time_seconds = feed.latest_metrics?.wait_time_seconds;
          const detections = feed.latest_metrics?.detections;
          const currentAction = activeFeedAction?.feedId === feed.feed_id ? activeFeedAction.action : null;
          const isFeedActionPending = activeFeedAction?.feedId === feed.feed_id;
          const canStart = feed.status === "created" || feed.status === "stopped" || feed.status === "error";
          const canStop = feed.status === "running";
          const canRestart = feed.status !== "created" && feed.status !== "initializing";
          const canDelete = feed.status !== "initializing";

          return (
            <div
              key={feed.feed_id}
              className="group overflow-hidden rounded-lg border border-border bg-card transition-all hover:glow-border"
            >
              <FeedTransportSurface
                feed={feed}
                uiStatus={uiStatus}
                peopleInZone={peopleInZone}
                waitTimeSeconds={wait_time_seconds}
                detections={detections}
                isStopping={currentAction === "stop"}
                onOpenViewer={() => setExpandedFeedId(feed.feed_id)}
              />
              <div className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{feed.name}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">{feed.source}</p>
                  </div>
                  <div className="text-right text-xs text-muted-foreground">
                    <p>{feed.zone?.points.length ?? 0} zone points</p>
                    <p>{feed.status === "error" ? "Worker failed" : feed.last_warning ? "Warning active" : "Runtime nominal"}</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {feed.last_error && <Badge variant="destructive">Runtime failure</Badge>}
                  {feed.last_warning && <Badge variant="secondary">Worker warning</Badge>}
                  {feed.latest_metrics && (
                    <>
                      <Badge variant="outline">Live metrics active</Badge>
                    </>
                  )}
                  <Button onClick={() => onEditZone(feed)} size="sm" type="button" variant="outline">
                    Edit Zone
                  </Button>
                  <Button
                    onClick={() => onFeedAction(feed, canStop ? "stop" : "start")}
                    size="sm"
                    type="button"
                    variant={canStop ? "outline" : "default"}
                    disabled={isFeedActionPending || feed.status === "initializing" || (!canStop && !canStart)}
                  >
                    {currentAction === (canStop ? "stop" : "start") ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : canStop ? (
                      <Square className="mr-2 h-4 w-4" />
                    ) : (
                      <Play className="mr-2 h-4 w-4" />
                    )}
                    {canStop ? "Stop" : "Start"}
                  </Button>
                  <Button
                    onClick={() => onFeedAction(feed, "restart")}
                    size="sm"
                    type="button"
                    variant="outline"
                    disabled={isFeedActionPending || !canRestart}
                  >
                    {currentAction === "restart" ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCcw className="mr-2 h-4 w-4" />
                    )}
                    Restart
                  </Button>
                  <Button
                    onClick={() => onFeedAction(feed, "delete")}
                    size="sm"
                    type="button"
                    variant="outline"
                    disabled={isFeedActionPending || !canDelete}
                  >
                    {currentAction === "delete" ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 h-4 w-4" />
                    )}
                    Remove
                  </Button>
                  {feed.status === "initializing" && (
                    <span className="text-xs text-muted-foreground">Worker is initializing...</span>
                  )}
                </div>
                <FeedThresholdEditor feed={feed} isSaving={isSavingThresholds} onSave={onSaveThresholds} />
                {(feed.last_error || feed.last_warning) && (
                  <div className="mt-3 space-y-2">
                    {feed.last_error && (
                      <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                          <div>
                            <p className="text-xs font-semibold text-destructive">Runtime failure</p>
                            <p className="mt-1 text-xs leading-relaxed text-destructive/90">{feed.last_error}</p>
                          </div>
                        </div>
                      </div>
                    )}
                    {feed.last_warning && (
                      <div className="rounded-lg border border-border bg-background/50 p-3">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="mt-0.5 h-4 w-4 text-primary" />
                          <div>
                            <p className="text-xs font-semibold text-foreground">Worker warning</p>
                            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{feed.last_warning}</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-3 rounded-lg border border-border bg-background/40 p-3">
                  {feed.latest_metrics ? (
                    <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground xl:grid-cols-4">
                      <div>
                        <p className="uppercase tracking-[0.2em] text-muted-foreground/70">Queue</p>
                        <p className="mt-1 text-sm font-medium text-foreground">{feed.latest_metrics.people_in_zone} people</p>
                      </div>
                      <div>
                        <p className="uppercase tracking-[0.2em] text-muted-foreground/70">Arrival</p>
                        <p className="mt-1 text-sm font-medium text-foreground">{formatRatePerMinute(feed.latest_metrics.arrival_rate)}</p>
                      </div>
                      <div>
                        <p className="uppercase tracking-[0.2em] text-muted-foreground/70">Service</p>
                        <p className="mt-1 text-sm font-medium text-foreground">{formatRatePerMinute(feed.latest_metrics.service_rate)}</p>
                      </div>
                      <div>
                        <p className="uppercase tracking-[0.2em] text-muted-foreground/70">Wait</p>
                        <p className="mt-1 text-sm font-medium text-foreground">
                          {feed.latest_metrics.wait_time_seconds === null ? "Pending" : formatWaitTime(feed.latest_metrics.wait_time_seconds)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      {feed.status === "running"
                        ? "Worker is running. Waiting for the first live metrics update."
                        : "No live metrics yet for this feed."}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <Dialog open={expandedFeed !== null} onOpenChange={(open) => !open && setExpandedFeedId(null)}>
        {expandedFeed && (
          <DialogContent className="w-[95vw] max-w-6xl p-0">
            <DialogTitle className="sr-only">{expandedFeed.name} expanded view</DialogTitle>
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-foreground">{expandedFeed.name}</p>
              <p className="truncate font-mono text-xs text-muted-foreground">{expandedFeed.source}</p>
            </div>
            <FeedTransportSurface
              feed={expandedFeed}
              uiStatus={mapFeedStatus(expandedFeed.status)}
              peopleInZone={expandedFeed.latest_metrics?.people_in_zone ?? 0}
              waitTimeSeconds={expandedFeed.latest_metrics?.wait_time_seconds}
              detections={expandedFeed.latest_metrics?.detections}
              isStopping={
                activeFeedAction?.feedId === expandedFeed.feed_id && activeFeedAction.action === "stop"
              }
            />
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}

export const FeedGrid = memo(FeedGridComponent);