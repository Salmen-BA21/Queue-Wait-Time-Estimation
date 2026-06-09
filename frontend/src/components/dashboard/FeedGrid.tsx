import { memo, useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, Loader2, Play, RotateCcw, Square, Trash2, Wifi, WifiOff, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/status-badge";
import { useFeedWebRtc } from "@/hooks/use-feed-webrtc";
import { getFeedMjpegStreamUrl, resolveApiUrl, type VideoFeed } from "@/lib/api";

export type FeedGridAction = "start" | "stop" | "restart" | "delete";
type FeedTransportState =
  | "idle"
  | "worker-loading"
  | "webrtc-connecting"
  | "webrtc-live"
  | "mjpeg-live"
  | "preview";

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
  const [streamAttempt, setStreamAttempt] = useState(0);
  const [streamErrorCount, setStreamErrorCount] = useState(0);
  const [mjpegFrameLoaded, setMjpegFrameLoaded] = useState(false);
  const previousStatusRef = useRef(feed.status);
  const lastForcedReconnectAtRef = useRef(0);
  const WORKER_LOADING_TIMEOUT_MS = 60_000;
  const [workerLoadingTimedOut, setWorkerLoadingTimedOut] = useState(false);
  const workerLoadingTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setPlaybackFailed(false);
    setMjpegFrameLoaded(false);
    previousStatusRef.current = feed.status;
    lastForcedReconnectAtRef.current = 0;
    if (workerLoadingTimerRef.current !== null) {
      window.clearTimeout(workerLoadingTimerRef.current);
      workerLoadingTimerRef.current = null;
    }
    setWorkerLoadingTimedOut(false);
  }, [feed.feed_id, feed.preview_path, feed.status]);

  const transportActive = uiStatus !== "offline" && !isStopping;
  const hasWorkerMetrics = Boolean(feed.latest_metrics);
  const transportCapabilities = feed.transport ?? null;
  const webrtcCapability = transportCapabilities?.webrtc;
  const backendAnnotationsActive = Boolean(
    transportCapabilities?.backend_annotations ?? feed.latest_metrics?.backend_annotations_active,
  );
  const canUseWebRtc = Boolean(
    webrtcCapability?.enabled
    && webrtcCapability?.ready
    && webrtcCapability?.source_mode !== "none",
  );
  const shouldShowWorkerLoading = transportActive
    && (feed.status === "initializing" || (feed.status === "running" && !hasWorkerMetrics));

  useEffect(() => {
    if (shouldShowWorkerLoading) {
      if (workerLoadingTimerRef.current === null) {
        workerLoadingTimerRef.current = window.setTimeout(() => {
          setWorkerLoadingTimedOut(true);
        }, WORKER_LOADING_TIMEOUT_MS);
      }
    } else {
      if (workerLoadingTimerRef.current !== null) {
        window.clearTimeout(workerLoadingTimerRef.current);
        workerLoadingTimerRef.current = null;
      }
      setWorkerLoadingTimedOut(false);
    }
    return () => {
      if (workerLoadingTimerRef.current !== null) {
        window.clearTimeout(workerLoadingTimerRef.current);
        workerLoadingTimerRef.current = null;
      }
    };
  }, [shouldShowWorkerLoading]);

  const shouldAttemptWebRtc = transportActive
    && feed.status === "running"
    && canUseWebRtc
    && (hasWorkerMetrics || workerLoadingTimedOut);
  const {
    videoRef: webRtcVideoRef,
    streamReady: webRtcReady,
    connectionError: webRtcConnectionError,
    isSupported: webRtcSupported,
  } = useFeedWebRtc({
    feedId: feed.feed_id,
    enabled: shouldAttemptWebRtc,
  });
  const showWebRtcFrame = shouldAttemptWebRtc && webRtcSupported && webRtcReady;
  const shouldUseMjpegFallback = !shouldAttemptWebRtc
    || !webRtcSupported
    || Boolean(webRtcConnectionError);
  const shouldUseMjpegStream = transportActive
    && feed.status === "running"
    && shouldUseMjpegFallback
    && (hasWorkerMetrics || workerLoadingTimedOut);
  const streamUrl = shouldUseMjpegStream
    ? `${getFeedMjpegStreamUrl(feed.feed_id)}?attempt=${streamAttempt}`
    : null;

  useEffect(() => {
    const previousStatus = previousStatusRef.current;
    const enteredRunning = previousStatus !== "running" && feed.status === "running";

    if (shouldUseMjpegStream && enteredRunning) {
      const now = Date.now();
      const reconnectCooldownMs = 1_500;
      if (now - lastForcedReconnectAtRef.current >= reconnectCooldownMs) {
        lastForcedReconnectAtRef.current = now;
        setPlaybackFailed(false);
        setStreamErrorCount(0);
        setStreamAttempt((attempt) => attempt + 1);
      }
    }

    previousStatusRef.current = feed.status;
  }, [feed.status, shouldUseMjpegStream]);

  useEffect(() => {
    if (!shouldUseMjpegStream) {
      setStreamAttempt(0);
      setStreamErrorCount(0);
      setMjpegFrameLoaded(false);
      lastForcedReconnectAtRef.current = 0;
      return;
    }

    if (streamErrorCount === 0) {
      return;
    }

    const retryDelayMs = Math.min(15_000, 1_000 * 2 ** Math.max(streamErrorCount - 1, 0));
    const retryId = window.setTimeout(() => {
      setPlaybackFailed(false);
      setStreamAttempt((attempt) => attempt + 1);
    }, retryDelayMs);

    return () => {
      window.clearTimeout(retryId);
    };
  }, [shouldUseMjpegStream, streamErrorCount]);

  useEffect(() => {
    setMjpegFrameLoaded(false);
  }, [streamUrl]);

  useEffect(() => {
    if (!streamUrl || playbackFailed || mjpegFrameLoaded) {
      return;
    }

    const stallId = window.setTimeout(() => {
      setPlaybackFailed(true);
      setStreamErrorCount((count) => count + 1);
    }, 12_000);

    return () => {
      window.clearTimeout(stallId);
    };
  }, [streamUrl, playbackFailed, mjpegFrameLoaded, streamAttempt]);

  const previewUrl = feed.preview_path ? resolveApiUrl(feed.preview_path) : null;
  const shouldRenderMjpegStream = Boolean(streamUrl) && !playbackFailed;
  const showMjpegFrame = shouldRenderMjpegStream && mjpegFrameLoaded;
  const showWebRtcLoadingState = shouldAttemptWebRtc
    && !showWebRtcFrame
    && !showMjpegFrame;
  const showMjpegLoadingState = shouldRenderMjpegStream && !showMjpegFrame;
  const showLoadingState = (shouldShowWorkerLoading || showWebRtcLoadingState || showMjpegLoadingState)
    && !showWebRtcFrame
    && !showMjpegFrame;
  const showPreview = transportActive
    && !shouldShowWorkerLoading
    && !showWebRtcFrame
    && !showMjpegFrame
    && !shouldRenderMjpegStream
    && Boolean(previewUrl)
    && !playbackFailed;
  const transportState: FeedTransportState = (() => {
    if (showWebRtcFrame) {
      return "webrtc-live";
    }
    if (showMjpegFrame) {
      return "mjpeg-live";
    }
    if (showPreview) {
      return "preview";
    }
    if (showWebRtcLoadingState) {
      return "webrtc-connecting";
    }
    if (showLoadingState) {
      return "worker-loading";
    }
    return "idle";
  })();
  const shouldSuppressClientDetectionsOnWebRtc = Boolean(
    transportState === "webrtc-live"
    && backendAnnotationsActive
    && webrtcCapability?.source_mode === "annotated",
  );
  const transportDebugLabel = (() => {
    switch (transportState) {
      case "webrtc-live":
        return webrtcCapability?.source_mode === "annotated" ? "WEBRTC ANN" : "WEBRTC DIR";
      case "mjpeg-live":
        return shouldAttemptWebRtc ? "MJPEG FB" : "MJPEG";
      case "preview":
        return "PREVIEW";
      case "webrtc-connecting":
        return "WEBRTC...";
      case "worker-loading":
        return "LOADING";
      default:
        return "IDLE";
    }
  })();
  const transportDebugBadgeClassName = transportState === "webrtc-live"
    ? "border-emerald-300/50 bg-emerald-500/20 text-emerald-100"
    : transportState === "mjpeg-live"
    ? "border-amber-300/50 bg-amber-500/20 text-amber-100"
    : "border-border/70 bg-background/80 text-foreground/80";
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
      {transportState === "webrtc-live" ? (
        <>
          <video
            ref={webRtcVideoRef}
            className="h-full w-full object-cover"
            autoPlay
            muted
            playsInline
            onLoadedMetadata={onVideoLoad}
          />
          {/* Zone polygon overlay only – detection boxes disabled */}
          {videoDims && zonePolygonPoints && (
            <svg
              className="absolute inset-0 h-full w-full pointer-events-none"
              viewBox={`0 0 ${videoDims.width} ${videoDims.height}`}
              preserveAspectRatio="xMidYMid slice"
            >
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
            </svg>
          )}
        </>
      ) : shouldRenderMjpegStream ? (
        <>
          <img
            key={streamUrl}
            className="h-full w-full object-cover"
            src={streamUrl ?? undefined}
            alt={`${feed.name} live frame`}
            onLoad={(event) => {
              setPlaybackFailed(false);
              setStreamErrorCount(0);
              setMjpegFrameLoaded(true);
              onImageLoad(event);
            }}
            onError={() => {
              setPlaybackFailed(true);
              setMjpegFrameLoaded(false);
              setStreamErrorCount((count) => count + 1);
            }}
          />
          {!mjpegFrameLoaded && (
            <div className="absolute inset-0 flex h-full w-full flex-col items-center justify-center gap-2 bg-background/70 px-4 text-center">
              <Loader2 className="h-7 w-7 animate-spin text-primary/60" />
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground/80">
                Preparing live stream
              </p>
              <p className="text-[11px] text-muted-foreground">
                Waiting for the first analyzed frame from the backend worker.
              </p>
            </div>
          )}
          {/* Zone polygon overlay only – detection boxes are already drawn by the backend pipeline */}
          {videoDims && zonePolygonPoints && (
            <svg
              className="absolute inset-0 h-full w-full pointer-events-none"
              viewBox={`0 0 ${videoDims.width} ${videoDims.height}`}
              preserveAspectRatio="xMidYMid slice"
            >
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
            </svg>
          )}
        </>
      ) : transportState === "preview" ? (
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
          {/* Zone polygon overlay only – detection boxes disabled */}
          {videoDims && zonePolygonPoints && (
            <svg
              className="absolute inset-0 h-full w-full pointer-events-none"
              viewBox={`0 0 ${videoDims.width} ${videoDims.height}`}
              preserveAspectRatio="xMidYMid slice"
            >
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
            </svg>
          )}
        </>
      ) : transportState === "worker-loading" || transportState === "webrtc-connecting" ? (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-background/90 px-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary/60" />
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground/80">
            {feed.status === "initializing"
              ? "Initializing worker"
              : transportState === "webrtc-connecting"
              ? "Connecting WebRTC"
              : "Preparing live stream"}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {feed.status === "initializing"
              ? "Starting model and tracker before the first analyzed frame is emitted."
              : transportState === "webrtc-connecting"
              ? "Loading the latest backend frame while the live WebRTC stream is negotiated."
              : "Waiting for the first analyzed frame from the backend worker."}
          </p>
        </div>
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
      <div
        data-testid="transport-badge"
        className={`absolute left-2 top-10 rounded border px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.14em] ${transportDebugBadgeClassName}`}
      >
        {transportDebugLabel}
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