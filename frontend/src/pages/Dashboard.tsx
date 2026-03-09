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
import { ReviewLaunchDialog } from "@/components/dashboard/ReviewLaunchDialog";
import { ZoneSelectionDialog } from "@/components/dashboard/ZoneSelectionDialog";
import { AppLayout } from "@/components/layout/AppLayout";
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
  Caisse,
  Establishment,
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
type FeedAction = "start" | "stop" | "restart";

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

function getFileLabel(file: File | null): string {
  if (!file) {
    return "No video selected yet";
  }
  const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
  return `${file.name} (${sizeMb} MB)`;
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
  const [feedName, setFeedName] = useState("");
  const [feedSource, setFeedSource] = useState("");
  const [sourceMode, setSourceMode] = useState<SourceMode>("file");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [zonePoints, setZonePoints] = useState<ZonePoint[]>([]);
  const [editingFeedZone, setEditingFeedZone] = useState<VideoFeed | null>(null);
  const [editingZonePoints, setEditingZonePoints] = useState<ZonePoint[]>([]);
  const [isSavingEditedZone, setIsSavingEditedZone] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelSize>("n");
  const [isFinalizingSetup, setIsFinalizingSetup] = useState(false);
  const [activeFeedAction, setActiveFeedAction] = useState<{ feedId: string; action: FeedAction } | null>(null);
  const [selectedEstablishmentId, setSelectedEstablishmentId] = useState<number | null>(null);
  const [selectedCaisseId, setSelectedCaisseId] = useState<number | null>(null);
  const [isCreateEstablishmentDialogOpen, setIsCreateEstablishmentDialogOpen] = useState(false);
  const [isCreateCaisseDialogOpen, setIsCreateCaisseDialogOpen] = useState(false);
  const [newEstablishmentName, setNewEstablishmentName] = useState("");
  const [newCaisseName, setNewCaisseName] = useState("");
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
    createFeedMutation,
    updateZoneMutation,
    startFeedMutation,
    stopFeedMutation,
    restartFeedMutation,
    activity,
    derived,
  } = useLiveDashboard();
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
  const establishments = establishmentsQuery.data ?? [];
  const caisses = caissesQuery.data ?? [];
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

  const isSavingSetup = isFinalizingSetup || createFeedMutation.isPending || updateZoneMutation.isPending;
  const isReviewSubmitting = isSavingSetup || startFeedMutation.isPending;
  const isTestingCameraSource = isTestingRtsp || isDiscoveringOnvif || isResolvingOnvifStreams || isTestingOnvif;
  const isSavingMetadata = createEstablishmentMutation.isPending || createCaisseMutation.isPending;

  useEffect(() => {
    if (setupStep === null || zonePoints.length > 0 || !selectedCaisse?.zone?.points?.length) {
      return;
    }

    setZonePoints(selectedCaisse.zone.points);
  }, [selectedCaisse, setupStep, zonePoints.length]);

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

  const resetRtspState = () => {
    setRtspUsername("");
    setRtspPassword("");
    setRtspTransport("tcp");
    setRtspTestResult(null);
    setIsTestingRtsp(false);
  };

  const resetOnvifState = () => {
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
  };

  const resetSetupFlow = () => {
    setSetupStep(null);
    setFeedName("");
    setFeedSource("");
    setSourceMode("file");
    setUploadedFile(null);
    setZonePoints([]);
    setSelectedModel("n");
    setIsFinalizingSetup(false);
    setSelectedEstablishmentId(null);
    setSelectedCaisseId(null);
    setIsCreateEstablishmentDialogOpen(false);
    setIsCreateCaisseDialogOpen(false);
    setNewEstablishmentName("");
    setNewCaisseName("");
    resetRtspState();
    resetOnvifState();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
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

  const handleSourceModeChange = (mode: SourceMode) => {
    setSourceMode(mode);
    setFeedSource("");
    if (mode !== "file") {
      setUploadedFile(null);
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

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setUploadedFile(file);
    setZonePoints([]);

    if (file && !feedName.trim()) {
      setFeedName(file.name.replace(/\.[^.]+$/, ""));
    }
  };

  const handleSourceStepSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

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

  const handleFinalizeFeed = async (launchAfterCreate: boolean) => {
    setIsFinalizingSetup(true);

    let createdFeed: VideoFeed | null = null;

    try {
      let source = feedSource.trim();

      const createFeedInput: Parameters<typeof createFeedMutation.mutateAsync>[0] = {
        name: feedName.trim(),
        source,
        model_size: selectedModel,
        establishment_id: selectedEstablishmentId,
        caisse_id: selectedCaisseId,
      };

      if (sourceMode === "file") {
        if (!uploadedFile) {
          throw new Error("Choose a video file before creating the feed.");
        }

        const upload = await uploadVideo(uploadedFile);
        source = upload.file_path;
        createFeedInput.source = source;
      } else if (sourceMode === "rtsp") {
        createFeedInput.source = feedSource.trim();
        createFeedInput.rtsp_username = rtspUsername.trim() || null;
        createFeedInput.rtsp_password = rtspPassword.trim() || null;
        createFeedInput.rtsp_transport = rtspTransport;
      } else {
        createFeedInput.source = feedSource.trim();
        createFeedInput.rtsp_username = onvifUsername.trim() || null;
        createFeedInput.rtsp_password = onvifPassword.trim() || null;
        createFeedInput.rtsp_transport = onvifTransport;
      }

      const feed = await createFeedMutation.mutateAsync(createFeedInput);
      createdFeed = feed;

      if (zonePoints.length >= 3) {
        await updateZoneMutation.mutateAsync({
          feedId: feed.feed_id,
          zone: { points: zonePoints },
        });
      }

      if (launchAfterCreate) {
        await startFeedMutation.mutateAsync(feed.feed_id);
      }

      toast.success(
        launchAfterCreate
          ? sourceMode === "file"
            ? "Feed created, zone saved, and worker started."
            : sourceMode === "onvif"
              ? "ONVIF feed created and started from the review step."
              : "RTSP feed created and started from the review step."
          : sourceMode === "file"
            ? "Feed created with its uploaded video, queue zone, and selected model."
            : sourceMode === "onvif"
              ? "Feed created from the discovered ONVIF camera and selected model."
              : "Feed created with the tested RTSP camera and selected model.",
      );
      resetSetupFlow();
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Failed to complete the feed workflow.";

      if (createdFeed) {
        toast.error(
          launchAfterCreate
            ? `Feed was created, but the automatic launch failed: ${reason}`
            : `Feed was created, but follow-up setup failed: ${reason}`,
        );
        resetSetupFlow();
      } else {
        toast.error(reason);
      }
    } finally {
      setIsFinalizingSetup(false);
    }
  };

  const handleFeedAction = async (feed: VideoFeed, action: FeedAction) => {
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
              Add Feed
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
            title="Average Wait"
            value={formatWaitTime(derived.averageWaitTime)}
            icon={Clock}
            subtitle={systemHealth ? `API ${systemHealth.status}` : "No API heartbeat yet"}
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
                            <p className="max-w-[12rem] truncate">{feed.last_error ?? "No runtime error"}</p>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
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
                          {feed.status === "initializing" && (
                            <span className="text-xs text-muted-foreground">Worker is initializing...</span>
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

          <div className="space-y-3">
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
                  className="rounded-lg border border-border bg-card p-3 text-sm transition-all hover:bg-accent/50"
                >
                  <p className="text-xs leading-relaxed text-foreground">{alert.message}</p>
                  <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">{alert.time}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <Dialog open={setupStep === "source"} onOpenChange={handleDialogOpenChange}>
          <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle className="text-foreground">Add Feed</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Start with the source. The dashboard now supports the GUI-style camera preflight flow for manual RTSP and ONVIF discovery, while uploaded videos still go through zone selection before model choice.
              </DialogDescription>
            </DialogHeader>

            <form className="space-y-4" onSubmit={handleSourceStepSubmit}>
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
                      onChange={handleFileChange}
                      ref={fileInputRef}
                      type="file"
                    />

                    <div className="flex flex-wrap items-center gap-3">
                      <Button onClick={() => fileInputRef.current?.click()} type="button" variant="outline">
                        <Upload className="mr-2 h-4 w-4" />
                        Choose Video
                      </Button>
                      <span className="text-sm text-muted-foreground">{getFileLabel(uploadedFile)}</span>
                    </div>
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

              <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">Store metadata</p>
                    <p className="text-xs text-muted-foreground">
                      Assign an establishment and caisse now so the feed is linked to the same hierarchy used in the desktop workflow.
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
                    {establishmentsQuery.isError && (
                      <p className="text-xs text-destructive">Failed to load establishments.</p>
                    )}
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
                    {caissesQuery.isError && (
                      <p className="text-xs text-destructive">Failed to load caisses for the selected establishment.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                  {selectedCaisse?.zone
                    ? "This caisse already has a saved zone. Camera feeds created with this selection will automatically reuse it until you edit the zone later."
                    : "Metadata is optional, but selecting it now links the feed to the SQLite hierarchy and lets saved caisse zones be reused when they exist."}
                </div>
              </div>

              <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                {sourceMode === "file"
                  ? "Step 1 uploads the source file into the backend workflow. Step 2 lets you draw the queue polygon on the video frame. Step 3 selects the model size."
                  : sourceMode === "rtsp"
                    ? "Manual RTSP now mirrors the GUI preflight workflow: provide credentials, choose transport, validate the stream, capture a camera snapshot, define the queue polygon, then continue to model selection."
                    : "ONVIF onboarding now covers device discovery, stream resolution, backend camera testing, and snapshot-based zone selection before model choice."}
              </div>

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
          loadPreviewFrame={sourceMode === "file" ? null : buildSnapshotLoader}
          onBack={() => setSetupStep("source")}
          onContinue={() => setSetupStep("model")}
          onOpenChange={handleDialogOpenChange}
          onPointsChange={setZonePoints}
          open={setupStep === "zone"}
          points={zonePoints}
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
          onOpenChange={handleDialogOpenChange}
          open={setupStep === "model"}
          selectedModel={selectedModel}
          sourceMode={sourceMode}
          zonePointCount={zonePoints.length}
        />

        <ReviewLaunchDialog
          caisseName={selectedCaisse?.name ?? null}
          establishmentName={selectedEstablishment?.name ?? null}
          feedName={feedName}
          hasSavedCaisseZone={Boolean(selectedCaisse?.zone)}
          isSubmitting={isReviewSubmitting}
          modelSize={selectedModel}
          onBack={() => setSetupStep("model")}
          onLaunch={() => void handleFinalizeFeed(true)}
          onOpenChange={handleDialogOpenChange}
          onSave={() => void handleFinalizeFeed(false)}
          open={setupStep === "review"}
          sourceDetail={reviewSourceDetail}
          sourceLabel={reviewSourceLabel}
          sourceMode={sourceMode}
          zonePointCount={zonePoints.length}
        />

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