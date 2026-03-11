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
  getOnvifDeviceKey,
  suggestFeedNameFromRtspUrl,
  type SourceMode,
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
  onvifTimeout: string;
  onvifUsername: string;
  onvifPassword: string;
  onvifTransport: RTSPTransport;
  setOnvifDevices: (devices: ONVIFDevice[]) => void;
  selectedOnvifDevice: ONVIFDevice | null;
  setSelectedOnvifDeviceKey: (value: string) => void;
  setOnvifStreams: (streams: ONVIFStream[]) => void;
  setOnvifTestResult: (result: ONVIFCameraTestResult | null) => void;
  setIsDiscoveringOnvif: (value: boolean) => void;
  setIsResolvingOnvifStreams: (value: boolean) => void;
  setIsTestingOnvif: (value: boolean) => void;
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
}: UseDashboardSourceOnboardingArgs) {
  const handleSourceModeChange = useCallback((mode: SourceMode) => {
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
  }, [fileInputRef, resetOnvifState, resetRtspState, setFeedSource, setQueuedLocalFiles, setSourceMode, setUploadedFile, setZonePoints]);

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
  }, [feedName, onvifTimeout, setFeedName, setFeedSource, setIsDiscoveringOnvif, setOnvifDevices, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKey]);

  const handleSelectOnvifDevice = useCallback((device: ONVIFDevice) => {
    setSelectedOnvifDeviceKey(getOnvifDeviceKey(device));
    setOnvifStreams([]);
    setOnvifTestResult(null);
    setFeedSource("");
    if (!feedName.trim()) {
      setFeedName(device.name);
    }
  }, [feedName, setFeedName, setFeedSource, setOnvifStreams, setOnvifTestResult, setSelectedOnvifDeviceKey]);

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
    buildSnapshotLoader,
    handleTestRtsp,
    handleDiscoverOnvif,
    handleSelectOnvifDevice,
    handleResolveOnvifStreams,
    handleTestOnvif,
  };
}