import { useCallback } from "react";
import type { RefObject } from "react";
import { toast } from "sonner";

import {
  captureRtspSnapshot,
  discoverOnvifDevices,
  resolveOnvifStreams,
  testOnvifCamera,
  testRtspConnection,
  type ONVIFCameraTestResult,
  type ONVIFDevice,
  type ONVIFStream,
  type RTSPConnectionTestResult,
  type RTSPSnapshotResult,
  type RTSPTransport,
} from "@/lib/api";
import {
  formatResolution,
  DEFAULT_ONVIF_TIMEOUT,
  getOnvifDeviceKey,
  createDraftId,
  suggestFeedNameFromRtspUrl,
  type OnvifDeviceCredentials,
  type SetupStep,
  type SourceMode,
  type StagedFeedDraft,
} from "@/lib/dashboard-setup";

interface UseDashboardSourceOnboardingArgs {
  sourceMode: SourceMode;
  setSourceMode: (mode: SourceMode) => void;
  feedSource: string;
  setFeedSource: (value: string | ((current: string) => string)) => void;
  feedName: string;
  setFeedName: (value: string) => void;
  uploadedFile: File | null;
  setUploadedFile: (file: File | null) => void;
  setQueuedLocalFiles: (next: File[] | ((current: File[]) => File[])) => void;
  setZonePoints: (points: Array<{ x: number; y: number }>) => void;
  fileInputRef: RefObject<HTMLInputElement>;
  resetRtspState: () => void;
  resetOnvifState: () => void;
  rtspUsername: string;
  rtspPassword: string;
  rtspTransport: RTSPTransport;
  setRtspTestResult: (result: RTSPConnectionTestResult | null) => void;
  setIsTestingRtsp: (value: boolean) => void;
  onvifUsername: string;
  onvifPassword: string;
  onvifTransport: RTSPTransport;
  onvifDevices: ONVIFDevice[];
  setOnvifDevices: (devices: ONVIFDevice[]) => void;
  onvifDeviceCredentials: Record<string, OnvifDeviceCredentials>;
  setOnvifDeviceCredentials: (value: Record<string, OnvifDeviceCredentials> | ((current: Record<string, OnvifDeviceCredentials>) => Record<string, OnvifDeviceCredentials>)) => void;
  selectedOnvifDevice: ONVIFDevice | null;
  selectedOnvifDeviceKeys: string[];
  setSelectedOnvifDeviceKeys: (value: string[] | ((current: string[]) => string[])) => void;
  setOnvifStreams: (streams: ONVIFStream[]) => void;
  setOnvifTestResult: (result: ONVIFCameraTestResult | null) => void;
  setIsDiscoveringOnvif: (value: boolean) => void;
  setIsResolvingOnvifStreams: (value: boolean) => void;
  setIsTestingOnvif: (value: boolean) => void;
  setStagedFeeds: (value: StagedFeedDraft[] | ((current: StagedFeedDraft[]) => StagedFeedDraft[])) => void;
  selectedModel: "n" | "s" | "m" | "l" | "x";
  selectedEstablishmentId: number | null;
  selectedEstablishmentName: string | null;
  selectedCaisseId: number | null;
  selectedCaisseName: string | null;
  selectedCaisseHasSavedZone: boolean;
  setSetupStep: (step: SetupStep) => void;
}

