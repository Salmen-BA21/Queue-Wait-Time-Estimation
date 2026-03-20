import type {
  ModelSize,
  ONVIFCameraTestResult,
  ONVIFDevice,
  ONVIFStream,
  RTSPConnectionTestResult,
  RTSPTransport,
  ZonePoint,
} from "@/lib/api";

export type SetupStep = "source" | "zone" | "model" | "review" | null;
export type SourceMode = "rtsp" | "file" | "onvif";
export type FeedAction = "start" | "stop" | "restart" | "delete";

export interface StagedFeedDraft {
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

export interface OnvifDeviceCredentials {
  username: string;
  password: string;
}

export const DEFAULT_ONVIF_TIMEOUT = "5";

export function formatResolution(result: {
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

export function getOnvifDeviceKey(device: ONVIFDevice): string {
  return `${device.ip}|${device.xaddrs ?? ""}`;
}

export function suggestFeedNameFromRtspUrl(url: string): string | null {
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

export function createDraftId(): string {
  return `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function getDraftSelectedOnvifDevice(draft: StagedFeedDraft): ONVIFDevice | null {
  return draft.onvifDevices.find((device) => getOnvifDeviceKey(device) === draft.selectedOnvifDeviceKey) ?? null;
}

export function getDraftSourceLabel(draft: StagedFeedDraft): string {
  if (draft.sourceMode === "file") {
    return draft.uploadedFile ? draft.uploadedFile.name : "No video selected";
  }

  if (draft.sourceMode === "onvif") {
    const device = getDraftSelectedOnvifDevice(draft);
    return device ? `${device.name} (${device.ip})` : draft.source || "No ONVIF camera selected";
  }

  return draft.source.trim() || "No RTSP URL provided";
}

export function getDraftSourceDetail(draft: StagedFeedDraft): string {
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