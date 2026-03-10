import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Play,
  Radio,
  RotateCcw,
  Search,
  Square,
  Trash2,
  Upload,
  Video,
  Wifi,
  WifiOff,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { ModelSelectionDialog } from "@/components/dashboard/ModelSelectionDialog";
import { ReviewLaunchDialog, type ReviewLaunchItem } from "@/components/dashboard/ReviewLaunchDialog";
import { ZoneSelectionDialog } from "@/components/dashboard/ZoneSelectionDialog";
import { AppLayout } from "@/components/layout/AppLayout";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/ui/status-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLiveDashboard } from "@/hooks/use-live-dashboard";
import type {
  BatchFeedDraft,
  Caisse,
  Establishment,
  LogLevel,
  ModelSize,
  ONVIFCameraTestResult,
  ONVIFDevice,
  ONVIFStream,
  RTSPConnectionTestResult,
  RTSPSnapshotResult,
  RTSPTransport,
  VideoFeed,
  ZonePoint,
} from "@/lib/api";
import {
  captureRtspSnapshot,
  createCaisse,
  createEstablishment,
  discoverOnvifDevices,
  getFeedSnapshot,
  launchFeedBatch,
  listCaisses,
  listEstablishments,
  resolveApiUrl,
  resolveOnvifStreams,
  testOnvifCamera,
  testRtspConnection,
  uploadVideo,
} from "@/lib/api";

type SetupStep = "source" | "zone" | "model" | "review" | null;
type SourceMode = "rtsp" | "file" | "onvif";
type FeedAction = "start" | "stop" | "restart" | "delete";

interface StagedFeedDraft {
  clientId: string;
  feedName: string;
  sourceMode: SourceMode;
  source: string;
  uploadedFile: File | null;
  zonePoints: ZonePoint[];
  modelSize: ModelSize;
  establishmentId: number | null;
  establishmentName: string | null;
  caisseId: number | null;
  caisseName: string | null;
  hasSavedCaisseZone: boolean;
  rtspUsername: string;
  rtspPassword: string;
  rtspTransport: RTSPTransport;
  rtspTestResult: RTSPConnectionTestResult | null;
  onvifTimeout: string;
  onvifUsername: string;
  onvifPassword: string;
  onvifTransport: RTSPTransport;
  onvifDevices: ONVIFDevice[];
  selectedOnvifDeviceKey: string;
  onvifStreams: ONVIFStream[];
  onvifTestResult: ONVIFCameraTestResult | null;
}

const DEFAULT_ONVIF_TIMEOUT = "5";
const UNASSIGNED_SELECT_VALUE = "__unassigned__";

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

function getUncertaintyTone(level: string): "default" | "secondary" | "destructive" {
  if (level === "High") {
    return "destructive";
  }
  if (level === "Medium") {
    return "secondary";
  }
  return "default";
}

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

function isRecoveryWarning(feed: VideoFeed): boolean {
  return feed.last_warning_code === "recovery_required";
}

function getFileLabel(file: File | null): string {
  if (!file) {
    return "No video selected yet";
  }
  const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
  return `${file.name} (${sizeMb} MB)`;
}

function getSuggestedFeedNameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, "") || file.name;
}

function getLocalFileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function dedupeLocalFiles(files: File[], excludedKeys: string[] = []): File[] {
  const seen = new Set(excludedKeys);
  const deduped: File[] = [];

  for (const file of files) {
    const key = getLocalFileKey(file);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(file);
  }

  return deduped;
}

function areZonePointsEqual(left: ZonePoint[], right: ZonePoint[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((point, index) => point.x === right[index]?.x && point.y === right[index]?.y);
}

const LOCAL_FILE_DRAFT_PREFIX = "local-file-draft:";

function createLocalFileDraftId(file: File): string {
  return `${LOCAL_FILE_DRAFT_PREFIX}${getLocalFileKey(file)}`;
}

function isLocalFileDraftId(clientId: string): boolean {
  return clientId.startsWith(LOCAL_FILE_DRAFT_PREFIX);
}

function formatResolution(result: {
  resolution: string | null;
  width: number | null;
  height: number | null;
}): string {
  if (result.resolution) {
    return result.resolution;
  }

  if (typeof result.width === "number" && typeof result.height === "number") {
    return `${result.width}x${result.height}`;
  }

  return "Unknown";
}

function getOnvifDeviceKey(device: ONVIFDevice): string {
  return `${device.ip}|${device.xaddrs ?? ""}`;
}

function suggestFeedNameFromRtspUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (!parsed.hostname) {
      return null;
    }
    return `Camera ${parsed.hostname}`;
  } catch {
    return null;
  }
}

