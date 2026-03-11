import { useCallback, useMemo, useRef, useState } from "react";

import type { DashboardLocalFileConfig } from "@/hooks/use-dashboard-local-files";
import { createDraftId, DEFAULT_ONVIF_TIMEOUT, getOnvifDeviceKey } from "@/lib/dashboard-setup";
import type { SetupStep, SourceMode, StagedFeedDraft } from "@/lib/dashboard-setup";
import type {
  LogLevel,
  ModelSize,
  ONVIFCameraTestResult,
  ONVIFDevice,
  ONVIFStream,
  RTSPConnectionTestResult,
  RTSPTransport,
  ZonePoint,
} from "@/lib/api";

interface UseDashboardSetupStateArgs {
  getStoredLocalFileConfig: (file: File | null) => DashboardLocalFileConfig | undefined;
  setQueuedLocalFiles: (next: File[] | ((current: File[]) => File[])) => void;
  resetLocalFiles: () => void;
}

interface ResetCurrentDraftOptions {
  preserveSourceMode?: boolean;
  preserveOnvifDiscovery?: boolean;
  nextUploadedFile?: File | null;
  nextQueuedLocalFiles?: File[];
}

export function useDashboardSetupState({
  getStoredLocalFileConfig,
  setQueuedLocalFiles,
  resetLocalFiles,
}: UseDashboardSetupStateArgs) {
  const [setupStep, setSetupStep] = useState<SetupStep>(null);
  const [targetSourceCount, setTargetSourceCount] = useState("1");
  const [stagedFeeds, setStagedFeeds] = useState<StagedFeedDraft[]>([]);
  const [currentDraftId, setCurrentDraftId] = useState(() => createDraftId());
  const [feedName, setFeedName] = useState("");
  const [feedSource, setFeedSource] = useState("");
  const [sourceMode, setSourceMode] = useState<SourceMode>("file");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [zonePoints, setZonePoints] = useState<ZonePoint[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelSize>("n");
  const [isFinalizingSetup, setIsFinalizingSetup] = useState(false);
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

  const targetSourceCountValue = useMemo(() => {
    const parsed = Number.parseInt(targetSourceCount, 10);
    if (Number.isNaN(parsed) || parsed < 1) {
      return 1;
    }
    return parsed;
  }, [targetSourceCount]);

  const selectedOnvifDevice = useMemo(
    () => onvifDevices.find((device) => getOnvifDeviceKey(device) === selectedOnvifDeviceKey) ?? null,
    [onvifDevices, selectedOnvifDeviceKey],
  );

  const isTestingCameraSource = isTestingRtsp || isDiscoveringOnvif || isResolvingOnvifStreams || isTestingOnvif;

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
  }: ResetCurrentDraftOptions = {}) => {
    const nextSourceMode = preserveSourceMode ? sourceMode : "file";
    const nextFileConfig = nextUploadedFile ? getStoredLocalFileConfig(nextUploadedFile) : undefined;

    setFeedName("");
    setFeedSource("");
    setSourceMode(nextSourceMode);
    setUploadedFile(nextSourceMode === "file" ? nextUploadedFile : null);
    setQueuedLocalFiles(nextSourceMode === "file" ? nextQueuedLocalFiles ?? [] : []);
    setZonePoints(nextSourceMode === "file" && nextUploadedFile ? nextFileConfig?.zonePoints ?? [] : []);
    setSelectedModel(nextSourceMode === "file" && nextUploadedFile ? nextFileConfig?.modelSize ?? "n" : "n");
    setSelectedEstablishmentId(nextSourceMode === "file" && nextUploadedFile ? nextFileConfig?.establishmentId ?? null : null);
    setSelectedCaisseId(nextSourceMode === "file" && nextUploadedFile ? nextFileConfig?.caisseId ?? null : null);

    if (nextSourceMode === "file" && nextUploadedFile) {
      const suggestedFeedName = nextUploadedFile.name.replace(/\.[^.]+$/, "") || nextUploadedFile.name;
      setFeedName(nextFileConfig?.feedName ?? suggestedFeedName);
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
  }, [getStoredLocalFileConfig, resetOnvifState, resetRtspState, setQueuedLocalFiles, sourceMode]);

  const resetSetupFlow = useCallback(() => {
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
    resetLocalFiles();
    resetCurrentDraft();
  }, [resetCurrentDraft, resetLocalFiles]);

  return {
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
  };
}