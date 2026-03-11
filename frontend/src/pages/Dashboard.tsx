import { FormEvent, useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Radio,
  Search,
  Upload,
  Video,
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

import { ActivityPanel } from "@/components/dashboard/ActivityPanel";
import { AttentionPanel } from "@/components/dashboard/AttentionPanel";
import { FeedDeleteDialog } from "@/components/dashboard/FeedDeleteDialog";
import { FeedGrid, type FeedGridAction } from "@/components/dashboard/FeedGrid";
import { DashboardSetupDialogs } from "@/components/dashboard/DashboardSetupDialogs";
import type { ReviewLaunchItem } from "@/components/dashboard/ReviewLaunchDialog";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { useDashboardLocalFiles } from "@/hooks/use-dashboard-local-files";
import { useDashboardBatchSubmission } from "@/hooks/use-dashboard-batch-submission";
import { useDashboardSourceOnboarding } from "@/hooks/use-dashboard-source-onboarding";
import { useDashboardSetupEffects } from "@/hooks/use-dashboard-setup-effects";
import { useDashboardSetupState } from "@/hooks/use-dashboard-setup-state";
import { useLiveDashboard } from "@/hooks/use-live-dashboard";
import type {
  Caisse,
  Establishment,
  ONVIFDevice,
  RTSPSnapshotResult,
  RTSPTransport,
  VideoFeed,
  ZonePoint,
} from "@/lib/api";
import {
  createCaisse,
  createEstablishment,
  getFeedSnapshot,
  launchFeedBatch,
  listCaisses,
  listEstablishments,
} from "@/lib/api";
import {
  createDraftId,
  DEFAULT_ONVIF_TIMEOUT,
  type FeedAction,
  formatResolution,
  getDraftSourceDetail,
  getDraftSourceLabel,
  getOnvifDeviceKey,
  type SourceMode,
  type StagedFeedDraft,
} from "@/lib/dashboard-setup";

const UNASSIGNED_SELECT_VALUE = "__unassigned__";

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

const LOCAL_FILE_DRAFT_PREFIX = "local-file-draft:";

function createLocalFileDraftId(file: File): string {
  return `${LOCAL_FILE_DRAFT_PREFIX}${getLocalFileKey(file)}`;
}

function isLocalFileDraftId(clientId: string): boolean {
  return clientId.startsWith(LOCAL_FILE_DRAFT_PREFIX);
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

export default function Dashboard() {
  const queryClient = useQueryClient();
  const [editingFeedZone, setEditingFeedZone] = useState<VideoFeed | null>(null);
  const [editingZonePoints, setEditingZonePoints] = useState<ZonePoint[]>([]);
  const [isSavingEditedZone, setIsSavingEditedZone] = useState(false);
  const [feedPendingDeletion, setFeedPendingDeletion] = useState<VideoFeed | null>(null);
  const [activeFeedAction, setActiveFeedAction] = useState<{ feedId: string; action: FeedAction } | null>(null);

  const {
    queuedLocalFiles,
    localFileConfigs,
    setQueuedLocalFiles,
    mergeLocalFileConfig,
    removeLocalFile,
    resetLocalFiles,
  } = useDashboardLocalFiles({ getFileKey: getLocalFileKey });

  const getStoredLocalFileConfig = useCallback(
    (file: File | null) => {
      if (!file) {
        return undefined;
      }

      return localFileConfigs[getLocalFileKey(file)];
    },
    [localFileConfigs],
  );

  const {
    setupStep,
    setSetupStep,
    targetSourceCount,
    setTargetSourceCount,
    targetSourceCountValue,
    stagedFeeds,
    setStagedFeeds,
    currentDraftId,
    setCurrentDraftId,
    feedName,
    setFeedName,
    feedSource,
    setFeedSource,
    sourceMode,
    setSourceMode,
    uploadedFile,
    setUploadedFile,
    zonePoints,
    setZonePoints,
    selectedModel,
    setSelectedModel,
    isFinalizingSetup,
    setIsFinalizingSetup,
    selectedEstablishmentId,
    setSelectedEstablishmentId,
    selectedCaisseId,
    setSelectedCaisseId,
    isCreateEstablishmentDialogOpen,
    setIsCreateEstablishmentDialogOpen,
    isCreateCaisseDialogOpen,
    setIsCreateCaisseDialogOpen,
    newEstablishmentName,
    setNewEstablishmentName,
    newCaisseName,
    setNewCaisseName,
    batchLogLevel,
    setBatchLogLevel,
    batchWebhookEnabled,
    setBatchWebhookEnabled,
    rtspUsername,
    setRtspUsername,
    rtspPassword,
    setRtspPassword,
    rtspTransport,
    setRtspTransport,
    rtspTestResult,
    setRtspTestResult,
    isTestingRtsp,
    setIsTestingRtsp,
    onvifTimeout,
    setOnvifTimeout,
    onvifUsername,
    setOnvifUsername,
    onvifPassword,
    setOnvifPassword,
    onvifTransport,
    setOnvifTransport,
    onvifDevices,
    setOnvifDevices,
    selectedOnvifDevice,
    selectedOnvifDeviceKey,
    setSelectedOnvifDeviceKey,
    onvifStreams,
    setOnvifStreams,
    onvifTestResult,
    setOnvifTestResult,
    isDiscoveringOnvif,
    setIsDiscoveringOnvif,
    isResolvingOnvifStreams,
    setIsResolvingOnvifStreams,
    isTestingOnvif,
    setIsTestingOnvif,
    isTestingCameraSource,
    canContinueSourceStep,
    fileInputRef,
    resetRtspState,
    resetOnvifState,
    resetCurrentDraft,
    resetSetupFlow,
  } = useDashboardSetupState({
    getStoredLocalFileConfig,
    setQueuedLocalFiles,
    resetLocalFiles,
  });

  const {
    handleSourceModeChange,
    buildSnapshotLoader,
    handleTestRtsp,
    handleDiscoverOnvif,
    handleSelectOnvifDevice,
    handleResolveOnvifStreams,
    handleTestOnvif,
  } = useDashboardSourceOnboarding({
    sourceMode,
    setSourceMode,
    feedSource,
    setFeedSource,
    feedName,
    setFeedName,
    uploadedFile,
    setUploadedFile,
    setQueuedLocalFiles,
    setZonePoints,
    fileInputRef,
    resetRtspState,
    resetOnvifState,
    rtspUsername,
    rtspPassword,
    rtspTransport,
    setRtspTestResult,
    setIsTestingRtsp,
    onvifTimeout,
    onvifUsername,
    onvifPassword,
    onvifTransport,
    setOnvifDevices,
    selectedOnvifDevice,
    setSelectedOnvifDeviceKey,
    setOnvifStreams,
    setOnvifTestResult,
    setIsDiscoveringOnvif,
    setIsResolvingOnvifStreams,
    setIsTestingOnvif,
  });

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
  const selectedEstablishment = useMemo<Establishment | null>(
    () => establishments.find((establishment) => establishment.id === selectedEstablishmentId) ?? null,
    [establishments, selectedEstablishmentId],
  );
  const selectedCaisse = useMemo<Caisse | null>(
    () => caisses.find((caisse) => caisse.id === selectedCaisseId) ?? null,
    [caisses, selectedCaisseId],
  );
  const applyLocalFileSelection = useCallback((file: File | null) => {
    if (!file) {
      setFeedName("");
      setZonePoints([]);
      setSelectedModel("n");
      setSelectedEstablishmentId(null);
      setSelectedCaisseId(null);
      return;
    }

    const storedConfig = getStoredLocalFileConfig(file);
    setFeedName(storedConfig?.feedName ?? getSuggestedFeedNameFromFile(file));
    setZonePoints(storedConfig?.zonePoints ?? []);
    setSelectedModel(storedConfig?.modelSize ?? "n");
    setSelectedEstablishmentId(storedConfig?.establishmentId ?? null);
    setSelectedCaisseId(storedConfig?.caisseId ?? null);
  }, [getStoredLocalFileConfig, setFeedName, setSelectedCaisseId, setSelectedEstablishmentId, setSelectedModel, setZonePoints]);

  const isSavingSetup = isFinalizingSetup || batchLaunchMutation.isPending || updateZoneMutation.isPending;
  const isReviewSubmitting = isSavingSetup;
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

  useDashboardSetupEffects({
    setupStep,
    zonePoints,
    selectedCaisse,
    setZonePoints,
    sourceMode,
    uploadedFile,
    getLocalFileKey,
    mergeLocalFileConfig,
    feedName,
    selectedModel,
    selectedEstablishmentId,
    selectedCaisseId,
    caisses,
    isLoadingCaisses: caissesQuery.isLoading,
    setSelectedCaisseId,
  });

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
            const storedConfig = localFileConfigs[fileKey] ?? {};
            return {
              clientId: createLocalFileDraftId(file),
              feedName: storedConfig.feedName?.trim() || getSuggestedFeedNameFromFile(file),
              sourceMode: "file" as const,
              source: "",
              uploadedFile: file,
              zonePoints: storedConfig.zonePoints ?? [],
              modelSize: storedConfig.modelSize ?? "n",
              establishmentId: storedConfig.establishmentId ?? null,
              establishmentName:
                establishments.find((establishment) => establishment.id === (storedConfig.establishmentId ?? null))?.name ?? null,
              caisseId: storedConfig.caisseId ?? null,
              caisseName: caisses.find((caisse) => caisse.id === (storedConfig.caisseId ?? null))?.name ?? null,
              hasSavedCaisseZone: Boolean(caisses.find((caisse) => caisse.id === (storedConfig.caisseId ?? null))?.zone),
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
      localFileConfigs,
      sourceMode,
    ],
  );

  const currentReviewDraft = useMemo(
    () => (setupStep === "review" && sourceMode !== "file" ? buildCurrentDraft() : null),
    [buildCurrentDraft, setupStep, sourceMode],
  );
  const { handleFinalizeBatch } = useDashboardBatchSubmission({
    stagedFeeds,
    preparedLocalFileDrafts,
    currentReviewDraft,
    targetSourceCountValue,
    batchLogLevel,
    batchWebhookEnabled,
    allSelectedLocalFiles,
    setStagedFeeds,
    setUploadedFile,
    setQueuedLocalFiles,
    applyLocalFileSelection,
    setCurrentDraftId,
    setSetupStep,
    setIsFinalizingSetup,
    resetSetupFlow,
    createLocalFileDraftId,
    isLocalFileDraftId,
    submitBatch: batchLaunchMutation.mutateAsync,
  });

  const reviewItems = useMemo(
    () => [
      ...stagedFeeds.map((draft) => toReviewLaunchItem(draft)),
      ...(setupStep === "review" ? preparedLocalFileDrafts.map((draft) => toReviewLaunchItem(draft)) : []),
      ...(currentReviewDraft ? [toReviewLaunchItem(currentReviewDraft, true)] : []),
    ],
    [currentReviewDraft, preparedLocalFileDrafts, setupStep, stagedFeeds],
  );
  const stagedSourceSummaries = useMemo(
    () => stagedFeeds.map((draft) => ({
      clientId: draft.clientId,
      feedName: draft.feedName,
      sourceLabel: getDraftSourceLabel(draft),
      sourceMode: draft.sourceMode,
    })),
    [stagedFeeds],
  );

  const preparedSourceCount = stagedFeeds.length + preparedLocalFileDrafts.length + (currentReviewDraft ? 1 : 0);
  const remainingSourceSlots = Math.max(targetSourceCountValue - preparedSourceCount, 0);
  const canSubmitBatch = preparedSourceCount === targetSourceCountValue;

  const closeFeedZoneEditor = useCallback(() => {
    setEditingFeedZone(null);
    setEditingZonePoints([]);
    setIsSavingEditedZone(false);
  }, []);

  const handleDialogOpenChange = useCallback((open: boolean) => {
    if (!open) {
      resetSetupFlow();
    }
  }, [resetSetupFlow]);

  const loadDraftIntoEditor = useCallback((draft: StagedFeedDraft) => {
    setCurrentDraftId(draft.clientId);
    setFeedName(draft.feedName);
    setSourceMode(draft.sourceMode);
    setFeedSource(draft.source);
    setUploadedFile(draft.uploadedFile);
    if (draft.sourceMode === "file" && draft.uploadedFile) {
      mergeLocalFileConfig(getLocalFileKey(draft.uploadedFile), {
        feedName: draft.feedName,
        modelSize: draft.modelSize,
        establishmentId: draft.establishmentId,
        caisseId: draft.caisseId,
        zonePoints: draft.zonePoints,
      });
    }
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
  }, [
    mergeLocalFileConfig,
    setCurrentDraftId,
    setFeedName,
    setFeedSource,
    setOnvifDevices,
    setOnvifPassword,
    setOnvifStreams,
    setOnvifTestResult,
    setOnvifTimeout,
    setOnvifTransport,
    setOnvifUsername,
    setQueuedLocalFiles,
    setRtspPassword,
    setRtspTestResult,
    setRtspTransport,
    setRtspUsername,
    setSelectedCaisseId,
    setSelectedEstablishmentId,
    setSelectedModel,
    setSelectedOnvifDeviceKey,
    setSetupStep,
    setSourceMode,
    setUploadedFile,
    setZonePoints,
    sourceMode,
    uploadedFile,
  ]);

  const handleEditStagedFeed = useCallback((clientId: string) => {
    if (isLocalFileDraftId(clientId)) {
      const draftFile = allSelectedLocalFiles.find((file) => createLocalFileDraftId(file) === clientId);
      if (!draftFile) {
        return;
      }

      const remainingFiles = allSelectedLocalFiles.filter((file) => createLocalFileDraftId(file) !== clientId);
      setUploadedFile(draftFile);
      setQueuedLocalFiles(remainingFiles);
      applyLocalFileSelection(draftFile);
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
  }, [
    allSelectedLocalFiles,
    applyLocalFileSelection,
    loadDraftIntoEditor,
    setCurrentDraftId,
    setQueuedLocalFiles,
    setSetupStep,
    setSourceMode,
    setStagedFeeds,
    setUploadedFile,
    stagedFeeds,
  ]);

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
      applyLocalFileSelection(nextActiveFile);
      return;
    }

    setStagedFeeds((current) => current.filter((item) => item.clientId !== clientId));
  }, [allSelectedLocalFiles, applyLocalFileSelection, setQueuedLocalFiles, setStagedFeeds, setUploadedFile, uploadedFile]);

  const handleEstablishmentChange = useCallback((value: string) => {
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
  }, [setSelectedCaisseId, setSelectedEstablishmentId]);

  const handleCaisseChange = useCallback((value: string) => {
    if (value === UNASSIGNED_SELECT_VALUE) {
      setSelectedCaisseId(null);
      return;
    }

    const nextId = Number.parseInt(value, 10);
    if (Number.isNaN(nextId)) {
      return;
    }

    setSelectedCaisseId(nextId);
  }, [setSelectedCaisseId]);

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
    removeLocalFile(fileKey);
  }, [removeLocalFile]);

  const handleActivateQueuedLocalFile = useCallback((fileKey: string) => {
    setQueuedLocalFiles((current) => {
      const nextFile = current.find((file) => getLocalFileKey(file) === fileKey) ?? null;
      if (!nextFile) {
        return current;
      }

      const remainingFiles = current.filter((file) => getLocalFileKey(file) !== fileKey);
      const nextQueue = uploadedFile ? dedupeLocalFiles([uploadedFile, ...remainingFiles], [getLocalFileKey(nextFile)]) : remainingFiles;

      setUploadedFile(nextFile);
      applyLocalFileSelection(nextFile);
      setCurrentDraftId(createDraftId());

      return nextQueue;
    });
  }, [applyLocalFileSelection, setCurrentDraftId, setQueuedLocalFiles, setUploadedFile, uploadedFile]);

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
      const storedConfig = getStoredLocalFileConfig(nextUploadedFile);
      setZonePoints(storedConfig?.zonePoints ?? []);
      setSelectedModel(storedConfig?.modelSize ?? "n");
      setSelectedEstablishmentId(storedConfig?.establishmentId ?? null);
      setSelectedCaisseId(storedConfig?.caisseId ?? null);
      if (nextUploadedFile) {
        setFeedName(storedConfig?.feedName ?? (feedName.trim() || getSuggestedFeedNameFromFile(nextUploadedFile)));
      }
    }

    setQueuedLocalFiles(nextQueuedLocalFiles);

    const preparedSourceCount = stagedFeeds.length + (nextUploadedFile ? 1 : 0) + nextQueuedLocalFiles.length;
    if (preparedSourceCount > targetSourceCountValue) {
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

    if (stagedFeeds.length >= targetSourceCountValue) {
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
    if (nextCount > targetSourceCountValue) {
      toast.error(`This batch is configured for ${targetSourceCountValue} source${targetSourceCountValue === 1 ? "" : "s"}. Remove a staged item or increase the target count first.`);
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
    setSetupStep(nextCount >= targetSourceCountValue ? "review" : "source");
    toast.success(`${draft.feedName} added to the staged batch.`);
  }, [buildCurrentDraft, queuedLocalFiles, resetCurrentDraft, setSetupStep, setStagedFeeds, stagedFeeds.length, targetSourceCountValue]);

  const handleOpenBatchReview = useCallback(() => {
    if (stagedFeeds.length === 0) {
      toast.error("Stage at least one source before opening the batch review.");
      return;
    }

    resetCurrentDraft({ preserveSourceMode: true, preserveOnvifDiscovery: sourceMode === "onvif" });
    setSetupStep("review");
  }, [resetCurrentDraft, setSetupStep, sourceMode, stagedFeeds.length]);

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

  const handleFeedAction = useCallback(async (feed: VideoFeed, action: FeedGridAction) => {
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
  }, [restartFeedMutation, startFeedMutation, stopFeedMutation]);

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
              <FeedGrid
                feeds={feeds}
                emptyState={emptyState}
                activeFeedAction={activeFeedAction}
                onEditZone={openFeedZoneEditor}
                onFeedAction={handleFeedAction}
              />

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
            <AttentionPanel items={liveAttentionItems} />
            <ActivityPanel activity={activity} />
          </div>
        </div>

        <DashboardSetupDialogs
          batchLogLevel={batchLogLevel}
          batchWebhookEnabled={batchWebhookEnabled}
          buildSnapshotLoader={sourceMode === "file" ? null : buildSnapshotLoader}
          canContinueSourceStep={canContinueSourceStep}
          canSubmitBatch={canSubmitBatch}
          caisses={caisses}
          caissesError={caissesQuery.isError}
          caissesLoading={caissesQuery.isLoading}
          closeFeedZoneEditor={closeFeedZoneEditor}
          createCaissePending={createCaisseMutation.isPending}
          createEstablishmentPending={createEstablishmentMutation.isPending}
          editingFeedZone={editingFeedZone}
          editingZonePoints={editingZonePoints}
          establishments={establishments}
          establishmentsError={establishmentsQuery.isError}
          establishmentsLoading={establishmentsQuery.isLoading}
          feedName={feedName}
          feedSource={feedSource}
          fileInputRef={fileInputRef}
          getFileLabel={getFileLabel}
          getLocalFileKey={getLocalFileKey}
          handleActivateQueuedLocalFile={handleActivateQueuedLocalFile}
          handleCaisseChange={handleCaisseChange}
          handleCreateCaisse={handleCreateCaisse}
          handleCreateEstablishment={handleCreateEstablishment}
          handleDialogOpenChange={handleDialogOpenChange}
          handleDiscoverOnvif={handleDiscoverOnvif}
          handleEditStagedFeed={handleEditStagedFeed}
          handleEstablishmentChange={handleEstablishmentChange}
          handleFileChange={handleFileChange}
          handleFinalizeBatch={handleFinalizeBatch}
          handleRemoveQueuedLocalFile={handleRemoveQueuedLocalFile}
          handleRemoveStagedFeed={handleRemoveStagedFeed}
          handleResolveOnvifStreams={handleResolveOnvifStreams}
          handleSaveEditedZone={() => void handleSaveEditedZone()}
          handleSelectOnvifDevice={handleSelectOnvifDevice}
          handleSelectZoneVideo={handleSelectZoneVideo}
          handleSourceModeChange={handleSourceModeChange}
          handleSourceStepSubmit={handleSourceStepSubmit}
          handleStageCurrentDraft={handleStageCurrentDraft}
          handleTestOnvif={handleTestOnvif}
          handleTestRtsp={handleTestRtsp}
          hasCurrentReviewDraft={currentReviewDraft !== null}
          isCreateCaisseDialogOpen={isCreateCaisseDialogOpen}
          isCreateEstablishmentDialogOpen={isCreateEstablishmentDialogOpen}
          isDiscoveringOnvif={isDiscoveringOnvif}
          isResolvingOnvifStreams={isResolvingOnvifStreams}
          isReviewSubmitting={isReviewSubmitting}
          isSavingEditedZone={isSavingEditedZone}
          isSavingMetadata={isSavingMetadata}
          isTestingCameraSource={isTestingCameraSource}
          isTestingOnvif={isTestingOnvif}
          isTestingRtsp={isTestingRtsp}
          loadExistingFeedSnapshot={loadExistingFeedSnapshot}
          localZoneVideoOptions={localZoneVideoOptions}
          newCaisseName={newCaisseName}
          newEstablishmentName={newEstablishmentName}
          onvifDevices={onvifDevices}
          onvifPassword={onvifPassword}
          onvifStreams={onvifStreams}
          onvifTestResult={onvifTestResult}
          onvifTimeout={onvifTimeout}
          onvifTransport={onvifTransport}
          onvifUsername={onvifUsername}
          preparedLocalFileDrafts={preparedLocalFileDrafts}
          preparedSourceCount={preparedSourceCount}
          queuedLocalFiles={queuedLocalFiles}
          remainingSourceSlots={remainingSourceSlots}
          resetSetupFlow={resetSetupFlow}
          reviewItems={reviewItems}
          rtspPassword={rtspPassword}
          rtspTestResult={rtspTestResult}
          rtspTransport={rtspTransport}
          rtspUsername={rtspUsername}
          selectedCaisse={selectedCaisse}
          selectedCaisseId={selectedCaisseId}
          selectedEstablishment={selectedEstablishment}
          selectedEstablishmentId={selectedEstablishmentId}
          selectedLocalZoneVideoKey={selectedLocalZoneVideoKey}
          selectedModel={selectedModel}
          selectedOnvifDevice={selectedOnvifDevice}
          selectedOnvifDeviceKey={selectedOnvifDeviceKey}
          setBatchLogLevel={setBatchLogLevel}
          setBatchWebhookEnabled={setBatchWebhookEnabled}
          setEditingZonePoints={setEditingZonePoints}
          setFeedName={setFeedName}
          setFeedSource={setFeedSource}
          setIsCreateCaisseDialogOpen={setIsCreateCaisseDialogOpen}
          setIsCreateEstablishmentDialogOpen={setIsCreateEstablishmentDialogOpen}
          setNewCaisseName={setNewCaisseName}
          setNewEstablishmentName={setNewEstablishmentName}
          setOnvifPassword={setOnvifPassword}
          setOnvifStreams={setOnvifStreams}
          setOnvifTestResult={setOnvifTestResult}
          setOnvifTimeout={setOnvifTimeout}
          setOnvifTransport={setOnvifTransport}
          setOnvifUsername={setOnvifUsername}
          setRtspPassword={setRtspPassword}
          setRtspTestResult={setRtspTestResult}
          setRtspTransport={setRtspTransport}
          setRtspUsername={setRtspUsername}
          setSelectedModel={setSelectedModel}
          setSetupStep={setSetupStep}
          setTargetSourceCount={setTargetSourceCount}
          setZonePoints={setZonePoints}
          setupStep={setupStep}
          sourceKind={sourceMode === "file" ? "Selected file" : sourceMode === "onvif" ? "ONVIF snapshot" : "RTSP preview"}
          sourceLabel={sourceMode === "file" ? uploadedFile?.name ?? "No file selected" : sourceMode === "onvif" ? selectedOnvifDevice ? `${selectedOnvifDevice.name} (${selectedOnvifDevice.ip})` : feedSource : feedSource}
          sourceMode={sourceMode}
          stagedSourceSummaries={stagedSourceSummaries}
          targetSourceCount={targetSourceCount}
          targetSourceCountValue={targetSourceCountValue}
          uploadedFile={uploadedFile}
          zonePoints={zonePoints}
        />

        <FeedDeleteDialog
          feed={feedPendingDeletion}
          isDeleting={activeFeedAction?.action === "delete"}
          onConfirm={() => void handleConfirmDeleteFeed()}
          onOpenChange={(open) => {
            if (!open) {
              setFeedPendingDeletion(null);
            }
          }}
        />
      </div>
    </AppLayout>
  );
}