function createDraftId(): string {
  return `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getDraftSelectedOnvifDevice(draft: StagedFeedDraft): ONVIFDevice | null {
  return draft.onvifDevices.find((device) => getOnvifDeviceKey(device) === draft.selectedOnvifDeviceKey) ?? null;
}

function getDraftSourceLabel(draft: StagedFeedDraft): string {
  if (draft.sourceMode === "file") {
    return draft.uploadedFile ? draft.uploadedFile.name : "No video selected";
  }

  if (draft.sourceMode === "onvif") {
    const device = getDraftSelectedOnvifDevice(draft);
    return device ? `${device.name} (${device.ip})` : draft.source || "No ONVIF camera selected";
  }

  return draft.source.trim() || "No RTSP URL provided";
}

function getDraftSourceDetail(draft: StagedFeedDraft): string {
  if (draft.sourceMode === "file") {
    return draft.uploadedFile
      ? `The file will be uploaded to the backend and the ${draft.zonePoints.length}-point queue zone will be saved before launch.`
      : "Choose a local video file before reviewing the configuration.";
  }

  if (draft.sourceMode === "rtsp") {
    if (draft.rtspTestResult?.connected) {
      return `${formatResolution(draft.rtspTestResult)} at ${(draft.rtspTestResult.fps ?? 0).toFixed(1)} FPS via ${draft.rtspTransport.toUpperCase()}.`;
    }
    return `Manual RTSP source using ${draft.rtspTransport.toUpperCase()} transport.`;
  }

  if (draft.onvifTestResult?.connected) {
    return `${draft.source || "Resolved stream"} · ${formatResolution(draft.onvifTestResult)} at ${(draft.onvifTestResult.fps ?? 0).toFixed(1)} FPS via ${draft.onvifTransport.toUpperCase()}.`;
  }

  return draft.source.trim() || "Resolve a stream from the selected ONVIF camera before launching.";
}

function toReviewLaunchItem(draft: StagedFeedDraft, isCurrentDraft = false): ReviewLaunchItem {
  return {
    clientId: draft.clientId,
    feedName: draft.feedName,
    sourceMode: draft.sourceMode,
    sourceLabel: getDraftSourceLabel(draft),
    sourceDetail: getDraftSourceDetail(draft),
    modelSize: draft.modelSize,
    zonePointCount: draft.zonePoints.length,
    establishmentName: draft.establishmentName,
    caisseName: draft.caisseName,
    hasSavedCaisseZone: draft.hasSavedCaisseZone,
    isCurrentDraft,
  };
}

function FeedTransportSurface({
  feed,
  uiStatus,
  peopleInZone,
  waitTimeSeconds,
}: {
  feed: VideoFeed;
  uiStatus: "online" | "offline" | "warning";
  peopleInZone: number;
  waitTimeSeconds: number | undefined;
}) {
  const [playbackFailed, setPlaybackFailed] = useState(false);

  useEffect(() => {
    setPlaybackFailed(false);
  }, [feed.preview_path]);

  const previewUrl = feed.preview_path ? resolveApiUrl(feed.preview_path) : null;
  const showPreview = Boolean(previewUrl) && !playbackFailed;

  return (
    <div className="relative flex aspect-video items-center justify-center bg-background/80">
      {showPreview ? (
        <video
          key={previewUrl}
          className="h-full w-full object-cover"
          src={previewUrl}
          autoPlay
          loop
          muted
          playsInline
          preload="metadata"
          onError={() => setPlaybackFailed(true)}
        />
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
    </div>
  );
}

export default function Dashboard() {
  const [setupStep, setSetupStep] = useState<SetupStep>(null);
  const [targetSourceCount, setTargetSourceCount] = useState("1");
  const [stagedFeeds, setStagedFeeds] = useState<StagedFeedDraft[]>([]);
  const [currentDraftId, setCurrentDraftId] = useState(() => createDraftId());
  const [feedName, setFeedName] = useState("");
  const [feedSource, setFeedSource] = useState("");
  const [sourceMode, setSourceMode] = useState<SourceMode>("file");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [queuedLocalFiles, setQueuedLocalFiles] = useState<File[]>([]);
  const [localFileFeedNames, setLocalFileFeedNames] = useState<Record<string, string>>({});
  const [localFileModelSelections, setLocalFileModelSelections] = useState<Record<string, ModelSize>>({});
  const [localFileEstablishmentSelections, setLocalFileEstablishmentSelections] = useState<Record<string, number | null>>({});
  const [localFileCaisseSelections, setLocalFileCaisseSelections] = useState<Record<string, number | null>>({});
  const [localFileZonePoints, setLocalFileZonePoints] = useState<Record<string, ZonePoint[]>>({});
  const [zonePoints, setZonePoints] = useState<ZonePoint[]>([]);
  const [editingFeedZone, setEditingFeedZone] = useState<VideoFeed | null>(null);
  const [editingZonePoints, setEditingZonePoints] = useState<ZonePoint[]>([]);
  const [isSavingEditedZone, setIsSavingEditedZone] = useState(false);
  const [feedPendingDeletion, setFeedPendingDeletion] = useState<VideoFeed | null>(null);
  const [selectedModel, setSelectedModel] = useState<ModelSize>("n");
  const [isFinalizingSetup, setIsFinalizingSetup] = useState(false);
  const [activeFeedAction, setActiveFeedAction] = useState<{ feedId: string; action: FeedAction } | null>(null);
  const [selectedEstablishmentId, setSelectedEstablishmentId] = useState<number | null>(null);
  const [selectedCaisseId, setSelectedCaisseId] = useState<number | null>(null);
  const [isCreateEstablishmentDialogOpen, setIsCreateEstablishmentDialogOpen] = useState(false);
  const [isCreateCaisseDialogOpen, setIsCreateCaisseDialogOpen] = useState(false);
  const [newEstablishmentName, setNewEstablishmentName] = useState("");
  const [newCaisseName, setNewCaisseName] = useState("");
  const [batchLogLevel, setBatchLogLevel] = useState<LogLevel>("INFO");
  const [batchWebhookEnabled, setBatchWebhookEnabled] = useState(true);
  const [rtspUsername, setRtspUsername] = useState("");
  const [rtspPassword, setRtspPassword] = useState("");
  const [rtspTransport, setRtspTransport] = useState<RTSPTransport>("tcp");
  const [rtspTestResult, setRtspTestResult] = useState<RTSPConnectionTestResult | null>(null);
  const [isTestingRtsp, setIsTestingRtsp] = useState(false);
  const [onvifTimeout, setOnvifTimeout] = useState(DEFAULT_ONVIF_TIMEOUT);
  const [onvifUsername, setOnvifUsername] = useState("");
  const [onvifPassword, setOnvifPassword] = useState("");
  const [onvifTransport, setOnvifTransport] = useState<RTSPTransport>("tcp");
  const [onvifDevices, setOnvifDevices] = useState<ONVIFDevice[]>([]);
  const [selectedOnvifDeviceKey, setSelectedOnvifDeviceKey] = useState("");
  const [onvifStreams, setOnvifStreams] = useState<ONVIFStream[]>([]);
  const [onvifTestResult, setOnvifTestResult] = useState<ONVIFCameraTestResult | null>(null);
  const [isDiscoveringOnvif, setIsDiscoveringOnvif] = useState(false);
  const [isResolvingOnvifStreams, setIsResolvingOnvifStreams] = useState(false);
  const [isTestingOnvif, setIsTestingOnvif] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const {
    feeds,
    feedsQuery,
    systemHealthQuery,
    updateZoneMutation,
    startFeedMutation,
    stopFeedMutation,
    restartFeedMutation,
    deleteFeedMutation,
    activity,
    derived,
  } = useLiveDashboard();
  const batchLaunchMutation = useMutation({
    mutationFn: launchFeedBatch,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["feeds"] });
      await queryClient.invalidateQueries({ queryKey: ["system-health"] });
    },
  });
  const establishmentsQuery = useQuery({
    queryKey: ["establishments"],
    queryFn: listEstablishments,
    enabled: setupStep !== null,
  });
  const caissesQuery = useQuery({
    queryKey: ["establishment-caisses", selectedEstablishmentId],
    queryFn: () => listCaisses(selectedEstablishmentId as number),
    enabled: setupStep !== null && selectedEstablishmentId !== null,
  });
  const createEstablishmentMutation = useMutation({
    mutationFn: createEstablishment,
    onSuccess: async (establishment) => {
      await queryClient.invalidateQueries({ queryKey: ["establishments"] });
      setSelectedEstablishmentId(establishment.id);
      setSelectedCaisseId(null);
      setNewEstablishmentName("");
      setIsCreateEstablishmentDialogOpen(false);
      toast.success(`Establishment ${establishment.name} created.`);
    },
  });
  const createCaisseMutation = useMutation({
    mutationFn: ({ establishmentId, name }: { establishmentId: number; name: string }) =>
      createCaisse(establishmentId, { name }),
    onSuccess: async (caisse) => {
      await queryClient.invalidateQueries({ queryKey: ["establishment-caisses", caisse.establishment_id] });
      setSelectedCaisseId(caisse.id);
      setNewCaisseName("");
      setIsCreateCaisseDialogOpen(false);
      toast.success(`Caisse ${caisse.name} created.`);
    },
  });

  const systemHealth = systemHealthQuery.data;
  const establishments = useMemo(() => establishmentsQuery.data ?? [], [establishmentsQuery.data]);
  const caisses = useMemo(() => caissesQuery.data ?? [], [caissesQuery.data]);
  const emptyState = useMemo(
    () => !feedsQuery.isLoading && feeds.length === 0,
    [feeds.length, feedsQuery.isLoading],
  );
  const selectedOnvifDevice = useMemo(
    () => onvifDevices.find((device) => getOnvifDeviceKey(device) === selectedOnvifDeviceKey) ?? null,
    [onvifDevices, selectedOnvifDeviceKey],
  );
  const selectedEstablishment = useMemo<Establishment | null>(
    () => establishments.find((establishment) => establishment.id === selectedEstablishmentId) ?? null,
    [establishments, selectedEstablishmentId],
  );
  const selectedCaisse = useMemo<Caisse | null>(
    () => caisses.find((caisse) => caisse.id === selectedCaisseId) ?? null,
    [caisses, selectedCaisseId],
  );

  const isSavingSetup = isFinalizingSetup || batchLaunchMutation.isPending || updateZoneMutation.isPending;
  const isReviewSubmitting = isSavingSetup;
  const isTestingCameraSource = isTestingRtsp || isDiscoveringOnvif || isResolvingOnvifStreams || isTestingOnvif;
  const isSavingMetadata = createEstablishmentMutation.isPending || createCaisseMutation.isPending;
  const liveAttentionItems = useMemo(() => {
    const items: Array<{
      id: string;
      title: string;
      detail: string;
      tone: "critical" | "warning";
    }> = [];
    const seenFeedIds = new Set<string>();

    for (const feed of derived.liveMonitoring.feedsWithRuntimeErrors) {
      if (seenFeedIds.has(feed.feed_id)) {
        continue;
      }
      seenFeedIds.add(feed.feed_id);
      items.push({
        id: `runtime-${feed.feed_id}`,
        title: feed.name,
        detail: feed.last_error ?? "Worker reported an error and needs operator attention.",
        tone: "critical",
      });
    }

    for (const feed of derived.liveMonitoring.feedsWithRuntimeWarnings) {
      if (seenFeedIds.has(feed.feed_id) || !feed.last_warning) {
        continue;
      }
      seenFeedIds.add(feed.feed_id);
      items.push({
        id: `warning-${feed.feed_id}`,
        title: feed.name,
        detail: feed.last_warning,
        tone: "warning",
      });
    }

    for (const feed of derived.liveMonitoring.unstableFeeds) {
      if (seenFeedIds.has(feed.feed_id) || !feed.latest_metrics) {
        continue;
      }
      seenFeedIds.add(feed.feed_id);
      items.push({
        id: `unstable-${feed.feed_id}`,
        title: feed.name,
        detail: `Queue is unstable. Arrival ${formatRatePerMinute(feed.latest_metrics.arrival_rate)} exceeds service ${formatRatePerMinute(feed.latest_metrics.service_rate)}.`,
        tone: "warning",
      });
    }

    for (const feed of derived.liveMonitoring.highUncertaintyFeeds) {
      if (seenFeedIds.has(feed.feed_id) || !feed.latest_metrics) {
        continue;
      }
      seenFeedIds.add(feed.feed_id);
      items.push({
        id: `uncertainty-${feed.feed_id}`,
        title: feed.name,
        detail: `High uncertainty on live estimates. Queue size ${feed.latest_metrics.people_in_zone}, wait ${feed.latest_metrics.wait_time_seconds === null ? "pending" : formatWaitTime(feed.latest_metrics.wait_time_seconds)}.`,
        tone: "warning",
      });
    }

    return items.slice(0, 6);
  }, [derived.liveMonitoring]);

  useEffect(() => {
    if (setupStep === null || zonePoints.length > 0 || !selectedCaisse?.zone?.points?.length) {
      return;
    }

    setZonePoints(selectedCaisse.zone.points);
  }, [selectedCaisse, setupStep, zonePoints.length]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    const fileKey = getLocalFileKey(uploadedFile);
    setLocalFileZonePoints((current) => {
      const existing = current[fileKey] ?? [];
      if (areZonePointsEqual(existing, zonePoints)) {
        return current;
      }

      return {
        ...current,
        [fileKey]: zonePoints,
      };
    });
  }, [sourceMode, uploadedFile, zonePoints]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    const fileKey = getLocalFileKey(uploadedFile);
    setLocalFileFeedNames((current) => {
      if (current[fileKey] === feedName) {
        return current;
      }

      return {
        ...current,
        [fileKey]: feedName,
      };
    });
  }, [feedName, sourceMode, uploadedFile]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    const fileKey = getLocalFileKey(uploadedFile);
    setLocalFileModelSelections((current) => {
      if (current[fileKey] === selectedModel) {
        return current;
      }

      return {
        ...current,
        [fileKey]: selectedModel,
      };
    });
  }, [selectedModel, sourceMode, uploadedFile]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    const fileKey = getLocalFileKey(uploadedFile);
    setLocalFileEstablishmentSelections((current) => {
      if (current[fileKey] === selectedEstablishmentId) {
        return current;
      }

      return {
        ...current,
        [fileKey]: selectedEstablishmentId,
      };
    });
  }, [selectedEstablishmentId, sourceMode, uploadedFile]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    const fileKey = getLocalFileKey(uploadedFile);
    setLocalFileCaisseSelections((current) => {
      if (current[fileKey] === selectedCaisseId) {
        return current;
      }

      return {
        ...current,
        [fileKey]: selectedCaisseId,
      };
    });
  }, [selectedCaisseId, sourceMode, uploadedFile]);

  const reviewSourceLabel = useMemo(() => {
    if (sourceMode === "file") {
      return uploadedFile ? uploadedFile.name : "No video selected";
    }

    if (sourceMode === "onvif") {
      return selectedOnvifDevice ? `${selectedOnvifDevice.name} (${selectedOnvifDevice.ip})` : "No ONVIF camera selected";
    }

    return feedSource.trim() || "No RTSP URL provided";
  }, [feedSource, selectedOnvifDevice, sourceMode, uploadedFile]);

  const reviewSourceDetail = useMemo(() => {
    if (sourceMode === "file") {
      return uploadedFile
        ? `The file will be uploaded to the backend and the ${zonePoints.length}-point queue zone will be saved before launch.`
        : "Choose a local video file before reviewing the configuration.";
    }

    if (sourceMode === "rtsp") {
      if (rtspTestResult?.connected) {
        return `${formatResolution(rtspTestResult)} at ${(rtspTestResult.fps ?? 0).toFixed(1)} FPS via ${rtspTransport.toUpperCase()}.`;
      }
      return `Manual RTSP source using ${rtspTransport.toUpperCase()} transport.`;
    }

    if (onvifTestResult?.connected) {
      return `${feedSource || "Resolved stream"} · ${formatResolution(onvifTestResult)} at ${(onvifTestResult.fps ?? 0).toFixed(1)} FPS via ${onvifTransport.toUpperCase()}.`;
    }

    return feedSource.trim() || "Resolve a stream from the selected ONVIF camera before launching.";
  }, [feedSource, onvifTestResult, onvifTransport, rtspTestResult, rtspTransport, sourceMode, uploadedFile, zonePoints.length]);

  const parsedTargetSourceCount = useMemo(() => {
    const parsed = Number.parseInt(targetSourceCount, 10);
    if (Number.isNaN(parsed) || parsed < 1) {
      return 1;
    }
    return parsed;
  }, [targetSourceCount]);

  const buildCurrentDraft = useCallback((): StagedFeedDraft | null => {
    if (!feedName.trim()) {
      return null;
    }

    if (sourceMode === "file" && !uploadedFile) {
      return null;
    }

    if (sourceMode === "rtsp" && (!feedSource.trim() || !rtspTestResult?.connected)) {
      return null;
    }

    if (sourceMode === "onvif" && (!feedSource.trim() || !selectedOnvifDevice || !onvifTestResult?.connected)) {
      return null;
    }

    return {
      clientId: currentDraftId,
      feedName: feedName.trim(),
      sourceMode,
      source: feedSource.trim(),
      uploadedFile,
      zonePoints,
      modelSize: selectedModel,
      establishmentId: selectedEstablishmentId,
      establishmentName: selectedEstablishment?.name ?? null,
      caisseId: selectedCaisseId,
      caisseName: selectedCaisse?.name ?? null,
      hasSavedCaisseZone: Boolean(selectedCaisse?.zone),
      rtspUsername,
      rtspPassword,
      rtspTransport,
      rtspTestResult,
      onvifTimeout,
      onvifUsername,
      onvifPassword,
      onvifTransport,
      onvifDevices,
      selectedOnvifDeviceKey,
      onvifStreams,
      onvifTestResult,
    };
  }, [
    currentDraftId,
    feedName,
    feedSource,
    onvifDevices,
    onvifPassword,
    onvifStreams,
    onvifTestResult,
    onvifTimeout,
    onvifTransport,
    onvifUsername,
    rtspPassword,
    rtspTestResult,
    rtspTransport,
    rtspUsername,
    selectedCaisse?.name,
    selectedCaisse?.zone,
    selectedCaisseId,
    selectedEstablishment?.name,
    selectedEstablishmentId,
    selectedModel,
    selectedOnvifDevice,
    selectedOnvifDeviceKey,
    sourceMode,
    uploadedFile,
    zonePoints,
  ]);

  const localZoneVideoOptions = useMemo(
    () =>
      sourceMode === "file"
        ? [uploadedFile, ...queuedLocalFiles]
            .filter((file): file is File => file !== null)
            .map((file) => ({ key: getLocalFileKey(file), label: file.name }))
        : [],
    [queuedLocalFiles, sourceMode, uploadedFile],
  );
  const selectedLocalZoneVideoKey = uploadedFile ? getLocalFileKey(uploadedFile) : "";
  const allSelectedLocalFiles = useMemo(
    () => [uploadedFile, ...queuedLocalFiles].filter((file): file is File => file !== null),
    [queuedLocalFiles, uploadedFile],
  );
  const preparedLocalFileDrafts = useMemo(
    () =>
      sourceMode === "file"
        ? allSelectedLocalFiles.map((file) => {
            const fileKey = getLocalFileKey(file);
            return {
              clientId: createLocalFileDraftId(file),
              feedName: localFileFeedNames[fileKey]?.trim() || getSuggestedFeedNameFromFile(file),
              sourceMode: "file" as const,
              source: "",
              uploadedFile: file,
              zonePoints: localFileZonePoints[fileKey] ?? [],
              modelSize: localFileModelSelections[fileKey] ?? "n",
              establishmentId: localFileEstablishmentSelections[fileKey] ?? null,
              establishmentName:
                establishments.find((establishment) => establishment.id === (localFileEstablishmentSelections[fileKey] ?? null))?.name ?? null,
              caisseId: localFileCaisseSelections[fileKey] ?? null,
              caisseName: caisses.find((caisse) => caisse.id === (localFileCaisseSelections[fileKey] ?? null))?.name ?? null,
              hasSavedCaisseZone: Boolean(caisses.find((caisse) => caisse.id === (localFileCaisseSelections[fileKey] ?? null))?.zone),
              rtspUsername: "",
              rtspPassword: "",
              rtspTransport: "tcp",
              rtspTestResult: null,
              onvifTimeout: DEFAULT_ONVIF_TIMEOUT,
              onvifUsername: "",
              onvifPassword: "",
              onvifTransport: "tcp",
              onvifDevices: [],
              selectedOnvifDeviceKey: "",
              onvifStreams: [],
              onvifTestResult: null,
            };
          })
        : [],
    [
      allSelectedLocalFiles,
      caisses,
      establishments,
      localFileCaisseSelections,
      localFileEstablishmentSelections,
      localFileFeedNames,
      localFileModelSelections,
      localFileZonePoints,
      sourceMode,
    ],
  );

  const currentReviewDraft = useMemo(
    () => (setupStep === "review" && sourceMode !== "file" ? buildCurrentDraft() : null),
    [buildCurrentDraft, setupStep, sourceMode],
  );

  const reviewItems = useMemo(
    () => [
      ...stagedFeeds.map((draft) => toReviewLaunchItem(draft)),
      ...(setupStep === "review" ? preparedLocalFileDrafts.map((draft) => toReviewLaunchItem(draft)) : []),
      ...(currentReviewDraft ? [toReviewLaunchItem(currentReviewDraft, true)] : []),
    ],
    [currentReviewDraft, preparedLocalFileDrafts, setupStep, stagedFeeds],
  );

  const stagedSourceCount = stagedFeeds.length + preparedLocalFileDrafts.length + (currentReviewDraft ? 1 : 0);
  const remainingSourceCount = Math.max(parsedTargetSourceCount - stagedSourceCount, 0);
  const canSubmitBatch = stagedSourceCount === parsedTargetSourceCount;

  const canContinueSourceStep = useMemo(() => {
    if (!feedName.trim()) {
      return false;
    }

    if (sourceMode === "file") {
      return uploadedFile !== null;
    }

    if (sourceMode === "rtsp") {
      return feedSource.trim().length > 0 && rtspTestResult?.connected === true;
    }

    return Boolean(selectedOnvifDevice && feedSource.trim() && onvifTestResult?.connected);
  }, [feedName, feedSource, onvifTestResult, rtspTestResult, selectedOnvifDevice, sourceMode, uploadedFile]);

  const resetRtspState = useCallback(() => {
    setRtspUsername("");
    setRtspPassword("");
    setRtspTransport("tcp");
    setRtspTestResult(null);
    setIsTestingRtsp(false);
  }, []);

  const resetOnvifState = useCallback(() => {
    setOnvifTimeout(DEFAULT_ONVIF_TIMEOUT);
    setOnvifUsername("");
    setOnvifPassword("");
    setOnvifTransport("tcp");
    setOnvifDevices([]);
    setSelectedOnvifDeviceKey("");
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setIsDiscoveringOnvif(false);
    setIsResolvingOnvifStreams(false);
    setIsTestingOnvif(false);
  }, []);

  const resetCurrentDraft = useCallback(({
    preserveSourceMode = false,
    preserveOnvifDiscovery = false,
    nextUploadedFile = null,
    nextQueuedLocalFiles,
  }: {
    preserveSourceMode?: boolean;
    preserveOnvifDiscovery?: boolean;
    nextUploadedFile?: File | null;
    nextQueuedLocalFiles?: File[];
  } = {}) => {
    const nextSourceMode = preserveSourceMode ? sourceMode : "file";
    setFeedName("");
    setFeedSource("");
    setSourceMode(nextSourceMode);
    setUploadedFile(nextSourceMode === "file" ? nextUploadedFile : null);
    setQueuedLocalFiles(nextSourceMode === "file" ? nextQueuedLocalFiles ?? [] : []);
    setZonePoints(nextSourceMode === "file" && nextUploadedFile ? localFileZonePoints[getLocalFileKey(nextUploadedFile)] ?? [] : []);
    setSelectedModel(nextSourceMode === "file" && nextUploadedFile ? localFileModelSelections[getLocalFileKey(nextUploadedFile)] ?? "n" : "n");
    setSelectedEstablishmentId(nextSourceMode === "file" && nextUploadedFile ? localFileEstablishmentSelections[getLocalFileKey(nextUploadedFile)] ?? null : null);
    setSelectedCaisseId(nextSourceMode === "file" && nextUploadedFile ? localFileCaisseSelections[getLocalFileKey(nextUploadedFile)] ?? null : null);
    if (nextSourceMode === "file" && nextUploadedFile) {
      const fileKey = getLocalFileKey(nextUploadedFile);
      setFeedName(localFileFeedNames[fileKey] ?? getSuggestedFeedNameFromFile(nextUploadedFile));
    }
    if (preserveSourceMode && sourceMode === "rtsp") {
      setRtspTestResult(null);
      setIsTestingRtsp(false);
    } else {
      resetRtspState();
    }
    if (preserveOnvifDiscovery) {
      setSelectedOnvifDeviceKey("");
      setOnvifStreams([]);
      setOnvifTestResult(null);
      setIsDiscoveringOnvif(false);
      setIsResolvingOnvifStreams(false);
      setIsTestingOnvif(false);
    } else {
      resetOnvifState();
    }
    setCurrentDraftId(createDraftId());
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [localFileCaisseSelections, localFileEstablishmentSelections, localFileFeedNames, localFileModelSelections, localFileZonePoints, resetOnvifState, resetRtspState, sourceMode]);

  const resetSetupFlow = () => {
    setSetupStep(null);
    setTargetSourceCount("1");
    setStagedFeeds([]);
    setIsFinalizingSetup(false);
    setBatchLogLevel("INFO");
    setBatchWebhookEnabled(true);
    setIsCreateEstablishmentDialogOpen(false);
    setIsCreateCaisseDialogOpen(false);
    setNewEstablishmentName("");
    setNewCaisseName("");
    setLocalFileEstablishmentSelections({});
    setLocalFileCaisseSelections({});
    setLocalFileFeedNames({});
    setLocalFileModelSelections({});
    setLocalFileZonePoints({});
    resetCurrentDraft();
  };

  const closeFeedZoneEditor = useCallback(() => {
    setEditingFeedZone(null);
    setEditingZonePoints([]);
    setIsSavingEditedZone(false);
  }, []);

  useEffect(() => {
    if (selectedEstablishmentId === null) {
      if (selectedCaisseId !== null) {
        setSelectedCaisseId(null);
      }
      return;
    }

    if (caissesQuery.isLoading) {
      return;
    }

    if (selectedCaisseId !== null && !caisses.some((caisse) => caisse.id === selectedCaisseId)) {
      setSelectedCaisseId(null);
    }
  }, [caisses, caissesQuery.isLoading, selectedCaisseId, selectedEstablishmentId]);

  const handleDialogOpenChange = (open: boolean) => {
    if (!open) {
      resetSetupFlow();
    }
  };

  const loadDraftIntoEditor = useCallback((draft: StagedFeedDraft) => {
    setCurrentDraftId(draft.clientId);
    setFeedName(draft.feedName);
    setSourceMode(draft.sourceMode);
    setFeedSource(draft.source);
    setUploadedFile(draft.uploadedFile);
    setLocalFileEstablishmentSelections((current) => {
      if (draft.sourceMode !== "file" || !draft.uploadedFile) {
        return current;
      }

      return {
        ...current,
        [getLocalFileKey(draft.uploadedFile)]: draft.establishmentId,
      };
    });
    setLocalFileCaisseSelections((current) => {
      if (draft.sourceMode !== "file" || !draft.uploadedFile) {
        return current;
      }

      return {
        ...current,
        [getLocalFileKey(draft.uploadedFile)]: draft.caisseId,
      };
    });
    setLocalFileFeedNames((current) => {
      if (draft.sourceMode !== "file" || !draft.uploadedFile) {
        return current;
      }

      return {
        ...current,
        [getLocalFileKey(draft.uploadedFile)]: draft.feedName,
      };
    });
    setLocalFileModelSelections((current) => {
      if (draft.sourceMode !== "file" || !draft.uploadedFile) {
        return current;
      }

      return {
        ...current,
        [getLocalFileKey(draft.uploadedFile)]: draft.modelSize,
      };
    });
    setLocalFileZonePoints((current) => {
      if (draft.sourceMode !== "file" || !draft.uploadedFile) {
        return current;
      }

      return {
        ...current,
        [getLocalFileKey(draft.uploadedFile)]: draft.zonePoints,
      };
    });
    setQueuedLocalFiles((current) => {
      if (draft.sourceMode !== "file") {
        return current;
      }

      const preservedCurrentFile = sourceMode === "file" && uploadedFile ? [uploadedFile, ...current] : current;
      const excludedKeys = draft.uploadedFile ? [getLocalFileKey(draft.uploadedFile)] : [];
      return dedupeLocalFiles(preservedCurrentFile, excludedKeys);
    });
    setZonePoints(draft.zonePoints);
    setSelectedModel(draft.modelSize);
    setSelectedEstablishmentId(draft.establishmentId);
    setSelectedCaisseId(draft.caisseId);
    setRtspUsername(draft.rtspUsername);
    setRtspPassword(draft.rtspPassword);
    setRtspTransport(draft.rtspTransport);
    setRtspTestResult(draft.rtspTestResult);
    setOnvifTimeout(draft.onvifTimeout);
    setOnvifUsername(draft.onvifUsername);
    setOnvifPassword(draft.onvifPassword);
    setOnvifTransport(draft.onvifTransport);
    setOnvifDevices(draft.onvifDevices);
    setSelectedOnvifDeviceKey(draft.selectedOnvifDeviceKey);
    setOnvifStreams(draft.onvifStreams);
    setOnvifTestResult(draft.onvifTestResult);
    setSetupStep("source");
  }, [sourceMode, uploadedFile]);

  const handleEditStagedFeed = useCallback((clientId: string) => {
    if (isLocalFileDraftId(clientId)) {
      const draftFile = allSelectedLocalFiles.find((file) => createLocalFileDraftId(file) === clientId);
      if (!draftFile) {
        return;
      }

      const remainingFiles = allSelectedLocalFiles.filter((file) => createLocalFileDraftId(file) !== clientId);
      setUploadedFile(draftFile);
      setQueuedLocalFiles(remainingFiles);
      setFeedName(localFileFeedNames[getLocalFileKey(draftFile)] ?? getSuggestedFeedNameFromFile(draftFile));
      setZonePoints(localFileZonePoints[getLocalFileKey(draftFile)] ?? []);
      setSelectedModel(localFileModelSelections[getLocalFileKey(draftFile)] ?? "n");
      setSelectedEstablishmentId(localFileEstablishmentSelections[getLocalFileKey(draftFile)] ?? null);
      setSelectedCaisseId(localFileCaisseSelections[getLocalFileKey(draftFile)] ?? null);
      setCurrentDraftId(createDraftId());
      setSourceMode("file");
      setSetupStep("source");
      return;
    }

    const draft = stagedFeeds.find((item) => item.clientId === clientId);
    if (!draft) {
      return;
    }

    setStagedFeeds((current) => current.filter((item) => item.clientId !== clientId));
    loadDraftIntoEditor(draft);
  }, [allSelectedLocalFiles, loadDraftIntoEditor, localFileCaisseSelections, localFileEstablishmentSelections, localFileFeedNames, localFileModelSelections, localFileZonePoints, stagedFeeds]);

  const handleRemoveStagedFeed = useCallback((clientId: string) => {
    if (isLocalFileDraftId(clientId)) {
      const remainingFiles = allSelectedLocalFiles.filter((file) => createLocalFileDraftId(file) !== clientId);
      const nextActiveFile = uploadedFile && createLocalFileDraftId(uploadedFile) !== clientId
        ? uploadedFile
        : remainingFiles[0] ?? null;
      const nextQueuedFiles = nextActiveFile
        ? remainingFiles.filter((file) => getLocalFileKey(file) !== getLocalFileKey(nextActiveFile))
        : [];

      setUploadedFile(nextActiveFile);
      setQueuedLocalFiles(nextQueuedFiles);
      setFeedName(nextActiveFile ? localFileFeedNames[getLocalFileKey(nextActiveFile)] ?? getSuggestedFeedNameFromFile(nextActiveFile) : "");
      setZonePoints(nextActiveFile ? localFileZonePoints[getLocalFileKey(nextActiveFile)] ?? [] : []);
      setSelectedModel(nextActiveFile ? localFileModelSelections[getLocalFileKey(nextActiveFile)] ?? "n" : "n");
      setSelectedEstablishmentId(nextActiveFile ? localFileEstablishmentSelections[getLocalFileKey(nextActiveFile)] ?? null : null);
      setSelectedCaisseId(nextActiveFile ? localFileCaisseSelections[getLocalFileKey(nextActiveFile)] ?? null : null);
      return;
    }

    setStagedFeeds((current) => current.filter((item) => item.clientId !== clientId));
  }, [allSelectedLocalFiles, localFileCaisseSelections, localFileEstablishmentSelections, localFileFeedNames, localFileModelSelections, localFileZonePoints, uploadedFile]);

  const handleSourceModeChange = (mode: SourceMode) => {
    setSourceMode(mode);
    setFeedSource("");
    if (mode !== "file") {
      setUploadedFile(null);
      setQueuedLocalFiles([]);
      setZonePoints([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
    if (mode !== "rtsp") {
      resetRtspState();
    }
    if (mode !== "onvif") {
      resetOnvifState();
    }
  };

  const handleEstablishmentChange = (value: string) => {
    if (value === UNASSIGNED_SELECT_VALUE) {
      setSelectedEstablishmentId(null);
      setSelectedCaisseId(null);
      return;
    }

    const nextId = Number.parseInt(value, 10);
    if (Number.isNaN(nextId)) {
      return;
    }

    setSelectedEstablishmentId(nextId);
    setSelectedCaisseId(null);
  };

  const handleCaisseChange = (value: string) => {
    if (value === UNASSIGNED_SELECT_VALUE) {
      setSelectedCaisseId(null);
      return;
    }

    const nextId = Number.parseInt(value, 10);
    if (Number.isNaN(nextId)) {
      return;
    }

    setSelectedCaisseId(nextId);
  };

  const handleCreateEstablishment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!newEstablishmentName.trim()) {
      toast.error("Enter an establishment name.");
      return;
    }

    try {
      await createEstablishmentMutation.mutateAsync({ name: newEstablishmentName.trim() });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create the establishment.");
    }
  };

  const handleCreateCaisse = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (selectedEstablishmentId === null) {
      toast.error("Select an establishment before creating a caisse.");
      return;
    }
    if (!newCaisseName.trim()) {
      toast.error("Enter a caisse name.");
      return;
    }

    try {
      await createCaisseMutation.mutateAsync({
        establishmentId: selectedEstablishmentId,
        name: newCaisseName.trim(),
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create the caisse.");
    }
  };

  const handleRemoveQueuedLocalFile = useCallback((fileKey: string) => {
    setQueuedLocalFiles((current) => current.filter((file) => getLocalFileKey(file) !== fileKey));
    setLocalFileZonePoints((current) => {
      if (!(fileKey in current)) {
        return current;
      }

      const next = { ...current };
      delete next[fileKey];
      return next;
    });
  }, []);

  const handleActivateQueuedLocalFile = useCallback((fileKey: string) => {
    setQueuedLocalFiles((current) => {
      const nextFile = current.find((file) => getLocalFileKey(file) === fileKey) ?? null;
      if (!nextFile) {
        return current;
      }

      const remainingFiles = current.filter((file) => getLocalFileKey(file) !== fileKey);
      const nextQueue = uploadedFile ? dedupeLocalFiles([uploadedFile, ...remainingFiles], [getLocalFileKey(nextFile)]) : remainingFiles;

      setUploadedFile(nextFile);
      setFeedName(localFileFeedNames[getLocalFileKey(nextFile)] ?? getSuggestedFeedNameFromFile(nextFile));
      setZonePoints(localFileZonePoints[getLocalFileKey(nextFile)] ?? []);
      setSelectedModel(localFileModelSelections[getLocalFileKey(nextFile)] ?? "n");
      setSelectedEstablishmentId(localFileEstablishmentSelections[getLocalFileKey(nextFile)] ?? null);
      setSelectedCaisseId(localFileCaisseSelections[getLocalFileKey(nextFile)] ?? null);
      setCurrentDraftId(createDraftId());

      return nextQueue;
    });
  }, [localFileCaisseSelections, localFileEstablishmentSelections, localFileFeedNames, localFileModelSelections, localFileZonePoints, uploadedFile]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }

    const nextUploadedFile = uploadedFile ?? selectedFiles[0] ?? null;
    const filesToQueue = uploadedFile ? selectedFiles : selectedFiles.slice(1);
    const nextQueuedLocalFiles = dedupeLocalFiles([
      ...queuedLocalFiles,
      ...filesToQueue,
    ], nextUploadedFile ? [getLocalFileKey(nextUploadedFile)] : []);

    if (!uploadedFile) {
      setUploadedFile(nextUploadedFile);
      setZonePoints(nextUploadedFile ? localFileZonePoints[getLocalFileKey(nextUploadedFile)] ?? [] : []);
      setSelectedModel(nextUploadedFile ? localFileModelSelections[getLocalFileKey(nextUploadedFile)] ?? "n" : "n");
      setSelectedEstablishmentId(nextUploadedFile ? localFileEstablishmentSelections[getLocalFileKey(nextUploadedFile)] ?? null : null);
      setSelectedCaisseId(nextUploadedFile ? localFileCaisseSelections[getLocalFileKey(nextUploadedFile)] ?? null : null);
      if (nextUploadedFile && !feedName.trim()) {
        setFeedName(localFileFeedNames[getLocalFileKey(nextUploadedFile)] ?? getSuggestedFeedNameFromFile(nextUploadedFile));
      }
    }

    setQueuedLocalFiles(nextQueuedLocalFiles);

    const preparedSourceCount = stagedFeeds.length + (nextUploadedFile ? 1 : 0) + nextQueuedLocalFiles.length;
    if (preparedSourceCount > parsedTargetSourceCount) {
      setTargetSourceCount(String(preparedSourceCount));
    }

    if (filesToQueue.length > 0) {
      toast.success(`${filesToQueue.length + (uploadedFile ? 0 : 1)} local video${filesToQueue.length + (uploadedFile ? 0 : 1) === 1 ? "" : "s"} selected. Configure the current file, then the queue will advance automatically.`);
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSelectZoneVideo = useCallback((fileKey: string) => {
    if (!uploadedFile || fileKey === getLocalFileKey(uploadedFile)) {
      return;
    }

    handleActivateQueuedLocalFile(fileKey);
  }, [handleActivateQueuedLocalFile, uploadedFile]);

  const handleSourceStepSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (stagedFeeds.length >= parsedTargetSourceCount) {
      toast.error("The batch already contains the target number of sources. Review or edit the staged feeds before adding more.");
      return;
    }

    if (!feedName.trim()) {
      toast.error("Feed name is required.");
      return;
    }

    if (sourceMode === "file") {
      if (!uploadedFile) {
        toast.error("Choose the MP4 or video file you want to upload.");
        return;
      }
      setSetupStep("zone");
      return;
    }

    if (sourceMode === "rtsp") {
      if (!feedSource.trim()) {
        toast.error("Enter the RTSP URL for the IP camera.");
        return;
      }
      if (rtspPassword.trim() && !rtspUsername.trim()) {
        toast.error("Enter the RTSP username before adding a password.");
        return;
      }
      if (!rtspTestResult?.connected) {
        toast.error("Run a successful RTSP connection test before continuing.");
        return;
      }

      setSetupStep("zone");
      return;
    }

    if (!selectedOnvifDevice) {
      toast.error("Select a discovered ONVIF camera before continuing.");
      return;
    }
    if (!feedSource.trim()) {
      toast.error("Resolve and select an RTSP stream for the ONVIF camera.");
      return;
    }
    if (onvifPassword.trim() && !onvifUsername.trim()) {
      toast.error("Enter the ONVIF username before adding a password.");
      return;
    }
    if (!onvifTestResult?.connected) {
      toast.error("Run a successful ONVIF camera test before continuing.");
      return;
    }

    setSetupStep("zone");
  };

  const handleStageCurrentDraft = useCallback(() => {
    const draft = buildCurrentDraft();
    if (!draft) {
      toast.error("Finish the current source configuration before staging it.");
      return;
    }

    const nextCount = stagedFeeds.length + 1;
    if (nextCount > parsedTargetSourceCount) {
      toast.error(`This batch is configured for ${parsedTargetSourceCount} source${parsedTargetSourceCount === 1 ? "" : "s"}. Remove a staged item or increase the target count first.`);
      return;
    }

    setStagedFeeds((current) => [...current, draft]);
    const preserveOnvifDiscovery = draft.sourceMode === "onvif";
    const nextUploadedFile = draft.sourceMode === "file" ? queuedLocalFiles[0] ?? null : null;
    const nextQueuedLocalFiles = draft.sourceMode === "file" ? queuedLocalFiles.slice(1) : [];
    resetCurrentDraft({
      preserveSourceMode: true,
      preserveOnvifDiscovery,
      nextUploadedFile,
      nextQueuedLocalFiles,
    });
    setSetupStep(nextCount >= parsedTargetSourceCount ? "review" : "source");
    toast.success(`${draft.feedName} added to the staged batch.`);
  }, [buildCurrentDraft, parsedTargetSourceCount, queuedLocalFiles, resetCurrentDraft, stagedFeeds.length]);

  const handleOpenBatchReview = useCallback(() => {
    if (stagedFeeds.length === 0) {
      toast.error("Stage at least one source before opening the batch review.");
      return;
    }

    resetCurrentDraft({ preserveSourceMode: true, preserveOnvifDiscovery: sourceMode === "onvif" });
    setSetupStep("review");
  }, [resetCurrentDraft, sourceMode, stagedFeeds.length]);

  const buildSnapshotLoader = useCallback(async (): Promise<{
    frameSrc: string;
    sourceLabel: string;
    sourceKind: string;
  }> => {
    let snapshotResult: RTSPSnapshotResult;

    if (sourceMode === "rtsp") {
      snapshotResult = await captureRtspSnapshot({
        url: feedSource.trim(),
        username: rtspUsername.trim() || undefined,
        password: rtspPassword.trim() || undefined,
        transport: rtspTransport,
      });
    } else {
      snapshotResult = await captureRtspSnapshot({
        url: feedSource.trim(),
        username: onvifUsername.trim() || undefined,
        password: onvifPassword.trim() || undefined,
        transport: onvifTransport,
      });
    }

    if (!snapshotResult.captured || !snapshotResult.image_data_url) {
      throw new Error(snapshotResult.error ?? "The backend could not capture a preview frame from this camera.");
    }

    if (sourceMode === "rtsp") {
      return {
        frameSrc: snapshotResult.image_data_url,
        sourceLabel: feedSource.trim(),
        sourceKind: "RTSP preview",
      };
    }

    return {
      frameSrc: snapshotResult.image_data_url,
      sourceLabel: selectedOnvifDevice ? `${selectedOnvifDevice.name} (${selectedOnvifDevice.ip})` : feedSource.trim(),
      sourceKind: "ONVIF snapshot",
    };
  }, [feedSource, onvifPassword, onvifTransport, onvifUsername, rtspPassword, rtspTransport, rtspUsername, selectedOnvifDevice, sourceMode]);

  const loadExistingFeedSnapshot = useCallback(async (): Promise<{
    frameSrc: string;
    sourceLabel: string;
    sourceKind: string;
  }> => {
    if (!editingFeedZone) {
      throw new Error("No feed selected for zone editing.");
    }

    const snapshot = await getFeedSnapshot(editingFeedZone.feed_id);
    if (!snapshot.captured || !snapshot.image_data_url) {
      throw new Error(snapshot.error ?? "Unable to capture a preview frame for this feed.");
    }

    return {
      frameSrc: snapshot.image_data_url,
      sourceLabel: snapshot.source,
      sourceKind: "Existing feed",
    };
  }, [editingFeedZone]);

  const openFeedZoneEditor = useCallback((feed: VideoFeed) => {
    setEditingFeedZone(feed);
    setEditingZonePoints(feed.zone?.points ?? []);
  }, []);

  const handleTestRtsp = async () => {
    if (!feedSource.trim()) {
      toast.error("Enter the RTSP URL first.");
      return;
    }
    if (rtspPassword.trim() && !rtspUsername.trim()) {
      toast.error("Enter the RTSP username before adding a password.");
      return;
    }

    setIsTestingRtsp(true);
    try {
      const result = await testRtspConnection({
        url: feedSource.trim(),
        username: rtspUsername.trim() || undefined,
        password: rtspPassword.trim() || undefined,
        transport: rtspTransport,
      });
      setRtspTestResult(result);

      if (result.connected) {
        if (!feedName.trim()) {
          const suggestedName = suggestFeedNameFromRtspUrl(feedSource.trim());
          if (suggestedName) {
            setFeedName(suggestedName);
          }
        }
        toast.success(`RTSP connection OK: ${formatResolution(result)} @ ${(result.fps ?? 0).toFixed(1)} FPS.`);
      } else {
        toast.error(result.error ?? "RTSP connection failed.");
      }
    } catch (error) {
      setRtspTestResult(null);
      toast.error(error instanceof Error ? error.message : "Failed to test the RTSP source.");
    } finally {
      setIsTestingRtsp(false);
    }
  };

  const handleDiscoverOnvif = async () => {
    const timeoutSeconds = Number.parseFloat(onvifTimeout);
    if (Number.isNaN(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 30) {
      toast.error("Enter an ONVIF discovery timeout between 0 and 30 seconds.");
      return;
    }

    setIsDiscoveringOnvif(true);
    setOnvifDevices([]);
    setSelectedOnvifDeviceKey("");
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setFeedSource("");

    try {
      const devices = await discoverOnvifDevices({ timeout_seconds: timeoutSeconds });
      setOnvifDevices(devices);

      if (devices.length > 0) {
        const firstDevice = devices[0];
        setSelectedOnvifDeviceKey(getOnvifDeviceKey(firstDevice));
        if (!feedName.trim()) {
          setFeedName(firstDevice.name);
        }
        toast.success(`Found ${devices.length} ONVIF camera${devices.length === 1 ? "" : "s"}.`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to discover ONVIF cameras.");
    } finally {
      setIsDiscoveringOnvif(false);
    }
  };

  const handleSelectOnvifDevice = (device: ONVIFDevice) => {
    setSelectedOnvifDeviceKey(getOnvifDeviceKey(device));
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setFeedSource("");
    if (!feedName.trim()) {
      setFeedName(device.name);
    }
  };

  const handleResolveOnvifStreams = async () => {
    if (!selectedOnvifDevice) {
      toast.error("Select an ONVIF camera first.");
      return;
    }
    if (onvifPassword.trim() && !onvifUsername.trim()) {
      toast.error("Enter the ONVIF username before adding a password.");
      return;
    }

    setIsResolvingOnvifStreams(true);
    setOnvifTestResult(null);

    try {
      const streams = await resolveOnvifStreams({
        device: selectedOnvifDevice,
        username: onvifUsername.trim() || undefined,
        password: onvifPassword.trim() || undefined,
      });
      setOnvifStreams(streams);

      if (streams.length === 0) {
        setFeedSource("");
        toast.error("No RTSP streams were resolved for the selected ONVIF camera.");
        return;
      }

      setFeedSource((currentSource) =>
        streams.some((stream) => stream.url === currentSource) ? currentSource : streams[0].url,
      );
      toast.success(`Resolved ${streams.length} RTSP stream${streams.length === 1 ? "" : "s"}.`);
    } catch (error) {
      setOnvifStreams([]);
      setFeedSource("");
      toast.error(error instanceof Error ? error.message : "Failed to resolve ONVIF camera streams.");
    } finally {
      setIsResolvingOnvifStreams(false);
    }
  };

  const handleTestOnvif = async () => {
    if (!selectedOnvifDevice) {
      toast.error("Select an ONVIF camera first.");
      return;
    }
    if (onvifPassword.trim() && !onvifUsername.trim()) {
      toast.error("Enter the ONVIF username before adding a password.");
      return;
    }

    setIsTestingOnvif(true);

    try {
      const result = await testOnvifCamera({
        device: selectedOnvifDevice,
        username: onvifUsername.trim() || undefined,
        password: onvifPassword.trim() || undefined,
        transport: onvifTransport,
      });
      setOnvifTestResult(result);

      if (result.streams.length > 0) {
        setOnvifStreams(result.streams);
        setFeedSource((currentSource) => {
          if (result.streams.some((stream) => stream.url === currentSource)) {
            return currentSource;
          }
          return result.tested_stream?.url ?? result.streams[0]?.url ?? "";
        });
      }

      if (result.connected) {
        if (!feedName.trim()) {
          setFeedName(selectedOnvifDevice.name);
        }
        toast.success(`ONVIF camera OK: ${formatResolution(result)} @ ${(result.fps ?? 0).toFixed(1)} FPS.`);
      } else {
        toast.error(result.error ?? "ONVIF camera test failed.");
      }
    } catch (error) {
      setOnvifTestResult(null);
      toast.error(error instanceof Error ? error.message : "Failed to test the ONVIF camera.");
    } finally {
      setIsTestingOnvif(false);
    }
  };

  const handleFinalizeBatch = async (launchAfterCreate: boolean) => {
    const currentDraft = currentReviewDraft;
    const drafts = [...stagedFeeds, ...preparedLocalFileDrafts, ...(currentDraft ? [currentDraft] : [])];

    if (drafts.length === 0) {
      toast.error("Stage at least one source before submitting the batch.");
      return;
    }

    if (drafts.length !== parsedTargetSourceCount) {
      toast.error(`This batch expects exactly ${parsedTargetSourceCount} source${parsedTargetSourceCount === 1 ? "" : "s"}.`);
      return;
    }

    setIsFinalizingSetup(true);

    try {
      const preparedFeeds: BatchFeedDraft[] = [];

      for (const draft of drafts) {
        let source = draft.source.trim();

        if (draft.sourceMode === "file") {
          if (!draft.uploadedFile) {
            throw new Error(`Choose a video file for ${draft.feedName} before submitting the batch.`);
          }

          const upload = await uploadVideo(draft.uploadedFile);
          source = upload.file_path;
        }

        preparedFeeds.push({
          client_id: draft.clientId,
          name: draft.feedName,
          source,
          model_size: draft.modelSize,
          establishment_id: draft.establishmentId,
          caisse_id: draft.caisseId,
          zone: draft.zonePoints.length >= 3 ? { points: draft.zonePoints } : null,
          rtsp_username:
            draft.sourceMode === "rtsp"
              ? draft.rtspUsername.trim() || null
              : draft.sourceMode === "onvif"
                ? draft.onvifUsername.trim() || null
                : null,
          rtsp_password:
            draft.sourceMode === "rtsp"
              ? draft.rtspPassword.trim() || null
              : draft.sourceMode === "onvif"
                ? draft.onvifPassword.trim() || null
                : null,
          rtsp_transport:
            draft.sourceMode === "rtsp"
              ? draft.rtspTransport
              : draft.sourceMode === "onvif"
                ? draft.onvifTransport
                : null,
        });
      }

      const result = await batchLaunchMutation.mutateAsync({
        launch_mode: launchAfterCreate ? "create_and_start" : "save_only",
        runtime: {
          log_level: batchLogLevel,
          webhook_enabled: batchWebhookEnabled,
        },
        feeds: preparedFeeds,
      });

      const failedIds = new Set(result.results.filter((item) => item.status === "failed").map((item) => item.client_id));
      if (failedIds.size > 0) {
        const failedCameraDrafts = drafts.filter((draft) => failedIds.has(draft.clientId) && !isLocalFileDraftId(draft.clientId));
        const failedLocalFiles = allSelectedLocalFiles.filter((file) => failedIds.has(createLocalFileDraftId(file)));
        const nextActiveLocalFile = failedLocalFiles[0] ?? null;

        setStagedFeeds(failedCameraDrafts);
        setUploadedFile(nextActiveLocalFile);
        setQueuedLocalFiles(nextActiveLocalFile ? failedLocalFiles.slice(1) : []);
        setFeedName(nextActiveLocalFile ? localFileFeedNames[getLocalFileKey(nextActiveLocalFile)] ?? getSuggestedFeedNameFromFile(nextActiveLocalFile) : "");
        setZonePoints(nextActiveLocalFile ? localFileZonePoints[getLocalFileKey(nextActiveLocalFile)] ?? [] : []);
        setSelectedModel(nextActiveLocalFile ? localFileModelSelections[getLocalFileKey(nextActiveLocalFile)] ?? "n" : "n");
        setSelectedEstablishmentId(nextActiveLocalFile ? localFileEstablishmentSelections[getLocalFileKey(nextActiveLocalFile)] ?? null : null);
        setSelectedCaisseId(nextActiveLocalFile ? localFileCaisseSelections[getLocalFileKey(nextActiveLocalFile)] ?? null : null);
        setCurrentDraftId(createDraftId());
        setSetupStep("review");
        toast.error(
          launchAfterCreate
            ? `${result.summary.started} source${result.summary.started === 1 ? "" : "s"} started, ${result.summary.failed} failed. Failed drafts remain staged for correction.`
            : `${result.summary.created} source${result.summary.created === 1 ? "" : "s"} saved, ${result.summary.failed} failed. Failed drafts remain staged for correction.`,
        );
        return;
      }

      toast.success(
        launchAfterCreate
          ? `Batch launched successfully: ${result.summary.started} source${result.summary.started === 1 ? "" : "s"} started.`
          : `Batch saved successfully: ${result.summary.created} source${result.summary.created === 1 ? "" : "s"} created.`,
      );
      resetSetupFlow();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to submit the staged batch.");
    } finally {
      setIsFinalizingSetup(false);
    }
  };

  const handleConfirmDeleteFeed = async () => {
    if (!feedPendingDeletion) {
      return;
    }

    const feed = feedPendingDeletion;
    setActiveFeedAction({ feedId: feed.feed_id, action: "delete" });

    try {
      await deleteFeedMutation.mutateAsync(feed.feed_id);
      toast.success(`${feed.name} removed.`);
      setFeedPendingDeletion(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete the feed.");
    } finally {
      setActiveFeedAction(null);
    }
  };

  const handleFeedAction = async (feed: VideoFeed, action: FeedAction) => {
    if (action === "delete") {
      setFeedPendingDeletion(feed);
      return;
    }

    setActiveFeedAction({ feedId: feed.feed_id, action });

    try {
      if (action === "start") {
        await startFeedMutation.mutateAsync(feed.feed_id);
        toast.success(`${feed.name} started.`);
        return;
      }

      if (action === "stop") {
        await stopFeedMutation.mutateAsync(feed.feed_id);
        toast.success(`${feed.name} stopped.`);
        return;
      }

      await restartFeedMutation.mutateAsync(feed.feed_id);
      toast.success(`${feed.name} restarted.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Failed to ${action} the feed.`);
    } finally {
      setActiveFeedAction(null);
    }
  };

  const handleSaveEditedZone = useCallback(async () => {
    if (!editingFeedZone) {
      return;
    }

    if (editingZonePoints.length < 3) {
      toast.error("Define at least 3 points before saving the updated zone.");
      return;
    }

    setIsSavingEditedZone(true);

    try {
      await updateZoneMutation.mutateAsync({
        feedId: editingFeedZone.feed_id,
        zone: { points: editingZonePoints },
      });
      toast.success(`Updated queue zone for ${editingFeedZone.name}.`);
      closeFeedZoneEditor();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update the queue zone.");
    } finally {
      setIsSavingEditedZone(false);
    }
  }, [closeFeedZoneEditor, editingFeedZone, editingZonePoints, updateZoneMutation]);

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="text-sm text-muted-foreground">Real-time surveillance wall for all configured queue feeds</p>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => setSetupStep("source")}>
              <Plus className="mr-1 h-4 w-4" />
              Setup Batch
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 animate-fade-in-up sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            title="Registered Feeds"
            value={derived.registeredFeeds}
            icon={Camera}
            subtitle={systemHealth ? `${systemHealth.websocket_clients} dashboard clients connected` : "Waiting for backend API"}
          />
          <KpiCard title="Running Feeds" value={derived.onlineFeeds} icon={Radio} subtitle="Use the wall controls to start, stop, and restart workers" />
          <KpiCard title="People In Queue" value={derived.peopleTotal} icon={Users} />
          <KpiCard
            title="Live Attention"
            value={derived.liveMonitoring.attentionFeedCount}
            icon={AlertTriangle}
            subtitle={systemHealth ? `API ${systemHealth.status} · ${activity.length} recent events` : "No API heartbeat yet"}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div>
              <h2 className="mb-3 text-sm font-semibold text-foreground">Surveillance Wall</h2>
              {emptyState && (
                <div className="rounded-lg border border-dashed border-border bg-card/60 p-8 text-center">
                  <Camera className="mx-auto h-10 w-10 text-primary/50" />
                  <p className="mt-3 text-sm font-medium text-foreground">No feeds configured yet</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Upload an MP4, validate an RTSP camera, or discover an ONVIF source to start the queue workflow.
                  </p>
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {feeds.map((feed) => {
                  const uiStatus = mapFeedStatus(feed.status);
                  const peopleInZone = feed.latest_metrics?.people_in_zone ?? 0;
                  const waitTimeSeconds = feed.latest_metrics?.wait_time_seconds;
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
                        waitTimeSeconds={waitTimeSeconds}
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
                          {feed.last_warning && (
                            <Badge variant="secondary">{isRecoveryWarning(feed) ? "Recovery notice" : "Worker warning"}</Badge>
                          )}
                          {feed.latest_metrics && (
                            <>
                              <Badge variant={feed.latest_metrics.queue_stable ? "outline" : "destructive"}>
                                {feed.latest_metrics.queue_stable ? "Stable queue" : "Unstable queue"}
                              </Badge>
                              <Badge variant={getUncertaintyTone(feed.latest_metrics.uncertainty_level)}>
                                {feed.latest_metrics.uncertainty_level} uncertainty
                              </Badge>
                            </>
                          )}
                          <Button onClick={() => openFeedZoneEditor(feed)} size="sm" type="button" variant="outline">
                            Edit Zone
                          </Button>
                          <Button
                            onClick={() => handleFeedAction(feed, canStop ? "stop" : "start")}
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
                            onClick={() => handleFeedAction(feed, "restart")}
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
                            onClick={() => handleFeedAction(feed, "delete")}
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
                              <div className={`rounded-lg border p-3 ${isRecoveryWarning(feed) ? "border-amber-500/40 bg-amber-500/10" : "border-border bg-background/50"}`}>
                                <div className="flex items-start gap-2">
                                  <AlertTriangle className={`mt-0.5 h-4 w-4 ${isRecoveryWarning(feed) ? "text-amber-300" : "text-primary"}`} />
                                  <div>
                                    <p className={`text-xs font-semibold ${isRecoveryWarning(feed) ? "text-amber-100" : "text-foreground"}`}>
                                      {isRecoveryWarning(feed) ? "Recovery required" : "Worker warning"}
                                    </p>
                                    <p className={`mt-1 text-xs leading-relaxed ${isRecoveryWarning(feed) ? "text-amber-50" : "text-muted-foreground"}`}>{feed.last_warning}</p>
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
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="mb-4 text-sm font-semibold text-foreground">Current Wait Time by Feed</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={derived.waitChartData}>
                    <CartesianGrid stroke="hsl(215 25% 20%)" strokeDasharray="3 3" />
                    <XAxis axisLine={false} dataKey="name" tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} />
                    <YAxis axisLine={false} tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(217 48% 10%)",
                        border: "1px solid hsl(215 25% 20%)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "hsl(215 16% 57%)" }}
                    />
                    <Line dataKey="value" dot={false} stroke="hsl(187 82% 53%)" strokeWidth={2} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="mb-4 text-sm font-semibold text-foreground">Queue Size by Feed</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={derived.queueChartData}>
                    <CartesianGrid stroke="hsl(215 25% 20%)" strokeDasharray="3 3" />
                    <XAxis axisLine={false} dataKey="name" tick={{ fill: "hsl(215 16% 57%)", fontSize: 10 }} />
                    <YAxis axisLine={false} tick={{ fill: "hsl(215 16% 57%)", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(217 48% 10%)",
                        border: "1px solid hsl(215 25% 20%)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" fill="hsl(187 82% 53%)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <AlertTriangle className="h-4 w-4 text-primary" />
                Attention Required
              </h2>
              <div className="mt-2 space-y-2">
                {liveAttentionItems.length === 0 ? (
                  <div className="rounded-lg border border-border bg-card p-3 text-sm">
                    <p className="text-xs leading-relaxed text-foreground">No feeds currently require immediate operator action.</p>
                    <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">Stable queue metrics and worker states across the wall</p>
                  </div>
                ) : (
                  liveAttentionItems.map((item) => (
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
              {activity.map((alert) => (
                <div
                  key={alert.id}
                  className={`rounded-lg border p-3 text-sm transition-all hover:bg-accent/50 ${getActivityCardClassName(alert.severity)}`}
                >
                  <div className="flex items-start gap-2">
                    {alert.severity === "critical" ? (
                      <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                    ) : alert.severity === "warning" ? (
                      <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
                    ) : alert.severity === "success" ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                    ) : (
                      <Activity className="mt-0.5 h-4 w-4 text-primary" />
                    )}
                    <div>
                      <p className={`text-xs leading-relaxed ${getActivityTextClassName(alert.severity)}`}>{alert.message}</p>
                      <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">{alert.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          </div>
        </div>

        <Dialog open={setupStep === "source"} onOpenChange={handleDialogOpenChange}>
          <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle className="text-foreground">Stage Sources</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Enter the feed information, select the required videos or camera sources, optionally attach metadata, then continue through zone tracing, model selection, and review.
              </DialogDescription>
            </DialogHeader>

            <form className="space-y-4" onSubmit={handleSourceStepSubmit}>
              <div className="grid gap-4 rounded-xl border border-border bg-background/40 p-4 md:grid-cols-[180px_minmax(0,1fr)] md:items-end">
                <div className="space-y-2">
                  <Label className="text-foreground" htmlFor="target-source-count">
                    Source count target
                  </Label>
                  <Input
                    id="target-source-count"
                    inputMode="numeric"
                    min="1"
                    onChange={(event) => setTargetSourceCount(event.target.value)}
                    value={targetSourceCount}
                  />
                </div>
                <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                  {stagedSourceCount} prepared so far. This session must contain exactly {parsedTargetSourceCount} source{parsedTargetSourceCount === 1 ? "" : "s"} before review and launch.
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-foreground" htmlFor="feed-name">
                  Feed name
                </Label>
                <Input
                  id="feed-name"
                  onChange={(event) => setFeedName(event.target.value)}
                  placeholder="Checkout 1"
                  required
                  value={feedName}
                />
              </div>

              <Tabs className="space-y-4" onValueChange={(value) => handleSourceModeChange(value as SourceMode)} value={sourceMode}>
                <div className="space-y-2">
                  <span className="text-sm font-medium text-foreground">Source type</span>
                  <TabsList className="grid h-auto w-full grid-cols-3 gap-1 bg-muted/60 p-1">
                    <TabsTrigger className="py-2" value="file">
                      Local MP4
                    </TabsTrigger>
                    <TabsTrigger className="py-2" value="rtsp">
                      RTSP Camera
                    </TabsTrigger>
                    <TabsTrigger className="py-2" value="onvif">
                      ONVIF Discovery
                    </TabsTrigger>
                  </TabsList>
                </div>

                <TabsContent className="mt-0" value="file">
                  <div className="space-y-3 rounded-xl border border-border bg-background/40 p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-lg bg-primary/10 p-2 text-primary">
                        <Video className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Upload a local video</p>
                        <p className="text-xs text-muted-foreground">
                          Supported formats: MP4, MOV, AVI, and MKV. The backend stores the file and uses its path automatically.
                        </p>
                      </div>
                    </div>

                    <input
                      accept=".mp4,.avi,.mov,.mkv,video/*"
                      className="hidden"
                      multiple
                      onChange={handleFileChange}
                      ref={fileInputRef}
                      type="file"
                    />

                    <div className="flex flex-wrap items-center gap-3">
                      <Button onClick={() => fileInputRef.current?.click()} type="button" variant="outline">
                        <Upload className="mr-2 h-4 w-4" />
                        Choose Video Files
                      </Button>
                      <span className="text-sm text-muted-foreground">{getFileLabel(uploadedFile)}</span>
                    </div>

                    <p className="text-xs text-muted-foreground">
                      Local videos are configured one source at a time so each feed can keep its own queue zone and model. You can now select several videos in one click, then the queue will advance after each source is staged.
                    </p>

                    <p className="text-xs text-muted-foreground">
                      Before opening zone selection, use the queue below to choose which video is active. The active video is the one whose frame will be used for tracing.
                    </p>

                    {(uploadedFile || queuedLocalFiles.length > 0) && (
                      <div className="space-y-3 rounded-lg border border-border bg-background/50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-foreground">Selected local videos</p>
                            <p className="text-xs text-muted-foreground">Current file is configured now. Remaining files stay queued for the next passes.</p>
                          </div>
                          <Badge variant="outline">{(uploadedFile ? 1 : 0) + queuedLocalFiles.length} selected</Badge>
                        </div>

                        {uploadedFile && (
                          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="outline">Now configuring</Badge>
                              <p className="text-sm font-medium text-foreground">{uploadedFile.name}</p>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{getFileLabel(uploadedFile)}</p>
                          </div>
                        )}

                        {queuedLocalFiles.length > 0 && (
                          <div className="grid gap-2">
                            {queuedLocalFiles.map((file, index) => (
                              <div key={getLocalFileKey(file)} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/60 p-3">
                                <div>
                                  <p className="text-sm font-medium text-foreground">Up next {index + 1}: {file.name}</p>
                                  <p className="text-xs text-muted-foreground">{getFileLabel(file)}</p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <Button onClick={() => handleActivateQueuedLocalFile(getLocalFileKey(file))} size="sm" type="button" variant="outline">
                                    Use This Video Now
                                  </Button>
                                  <Button onClick={() => handleRemoveQueuedLocalFile(getLocalFileKey(file))} size="sm" type="button" variant="outline">
                                    Remove
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </TabsContent>

                <TabsContent className="mt-0" value="rtsp">
                  <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-lg bg-primary/10 p-2 text-primary">
                        <Camera className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Manual RTSP onboarding</p>
                        <p className="text-xs text-muted-foreground">
                          Match the desktop GUI flow by validating the camera URL, credentials, and transport before the feed is registered.
                        </p>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-foreground" htmlFor="feed-source">
                        RTSP URL
                      </Label>
                      <Input
                        id="feed-source"
                        onChange={(event) => {
                          setFeedSource(event.target.value);
                          setRtspTestResult(null);
                        }}
                        placeholder="rtsp://192.168.1.10:554/live/main"
                        required={sourceMode === "rtsp"}
                        value={feedSource}
                      />
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label className="text-foreground" htmlFor="rtsp-username">
                          Username
                        </Label>
                        <Input
                          id="rtsp-username"
                          onChange={(event) => {
                            setRtspUsername(event.target.value);
                            setRtspTestResult(null);
                          }}
                          placeholder="admin"
                          value={rtspUsername}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-foreground" htmlFor="rtsp-password">
                          Password
                        </Label>
                        <Input
                          id="rtsp-password"
                          onChange={(event) => {
                            setRtspPassword(event.target.value);
                            setRtspTestResult(null);
                          }}
                          placeholder="Optional"
                          type="password"
                          value={rtspPassword}
                        />
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                      <div className="space-y-2">
                        <Label className="text-foreground">Transport</Label>
                        <Select
                          onValueChange={(value) => {
                            setRtspTransport(value as RTSPTransport);
                            setRtspTestResult(null);
                          }}
                          value={rtspTransport}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select RTSP transport" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="tcp">TCP</SelectItem>
                            <SelectItem value="udp">UDP</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Button onClick={handleTestRtsp} type="button" variant="outline" disabled={isTestingRtsp}>
                        {isTestingRtsp ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                        Test Connection
                      </Button>
                    </div>

                    {rtspTestResult ? (
                      <div
                        className={`rounded-lg border p-3 ${
                          rtspTestResult.connected
                            ? "border-emerald-500/40 bg-emerald-500/10"
                            : "border-destructive/40 bg-destructive/10"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {rtspTestResult.connected ? (
                            <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-400" />
                          ) : (
                            <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                          )}
                          <div className="space-y-1 text-sm">
                            <p className="font-medium text-foreground">
                              {rtspTestResult.connected ? "Connection successful" : "Connection failed"}
                            </p>
                            {rtspTestResult.connected ? (
                              <p className="text-muted-foreground">
                                {formatResolution(rtspTestResult)} at {(rtspTestResult.fps ?? 0).toFixed(1)} FPS via {rtspTestResult.transport.toUpperCase()}.
                              </p>
                            ) : (
                              <p className="text-muted-foreground">{rtspTestResult.error ?? "The backend could not open this RTSP stream."}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Run the RTSP test before continuing. This keeps the web onboarding flow aligned with the desktop GUI.
                      </p>
                    )}
                  </div>
                </TabsContent>

                <TabsContent className="mt-0" value="onvif">
                  <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-lg bg-primary/10 p-2 text-primary">
                        <Search className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">Discover ONVIF cameras</p>
                        <p className="text-xs text-muted-foreground">
                          Discover ONVIF devices, resolve their RTSP streams, then run a backend camera test before choosing the model.
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-[180px_auto] md:items-end">
                      <div className="space-y-2">
                        <Label className="text-foreground" htmlFor="onvif-timeout">
                          Discovery timeout (s)
                        </Label>
                        <Input
                          id="onvif-timeout"
                          inputMode="decimal"
                          onChange={(event) => setOnvifTimeout(event.target.value)}
                          placeholder="5"
                          value={onvifTimeout}
                        />
                      </div>
                      <Button onClick={handleDiscoverOnvif} type="button" variant="outline" disabled={isDiscoveringOnvif}>
                        {isDiscoveringOnvif ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                        Discover Cameras
                      </Button>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{onvifDevices.length} discovered</Badge>
                      {selectedOnvifDevice && <Badge variant="outline">Selected: {selectedOnvifDevice.name}</Badge>}
                    </div>

                    <div className="space-y-2">
                      {onvifDevices.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-border bg-background/50 p-4 text-sm text-muted-foreground">
                          Discover ONVIF devices on the local network to continue this camera onboarding path.
                        </div>
                      ) : (
                        <div className="grid max-h-64 gap-2 overflow-y-auto pr-1">
                          {onvifDevices.map((device) => {
                            const isSelected = selectedOnvifDeviceKey === getOnvifDeviceKey(device);

                            return (
                              <button
                                key={getOnvifDeviceKey(device)}
                                className={`rounded-xl border p-3 text-left transition-colors ${
                                  isSelected
                                    ? "border-primary bg-primary/10"
                                    : "border-border bg-background/50 hover:border-primary/40"
                                }`}
                                onClick={() => handleSelectOnvifDevice(device)}
                                type="button"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-medium text-foreground">{device.name}</p>
                                    <p className="font-mono text-xs text-muted-foreground">{device.ip}</p>
                                  </div>
                                  <Badge variant="outline">{device.model}</Badge>
                                </div>
                                <p className="mt-2 text-xs text-muted-foreground">
                                  {device.manufacturer} · {device.location} · {Object.keys(device.services).length} services
                                </p>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label className="text-foreground" htmlFor="onvif-username">
                          ONVIF username
                        </Label>
                        <Input
                          id="onvif-username"
                          onChange={(event) => {
                            setOnvifUsername(event.target.value);
                            setOnvifStreams([]);
                            setOnvifTestResult(null);
                            setFeedSource("");
                          }}
                          placeholder="admin"
                          value={onvifUsername}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-foreground" htmlFor="onvif-password">
                          ONVIF password
                        </Label>
                        <Input
                          id="onvif-password"
                          onChange={(event) => {
                            setOnvifPassword(event.target.value);
                            setOnvifStreams([]);
                            setOnvifTestResult(null);
                            setFeedSource("");
                          }}
                          placeholder="Optional"
                          type="password"
                          value={onvifPassword}
                        />
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-end">
                      <div className="space-y-2">
                        <Label className="text-foreground">Transport</Label>
                        <Select
                          onValueChange={(value) => {
                            setOnvifTransport(value as RTSPTransport);
                            setOnvifTestResult(null);
                          }}
                          value={onvifTransport}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select RTSP transport" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="tcp">TCP</SelectItem>
                            <SelectItem value="udp">UDP</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        onClick={handleResolveOnvifStreams}
                        type="button"
                        variant="outline"
                        disabled={!selectedOnvifDevice || isResolvingOnvifStreams || isTestingOnvif}
                      >
                        {isResolvingOnvifStreams ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Resolve Streams
                      </Button>
                      <Button
                        onClick={handleTestOnvif}
                        type="button"
                        variant="outline"
                        disabled={!selectedOnvifDevice || isTestingOnvif || isResolvingOnvifStreams}
                      >
                        {isTestingOnvif ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                        Test Camera
                      </Button>
                    </div>

                    {onvifStreams.length > 0 && (
                      <div className="space-y-2">
                        <Label className="text-foreground">Resolved RTSP stream</Label>
                        <Select onValueChange={setFeedSource} value={feedSource}>
                          <SelectTrigger>
                            <SelectValue placeholder="Choose the stream to register" />
                          </SelectTrigger>
                          <SelectContent>
                            {onvifStreams.map((stream) => (
                              <SelectItem key={stream.url} value={stream.url}>
                                {stream.url}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {onvifTestResult ? (
                      <div
                        className={`rounded-lg border p-3 ${
                          onvifTestResult.connected
                            ? "border-emerald-500/40 bg-emerald-500/10"
                            : "border-destructive/40 bg-destructive/10"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {onvifTestResult.connected ? (
                            <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-400" />
                          ) : (
                            <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                          )}
                          <div className="space-y-1 text-sm">
                            <p className="font-medium text-foreground">
                              {onvifTestResult.connected ? "Camera test successful" : "Camera test failed"}
                            </p>
                            <p className="text-muted-foreground">
                              {onvifTestResult.connected
                                ? `${formatResolution(onvifTestResult)} at ${(onvifTestResult.fps ?? 0).toFixed(1)} FPS via ${onvifTestResult.transport.toUpperCase()}.`
                                : onvifTestResult.error ?? "The backend could not validate this ONVIF camera."}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {onvifTestResult.stream_count} resolved stream{onvifTestResult.stream_count === 1 ? "" : "s"}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Resolve streams to inspect available RTSP URLs, then run the ONVIF camera test before continuing.
                      </p>
                    )}
                  </div>
                </TabsContent>
              </Tabs>

              <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                {sourceMode === "file"
                  ? "Step 1 uploads the source file into the backend workflow. Step 2 lets you draw the queue polygon on the video frame. Step 3 selects the model size."
                  : sourceMode === "rtsp"
                    ? "Manual RTSP now mirrors the GUI preflight workflow: provide credentials, choose transport, validate the stream, capture a camera snapshot, define the queue polygon, then continue to model selection."
                    : "ONVIF onboarding now covers device discovery, stream resolution, backend camera testing, and snapshot-based zone selection before model choice."}
              </div>

              {(stagedFeeds.length > 0 || allSelectedLocalFiles.length > 0) && (
                <div className="space-y-3 rounded-xl border border-border bg-background/40 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">Configured sources</p>
                      <p className="text-xs text-muted-foreground">These are the sources currently prepared for zone tracing, model assignment, and review.</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{stagedSourceCount} prepared</Badge>
                      <Badge variant="outline">{remainingSourceCount} remaining</Badge>
                    </div>
                  </div>

                  <div className="grid gap-2">
                    {stagedFeeds.map((draft) => {
                      const item = toReviewLaunchItem(draft);
                      return (
                        <div key={draft.clientId} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                          <div className="min-w-0 space-y-1">
                            <p className="text-sm font-medium text-foreground">{item.feedName}</p>
                            <p className="truncate text-xs text-muted-foreground">{item.sourceLabel}</p>
                          </div>
                          <Badge variant="outline">{item.sourceMode === "file" ? "Video" : item.sourceMode === "onvif" ? "ONVIF" : "RTSP"}</Badge>
                        </div>
                      );
                    })}
                    {preparedLocalFileDrafts.map((draft) => (
                      <div key={draft.clientId} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                        <div className="min-w-0 space-y-1">
                          <p className="text-sm font-medium text-foreground">{draft.feedName}</p>
                          <p className="truncate text-xs text-muted-foreground">{draft.uploadedFile?.name ?? "Selected local video"}</p>
                        </div>
                        <Badge variant="outline">YOLO {draft.modelSize.toUpperCase()}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <DialogFooter>
                <Button onClick={resetSetupFlow} type="button" variant="outline">
                  Cancel
                </Button>
                <Button disabled={!canContinueSourceStep || isTestingCameraSource} type="submit">
                  Continue to Zone
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        <ZoneSelectionDialog
          feedName={feedName}
          file={uploadedFile}
          fileOptions={localZoneVideoOptions}
          loadPreviewFrame={sourceMode === "file" ? null : buildSnapshotLoader}
          onBack={() => setSetupStep("source")}
          onContinue={() => setSetupStep("model")}
          onOpenChange={handleDialogOpenChange}
          onPointsChange={setZonePoints}
          onSelectedFileChange={handleSelectZoneVideo}
          open={setupStep === "zone"}
          points={zonePoints}
          selectedFileKey={selectedLocalZoneVideoKey}
          metadataContent={
            <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Store metadata</p>
                  <p className="text-xs text-muted-foreground">
                    Metadata is saved per selected source. Switching videos or streams restores that source's establishment and caisse.
                  </p>
                </div>
                {selectedCaisse?.zone && <Badge variant="outline">Saved caisse zone available</Badge>}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Label className="text-foreground">Establishment</Label>
                    <Button onClick={() => setIsCreateEstablishmentDialogOpen(true)} size="sm" type="button" variant="outline">
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      New
                    </Button>
                  </div>
                  <Select
                    onValueChange={handleEstablishmentChange}
                    value={selectedEstablishmentId !== null ? String(selectedEstablishmentId) : UNASSIGNED_SELECT_VALUE}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={establishmentsQuery.isLoading ? "Loading establishments..." : "Select an establishment"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={UNASSIGNED_SELECT_VALUE}>No establishment</SelectItem>
                      {establishments.map((establishment) => (
                        <SelectItem key={establishment.id} value={String(establishment.id)}>
                          {establishment.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {establishmentsQuery.isError && <p className="text-xs text-destructive">Failed to load establishments.</p>}
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Label className="text-foreground">Caisse</Label>
                    <Button
                      onClick={() => setIsCreateCaisseDialogOpen(true)}
                      size="sm"
                      type="button"
                      variant="outline"
                      disabled={selectedEstablishmentId === null}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      New
                    </Button>
                  </div>
                  <Select
                    onValueChange={handleCaisseChange}
                    value={selectedCaisseId !== null ? String(selectedCaisseId) : UNASSIGNED_SELECT_VALUE}
                    disabled={selectedEstablishmentId === null || caissesQuery.isLoading}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          selectedEstablishmentId === null
                            ? "Select an establishment first"
                            : caissesQuery.isLoading
                              ? "Loading caisses..."
                              : "Select a caisse"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={UNASSIGNED_SELECT_VALUE}>No caisse</SelectItem>
                      {caisses.map((caisse) => (
                        <SelectItem key={caisse.id} value={String(caisse.id)}>
                          {caisse.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedEstablishmentId !== null && !caissesQuery.isLoading && caisses.length === 0 && (
                    <p className="text-xs text-muted-foreground">No caisses yet for this establishment.</p>
                  )}
                  {caissesQuery.isError && <p className="text-xs text-destructive">Failed to load caisses for the selected establishment.</p>}
                </div>
              </div>

              <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                {selectedCaisse?.zone
                  ? "This caisse already has a saved zone. The current source can reuse it until you edit the zone." 
                  : "Metadata is optional, but selecting it now links this source to the SQLite hierarchy and lets saved caisse zones be reused when they exist."}
              </div>
            </div>
          }
          sourceKind={sourceMode === "file" ? "Selected file" : sourceMode === "onvif" ? "ONVIF snapshot" : "RTSP preview"}
          sourceLabel={
            sourceMode === "file"
              ? uploadedFile?.name ?? "No file selected"
              : sourceMode === "onvif"
                ? selectedOnvifDevice
                  ? `${selectedOnvifDevice.name} (${selectedOnvifDevice.ip})`
                  : feedSource
                : feedSource
          }
        />

        <ZoneSelectionDialog
          backLabel="Cancel"
          continueLabel={isSavingEditedZone ? "Saving..." : "Save Zone"}
          feedName={editingFeedZone?.name ?? "Selected feed"}
          file={null}
          helperText="A fresh preview frame is captured from the stored feed source. Adjust the polygon and save the updated queue zone."
          isContinuing={isSavingEditedZone}
          loadPreviewFrame={loadExistingFeedSnapshot}
          onBack={closeFeedZoneEditor}
          onContinue={() => void handleSaveEditedZone()}
          onOpenChange={(open) => {
            if (!open) {
              closeFeedZoneEditor();
            }
          }}
          onPointsChange={setEditingZonePoints}
          open={editingFeedZone !== null}
          points={editingZonePoints}
          sourceKind="Existing feed"
          sourceLabel={editingFeedZone?.source ?? "Feed preview"}
        />

        <ModelSelectionDialog
          caisseName={selectedCaisse?.name ?? null}
          establishmentName={selectedEstablishment?.name ?? null}
          feedName={feedName}
          isSubmitting={false}
          onBack={() => setSetupStep("zone")}
          onConfirm={() => setSetupStep("review")}
          onModelChange={setSelectedModel}
          onSelectedSourceChange={sourceMode === "file" ? handleSelectZoneVideo : undefined}
          onOpenChange={handleDialogOpenChange}
          open={setupStep === "model"}
          selectedModel={selectedModel}
          selectedSourceKey={sourceMode === "file" ? selectedLocalZoneVideoKey : undefined}
          sourceOptions={sourceMode === "file" ? localZoneVideoOptions : []}
          sourceMode={sourceMode}
          zonePointCount={zonePoints.length}
        />

        <ReviewLaunchDialog
          canSubmitBatch={canSubmitBatch}
          isSubmitting={isReviewSubmitting}
          items={reviewItems}
          logLevel={batchLogLevel}
          onBack={() => setSetupStep(currentReviewDraft ? "model" : "source")}
          onEditItem={handleEditStagedFeed}
          onLaunch={() => void handleFinalizeBatch(true)}
          onLogLevelChange={setBatchLogLevel}
          onOpenChange={handleDialogOpenChange}
          onRemoveItem={handleRemoveStagedFeed}
          onSave={() => void handleFinalizeBatch(false)}
          onStageCurrent={() => void handleStageCurrentDraft()}
          onWebhookEnabledChange={setBatchWebhookEnabled}
          open={setupStep === "review"}
          stageButtonLabel="Add Current Source"
          targetSourceCount={parsedTargetSourceCount}
          webhookEnabled={batchWebhookEnabled}
        />

        <AlertDialog open={feedPendingDeletion !== null} onOpenChange={(open) => {
          if (!open) {
            setFeedPendingDeletion(null);
          }
        }}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Remove Feed</AlertDialogTitle>
              <AlertDialogDescription>
                {feedPendingDeletion
                  ? `Remove ${feedPendingDeletion.name} from the dashboard and backend registry? This stops using the source until you add it again.`
                  : "Remove this feed from the dashboard and backend registry?"}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={activeFeedAction?.action === "delete"}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => void handleConfirmDeleteFeed()} disabled={activeFeedAction?.action === "delete"}>
                {activeFeedAction?.action === "delete" ? "Removing..." : "Remove Feed"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <Dialog open={isCreateEstablishmentDialogOpen} onOpenChange={setIsCreateEstablishmentDialogOpen}>
          <DialogContent className="border-border bg-card sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-foreground">Create Establishment</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Add a new establishment so the feed can be grouped under the same store hierarchy used by the desktop GUI.
              </DialogDescription>
            </DialogHeader>

            <form className="space-y-4" onSubmit={handleCreateEstablishment}>
              <div className="space-y-2">
                <Label className="text-foreground" htmlFor="new-establishment-name">
                  Establishment name
                </Label>
                <Input
                  id="new-establishment-name"
                  onChange={(event) => setNewEstablishmentName(event.target.value)}
                  placeholder="Store Alpha"
                  value={newEstablishmentName}
                />
              </div>

              <DialogFooter>
                <Button onClick={() => setIsCreateEstablishmentDialogOpen(false)} type="button" variant="outline">
                  Cancel
                </Button>
                <Button disabled={isSavingMetadata} type="submit">
                  {createEstablishmentMutation.isPending ? "Saving..." : "Create Establishment"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        <Dialog open={isCreateCaisseDialogOpen} onOpenChange={setIsCreateCaisseDialogOpen}>
          <DialogContent className="border-border bg-card sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-foreground">Create Caisse</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Add a caisse under the selected establishment. Existing saved zones for that caisse can then be reused by new feeds.
              </DialogDescription>
            </DialogHeader>

            <form className="space-y-4" onSubmit={handleCreateCaisse}>
              <div className="space-y-2">
                <Label className="text-foreground">Establishment</Label>
                <div className="rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-muted-foreground">
                  {selectedEstablishment?.name ?? "No establishment selected"}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-foreground" htmlFor="new-caisse-name">
                  Caisse name
                </Label>
                <Input
                  id="new-caisse-name"
                  onChange={(event) => setNewCaisseName(event.target.value)}
                  placeholder="Register 1"
                  value={newCaisseName}
                />
              </div>

              <DialogFooter>
                <Button onClick={() => setIsCreateCaisseDialogOpen(false)} type="button" variant="outline">
                  Cancel
                </Button>
                <Button disabled={selectedEstablishmentId === null || isSavingMetadata} type="submit">
                  {createCaisseMutation.isPending ? "Saving..." : "Create Caisse"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}