export function useDashboardSourceOnboarding({
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
  onvifUsername,
  onvifPassword,
  onvifTransport,
  onvifDevices,
  setOnvifDevices,
  onvifDeviceCredentials,
  setOnvifDeviceCredentials,
  selectedOnvifDevice,
  selectedOnvifDeviceKeys,
  setSelectedOnvifDeviceKeys,
  setOnvifStreams,
  setOnvifTestResult,
  setIsDiscoveringOnvif,
  setIsResolvingOnvifStreams,
  setIsTestingOnvif,
  setStagedFeeds,
  selectedModel,
  selectedEstablishmentId,
  selectedEstablishmentName,
  selectedCaisseId,
  selectedCaisseName,
  selectedCaisseHasSavedZone,
  setSetupStep,
}: UseDashboardSourceOnboardingArgs) {
  const handleSourceModeChange = useCallback((mode: SourceMode) => {
    setSourceMode(mode);
  }, [setSourceMode]);

  const getResolvedOnvifCredentials = useCallback((device: ONVIFDevice): { username: string; password: string } => {
    const deviceKey = getOnvifDeviceKey(device);
    return onvifDeviceCredentials[deviceKey] ?? { username: onvifUsername, password: onvifPassword };
  }, [onvifDeviceCredentials, onvifPassword, onvifUsername]);

  const handleSetOnvifDeviceCredentials = useCallback((device: ONVIFDevice, credentials: { username: string; password: string }) => {
    const deviceKey = getOnvifDeviceKey(device);

    setOnvifDeviceCredentials((current) => ({
      ...current,
      [deviceKey]: credentials,
    }));
  }, [setOnvifDeviceCredentials]);

  const buildSnapshotLoader = useCallback(async (): Promise<{ frameSrc: string; sourceLabel: string; sourceKind: string }> => {
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

  const handleTestRtsp = useCallback(async () => {
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
  }, [feedName, feedSource, rtspPassword, rtspTransport, rtspUsername, setFeedName, setIsTestingRtsp, setRtspTestResult]);

  const handleDiscoverOnvif = useCallback(async () => {
    const timeoutSeconds = Number.parseFloat(DEFAULT_ONVIF_TIMEOUT);
    if (Number.isNaN(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 30) {
      toast.error("Enter an ONVIF discovery timeout between 0 and 30 seconds.");
      return;
    }

    setIsDiscoveringOnvif(true);
    setOnvifDevices([]);
    setSelectedOnvifDeviceKeys([]);
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setFeedSource("");

    try {
      const devices = await discoverOnvifDevices({ timeout_seconds: timeoutSeconds });
      setOnvifDevices(devices);

      if (devices.length > 0) {
        const firstDevice = devices[0];
        setSelectedOnvifDeviceKeys([getOnvifDeviceKey(firstDevice)]);
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
  }, [feedName, setFeedName, setFeedSource, setIsDiscoveringOnvif, setOnvifDevices, setOnvifDeviceCredentials, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKeys]);

  const handleSelectOnvifDevice = useCallback((device: ONVIFDevice) => {
    setSelectedOnvifDeviceKeys([getOnvifDeviceKey(device)]);
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setFeedSource("");
    if (!feedName.trim()) {
      setFeedName(device.name);
    }
  }, [feedName, setFeedName, setFeedSource, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKeys]);

  const handleToggleOnvifDevice = useCallback((device: ONVIFDevice) => {
    const deviceKey = getOnvifDeviceKey(device);

    setSelectedOnvifDeviceKeys((current) => {
      if (current.includes(deviceKey)) {
        return current.filter((key) => key !== deviceKey);
      }

      return [...current, deviceKey];
    });

    setOnvifStreams([]);
    setOnvifTestResult(null);
    if (!feedName.trim()) {
      setFeedName(device.name);
    }
  }, [feedName, setFeedName, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKeys]);

  const handleSelectAllOnvifDevices = useCallback(() => {
    setSelectedOnvifDeviceKeys(onvifDevices.map((device) => getOnvifDeviceKey(device)));
    setOnvifStreams([]);
    setOnvifTestResult(null);
  }, [onvifDevices, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKeys]);

  const handleClearOnvifDeviceSelection = useCallback(() => {
    setSelectedOnvifDeviceKeys([]);
    setOnvifStreams([]);
    setOnvifTestResult(null);
  }, [setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKeys]);

  const handleBulkAddSelectedOnvifDevices = useCallback(async () => {
    if (selectedOnvifDeviceKeys.length === 0) {
      toast.error("Select one or more ONVIF cameras first.");
      return;
    }

    const selectedDevices = onvifDevices.filter((device) => selectedOnvifDeviceKeys.includes(getOnvifDeviceKey(device)));
    if (selectedDevices.length === 0) {
      toast.error("Select one or more ONVIF cameras first.");
      return;
    }

    setIsTestingOnvif(true);

    try {
      const stagedDrafts: StagedFeedDraft[] = [];

      for (const device of selectedDevices) {
        const { username, password } = getResolvedOnvifCredentials(device);
        if (password.trim() && !username.trim()) {
          throw new Error(`Enter a username for ${device.name} before using a password.`);
        }

        const streams = await resolveOnvifStreams({
          device,
          username: username.trim() || undefined,
          password: password.trim() || undefined,
        });

        if (streams.length === 0) {
          throw new Error(`No RTSP streams were resolved for ${device.name}.`);
        }

        const testResult = await testOnvifCamera({
          device,
          username: username.trim() || undefined,
          password: password.trim() || undefined,
          transport: onvifTransport,
        });

        const primaryStream = testResult.tested_stream?.url ?? streams[0]?.url ?? "";
        if (!primaryStream) {
          throw new Error(`No RTSP stream could be chosen for ${device.name}.`);
        }

        const derivedFeedName = feedName.trim()
          ? selectedDevices.length === 1
            ? feedName.trim()
            : `${feedName.trim()} - ${device.name}`
          : device.name;

        stagedDrafts.push({
          clientId: createDraftId(),
          feedName: derivedFeedName,
          sourceMode: "onvif",
          source: primaryStream,
          uploadedFile: null,
          zonePoints: [],
          modelSize: selectedModel,
          establishmentId: selectedEstablishmentId,
          establishmentName: selectedEstablishmentName,
          caisseId: selectedCaisseId,
          caisseName: selectedCaisseName,
          hasSavedCaisseZone: selectedCaisseHasSavedZone,
          rtspUsername: onvifUsername.trim(),
          rtspPassword: onvifPassword.trim(),
          rtspTransport: onvifTransport,
          rtspTestResult: null,
          onvifUsername,
          onvifPassword,
          onvifTransport,
          onvifDevices: [device],
          selectedOnvifDeviceKey: getOnvifDeviceKey(device),
          onvifStreams: streams,
          onvifTestResult: testResult,
        });
      }

      setStagedFeeds((current) => [...current, ...stagedDrafts]);
      setSelectedOnvifDeviceKeys([]);
      setOnvifStreams([]);
      setOnvifTestResult(null);
      setSetupStep("review");
      toast.success(`Added ${stagedDrafts.length} ONVIF camera${stagedDrafts.length === 1 ? "" : "s"} to the review queue.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to add the selected ONVIF cameras.");
    } finally {
      setIsTestingOnvif(false);
    }
  }, [
    feedName,
    getResolvedOnvifCredentials,
    onvifDevices,
    onvifPassword,
    onvifTransport,
    onvifUsername,
    selectedCaisseHasSavedZone,
    selectedCaisseId,
    selectedCaisseName,
    selectedEstablishmentId,
    selectedEstablishmentName,
    selectedModel,
    selectedOnvifDeviceKeys,
    setIsTestingOnvif,
    setOnvifDeviceCredentials,
    setOnvifStreams,
    setOnvifTestResult,
    setSelectedOnvifDeviceKeys,
    setStagedFeeds,
  ]);

  const handleResolveOnvifStreams = useCallback(async () => {
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
  }, [onvifPassword, onvifUsername, selectedOnvifDevice, setFeedSource, setIsResolvingOnvifStreams, setOnvifStreams, setOnvifTestResult]);

  const handleTestOnvif = useCallback(async () => {
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
  }, [feedName, onvifPassword, onvifTransport, onvifUsername, selectedOnvifDevice, setFeedName, setFeedSource, setIsTestingOnvif, setOnvifStreams, setOnvifTestResult]);

  return {
    handleSourceModeChange,
    handleSetOnvifDeviceCredentials,
    buildSnapshotLoader,
    handleTestRtsp,
    handleDiscoverOnvif,
    handleSelectOnvifDevice,
    handleToggleOnvifDevice,
    handleSelectAllOnvifDevices,
    handleClearOnvifDeviceSelection,
    handleResolveOnvifStreams,
    handleTestOnvif,
    handleBulkAddSelectedOnvifDevices,
  };
}