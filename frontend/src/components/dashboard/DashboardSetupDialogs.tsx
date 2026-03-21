import type { ChangeEventHandler, Dispatch, FormEventHandler, RefObject, SetStateAction } from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Loader2,
  Plus,
  Search,
  Upload,
  Video,
} from "lucide-react";

import { ModelSelectionDialog } from "@/components/dashboard/ModelSelectionDialog";
import { ReviewLaunchDialog, type ReviewLaunchItem } from "@/components/dashboard/ReviewLaunchDialog";
import { ZoneSelectionDialog } from "@/components/dashboard/ZoneSelectionDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  Caisse,
  Establishment,
  LogLevel,
  ModelSize,
  ONVIFCameraTestResult,
  ONVIFDevice,
  ONVIFStream,
  RTSPConnectionTestResult,
  RTSPTransport,
  VideoFeed,
  ZonePoint,
} from "@/lib/api";
import { formatResolution, getOnvifDeviceKey, type OnvifDeviceCredentials, type SetupStep, type SourceMode, type StagedFeedDraft } from "@/lib/dashboard-setup";

const UNASSIGNED_SELECT_VALUE = "__unassigned__";

export interface StagedSourceSummary {
  clientId: string;
  feedName: string;
  sourceLabel: string;
  sourceMode: SourceMode;
}

interface DashboardSetupDialogsProps {
  setupStep: SetupStep;
  setSetupStep: (step: SetupStep) => void;
  handleDialogOpenChange: (open: boolean) => void;
  handleSourceStepSubmit: FormEventHandler<HTMLFormElement>;
  preparedSourceCount: number;
  feedName: string;
  setFeedName: Dispatch<SetStateAction<string>>;
  sourceMode: SourceMode;
  handleSourceModeChange: (mode: SourceMode) => void;
  handleFileChange: ChangeEventHandler<HTMLInputElement>;
  fileInputRef: RefObject<HTMLInputElement>;
  uploadedFile: File | null;
  queuedLocalFiles: File[];
  getFileLabel: (file: File | null) => string;
  getLocalFileKey: (file: File) => string;
  handleActivateQueuedLocalFile: (fileKey: string) => void;
  handleRemoveQueuedLocalFile: (fileKey: string) => void;
  feedSource: string;
  setFeedSource: Dispatch<SetStateAction<string>>;
  rtspUsername: string;
  setRtspUsername: Dispatch<SetStateAction<string>>;
  rtspPassword: string;
  setRtspPassword: Dispatch<SetStateAction<string>>;
  rtspTransport: RTSPTransport;
  setRtspTransport: Dispatch<SetStateAction<RTSPTransport>>;
  rtspTestResult: RTSPConnectionTestResult | null;
  setRtspTestResult: Dispatch<SetStateAction<RTSPConnectionTestResult | null>>;
  isTestingRtsp: boolean;
  handleTestRtsp: () => void;
  handleDiscoverOnvif: () => void;
  isDiscoveringOnvif: boolean;
  onvifDevices: ONVIFDevice[];
  onvifDeviceCredentials: Record<string, OnvifDeviceCredentials>;
  selectedOnvifDevice: ONVIFDevice | null;
  selectedOnvifDeviceKey: string;
  selectedOnvifDeviceKeys: string[];
  handleSelectOnvifDevice: (device: ONVIFDevice) => void;
  handleSwitchOnvifDevice: (cameraKey: string) => void;
  handleToggleOnvifDevice: (device: ONVIFDevice) => void;
  handleSelectAllOnvifDevices: () => void;
  handleClearOnvifDeviceSelection: () => void;
  handleSetOnvifDeviceCredentials: (device: ONVIFDevice, credentials: OnvifDeviceCredentials) => void;
  onvifUsername: string;
  setOnvifUsername: Dispatch<SetStateAction<string>>;
  onvifPassword: string;
  setOnvifPassword: Dispatch<SetStateAction<string>>;
  onvifTransport: RTSPTransport;
  setOnvifTransport: Dispatch<SetStateAction<RTSPTransport>>;
  handleResolveOnvifStreams: () => void;
  isResolvingOnvifStreams: boolean;
  handleTestOnvif: () => void;
  isTestingOnvif: boolean;
  handleBulkAddSelectedOnvifDevices: () => void;
  onvifStreams: ONVIFStream[];
  setOnvifStreams: Dispatch<SetStateAction<ONVIFStream[]>>;
  onvifTestResult: ONVIFCameraTestResult | null;
  setOnvifTestResult: Dispatch<SetStateAction<ONVIFCameraTestResult | null>>;
  stagedSourceSummaries: StagedSourceSummary[];
  preparedLocalFileDrafts: StagedFeedDraft[];
  remainingSourceSlots: number;
  canContinueSourceStep: boolean;
  isTestingCameraSource: boolean;
  resetSetupFlow: () => void;
  zonePoints: ZonePoint[];
  setZonePoints: (points: ZonePoint[]) => void;
  localZoneVideoOptions: Array<{ key: string; label: string }>;
  buildSnapshotLoader: (() => Promise<{ frameSrc: string; sourceLabel: string; sourceKind: string }>) | null;
  handleSelectZoneVideo: (fileKey: string) => void;
  selectedLocalZoneVideoKey: string;
  selectedCaisse: Caisse | null;
  selectedEstablishmentId: number | null;
  setIsCreateEstablishmentDialogOpen: Dispatch<SetStateAction<boolean>>;
  establishments: Establishment[];
  establishmentsLoading: boolean;
  establishmentsError: boolean;
  handleEstablishmentChange: (value: string) => void;
  setIsCreateCaisseDialogOpen: Dispatch<SetStateAction<boolean>>;
  caissesLoading: boolean;
  caissesError: boolean;
  selectedCaisseId: number | null;
  handleCaisseChange: (value: string) => void;
  caisses: Caisse[];
  sourceLabel: string;
  sourceKind: string;
  editingFeedZone: VideoFeed | null;
  isSavingEditedZone: boolean;
  loadExistingFeedSnapshot: () => Promise<{ frameSrc: string; sourceLabel: string; sourceKind: string }>;
  closeFeedZoneEditor: () => void;
  handleSaveEditedZone: () => void;
  editingZonePoints: ZonePoint[];
  setEditingZonePoints: (points: ZonePoint[]) => void;
  selectedEstablishment: Establishment | null;
  selectedModel: ModelSize;
  setSelectedModel: Dispatch<SetStateAction<ModelSize>>;
  reviewItems: ReviewLaunchItem[];
  canSubmitBatch: boolean;
  isReviewSubmitting: boolean;
  batchLogLevel: LogLevel;
  setBatchLogLevel: Dispatch<SetStateAction<LogLevel>>;
  hasCurrentReviewDraft: boolean;
  handleEditStagedFeed: (clientId: string) => void;
  handleFinalizeBatch: (launchAfterCreate: boolean) => void;
  handleRemoveStagedFeed: (clientId: string) => void;
  handleStageCurrentDraft: () => void;
  batchWebhookEnabled: boolean;
  setBatchWebhookEnabled: Dispatch<SetStateAction<boolean>>;
  isCreateEstablishmentDialogOpen: boolean;
  handleCreateEstablishment: FormEventHandler<HTMLFormElement>;
  newEstablishmentName: string;
  setNewEstablishmentName: Dispatch<SetStateAction<string>>;
  isSavingMetadata: boolean;
  createEstablishmentPending: boolean;
  isCreateCaisseDialogOpen: boolean;
  handleCreateCaisse: FormEventHandler<HTMLFormElement>;
  newCaisseName: string;
  setNewCaisseName: Dispatch<SetStateAction<string>>;
  createCaissePending: boolean;
}

export function DashboardSetupDialogs({
  setupStep,
  setSetupStep,
  handleDialogOpenChange,
  handleSourceStepSubmit,
  preparedSourceCount,
  feedName,
  setFeedName,
  sourceMode,
  handleSourceModeChange,
  handleFileChange,
  fileInputRef,
  uploadedFile,
  queuedLocalFiles,
  getFileLabel,
  getLocalFileKey,
  handleActivateQueuedLocalFile,
  handleRemoveQueuedLocalFile,
  feedSource,
  setFeedSource,
  rtspUsername,
  setRtspUsername,
  rtspPassword,
  setRtspPassword,
  rtspTransport,
  setRtspTransport,
  rtspTestResult,
  setRtspTestResult,
  isTestingRtsp,
  handleTestRtsp,
  handleDiscoverOnvif,
  isDiscoveringOnvif,
  onvifDevices,
  onvifDeviceCredentials,
  selectedOnvifDevice,
  selectedOnvifDeviceKey,
  selectedOnvifDeviceKeys,
  handleSelectOnvifDevice,
  handleSwitchOnvifDevice,
  handleToggleOnvifDevice,
  handleSelectAllOnvifDevices,
  handleClearOnvifDeviceSelection,
  handleSetOnvifDeviceCredentials,
  onvifUsername,
  setOnvifUsername,
  onvifPassword,
  setOnvifPassword,
  onvifTransport,
  setOnvifTransport,
  handleResolveOnvifStreams,
  isResolvingOnvifStreams,
  handleTestOnvif,
  isTestingOnvif,
  handleBulkAddSelectedOnvifDevices,
  onvifStreams,
  setOnvifStreams,
  onvifTestResult,
  setOnvifTestResult,
  stagedSourceSummaries,
  preparedLocalFileDrafts,
  remainingSourceSlots,
  canContinueSourceStep,
  isTestingCameraSource,
  resetSetupFlow,
  zonePoints,
  setZonePoints,
  localZoneVideoOptions,
  buildSnapshotLoader,
  handleSelectZoneVideo,
  selectedLocalZoneVideoKey,
  selectedCaisse,
  selectedEstablishmentId,
  setIsCreateEstablishmentDialogOpen,
  establishments,
  establishmentsLoading,
  establishmentsError,
  handleEstablishmentChange,
  setIsCreateCaisseDialogOpen,
  caissesLoading,
  caissesError,
  selectedCaisseId,
  handleCaisseChange,
  caisses,
  sourceLabel,
  sourceKind,
  editingFeedZone,
  isSavingEditedZone,
  loadExistingFeedSnapshot,
  closeFeedZoneEditor,
  handleSaveEditedZone,
  editingZonePoints,
  setEditingZonePoints,
  selectedEstablishment,
  selectedModel,
  setSelectedModel,
  reviewItems,
  canSubmitBatch,
  isReviewSubmitting,
  batchLogLevel,
  setBatchLogLevel,
  hasCurrentReviewDraft,
  handleEditStagedFeed,
  handleFinalizeBatch,
  handleRemoveStagedFeed,
  handleStageCurrentDraft,
  batchWebhookEnabled,
  setBatchWebhookEnabled,
  isCreateEstablishmentDialogOpen,
  handleCreateEstablishment,
  newEstablishmentName,
  setNewEstablishmentName,
  isSavingMetadata,
  createEstablishmentPending,
  isCreateCaisseDialogOpen,
  handleCreateCaisse,
  newCaisseName,
  setNewCaisseName,
  createCaissePending,
}: DashboardSetupDialogsProps) {
  return (
    <>
      <Dialog open={setupStep === "source"} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="max-h-[92vh] overflow-y-auto border-border bg-card sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="text-foreground">Stage Sources</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Enter the feed information for one source, optionally attach metadata, then continue through zone tracing, model selection, and review.
            </DialogDescription>
          </DialogHeader>

          <form className="space-y-4" onSubmit={handleSourceStepSubmit}>
            <div className="rounded-xl border border-border bg-background/40 p-4 text-xs text-muted-foreground">
              One source is prepared at a time. Finish this source, then continue to zone tracing and model selection.
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="feed-name">Feed name</Label>
              <Input id="feed-name" onChange={(event) => setFeedName(event.target.value)} placeholder="Checkout 1" required value={feedName} />
            </div>

            <Tabs className="space-y-4" onValueChange={(value) => handleSourceModeChange(value as SourceMode)} value={sourceMode}>
              <div className="space-y-2">
                <span className="text-sm font-medium text-foreground">Source type</span>
                <TabsList className="grid h-auto w-full grid-cols-3 gap-1 bg-muted/60 p-1">
                  <TabsTrigger className="py-2" value="file">Local MP4</TabsTrigger>
                  <TabsTrigger className="py-2" value="rtsp">RTSP Camera</TabsTrigger>
                  <TabsTrigger className="py-2" value="onvif">ONVIF Discovery</TabsTrigger>
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
                      <p className="text-xs text-muted-foreground">Supported formats: MP4, MOV, AVI, and MKV. The backend stores the file and uses its path automatically.</p>
                    </div>
                  </div>

                  <input accept=".mp4,.avi,.mov,.mkv,video/*" className="hidden" onChange={handleFileChange} ref={fileInputRef} type="file" />

                  <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={() => fileInputRef.current?.click()} type="button" variant="outline">
                      <Upload className="mr-2 h-4 w-4" />
                      Choose Video File
                    </Button>
                    <span className="text-sm text-muted-foreground">{getFileLabel(uploadedFile)}</span>
                  </div>

                  <p className="text-xs text-muted-foreground">Local videos are configured one at a time so each feed keeps a single zone and model.</p>

                  {uploadedFile && (
                    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">Active video</Badge>
                        <p className="text-sm font-medium text-foreground">{uploadedFile.name}</p>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{getFileLabel(uploadedFile)}</p>
                    </div>
                  )}
                </div>
              </TabsContent>

              <TabsContent className="mt-0" value="rtsp">
                <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary"><Camera className="h-5 w-5" /></div>
                    <div>
                      <p className="text-sm font-medium text-foreground">Manual RTSP onboarding</p>
                      <p className="text-xs text-muted-foreground">Match the desktop GUI flow by validating the camera URL, credentials, and transport before the feed is registered.</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-foreground" htmlFor="feed-source">RTSP URL</Label>
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
                      <Label className="text-foreground" htmlFor="rtsp-username">Username</Label>
                      <Input id="rtsp-username" onChange={(event) => { setRtspUsername(event.target.value); setRtspTestResult(null); }} placeholder="admin" value={rtspUsername} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-foreground" htmlFor="rtsp-password">Password</Label>
                      <Input id="rtsp-password" onChange={(event) => { setRtspPassword(event.target.value); setRtspTestResult(null); }} placeholder="Optional" type="password" value={rtspPassword} />
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <div className="space-y-2">
                      <Label className="text-foreground">Transport</Label>
                      <Select onValueChange={(value) => { setRtspTransport(value as RTSPTransport); setRtspTestResult(null); }} value={rtspTransport}>
                        <SelectTrigger><SelectValue placeholder="Select RTSP transport" /></SelectTrigger>
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
                    <div className={`rounded-lg border p-3 ${rtspTestResult.connected ? "border-emerald-500/40 bg-emerald-500/10" : "border-destructive/40 bg-destructive/10"}`}>
                      <div className="flex items-start gap-2">
                        {rtspTestResult.connected ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-400" /> : <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />}
                        <div className="space-y-1 text-sm">
                          <p className="font-medium text-foreground">{rtspTestResult.connected ? "Connection successful" : "Connection failed"}</p>
                          {rtspTestResult.connected ? (
                            <p className="text-muted-foreground">{formatResolution(rtspTestResult)} at {(rtspTestResult.fps ?? 0).toFixed(1)} FPS via {rtspTestResult.transport.toUpperCase()}.</p>
                          ) : (
                            <p className="text-muted-foreground">{rtspTestResult.error ?? "The backend could not open this RTSP stream."}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Run the RTSP test before continuing. This keeps the web onboarding flow aligned with the desktop GUI.</p>
                  )}
                </div>
              </TabsContent>

              <TabsContent className="mt-0" value="onvif">
                <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary"><Search className="h-5 w-5" /></div>
                    <div>
                      <p className="text-sm font-medium text-foreground">Discover ONVIF cameras</p>
                      <p className="text-xs text-muted-foreground">Discover one ONVIF device, resolve its RTSP stream, then run a backend camera test before choosing the model.</p>
                    </div>
                  </div>

                  <div className="flex items-end justify-end">
                    <Button onClick={handleDiscoverOnvif} type="button" variant="outline" disabled={isDiscoveringOnvif}>
                      {isDiscoveringOnvif ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                      Discover Cameras
                    </Button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{onvifDevices.length} discovered</Badge>
                    {selectedOnvifDevice && <Badge variant="outline">Active: {selectedOnvifDevice.name}</Badge>}
                  </div>

                  <p className="text-xs text-muted-foreground">
                    Resolve Streams and Test Camera apply to the active camera only.
                  </p>

                  <div className="space-y-2">
                    {onvifDevices.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-border bg-background/50 p-4 text-sm text-muted-foreground">Discover ONVIF devices on the local network to continue this camera onboarding path.</div>
                    ) : (
                      <div className="space-y-3">
                        <div className="grid gap-2">
                          {onvifDevices.map((device) => {
                            const deviceKey = getOnvifDeviceKey(device);
                            const credentialValues = onvifDeviceCredentials[deviceKey] ?? { username: onvifUsername, password: onvifPassword };
                            const safeDeviceKey = deviceKey.replace(/[^a-zA-Z0-9_-]/g, "_");
                            return (
                              <div
                                key={deviceKey}
                                className={`rounded-xl border p-3 text-left transition-colors ${selectedOnvifDeviceKey === deviceKey ? "border-primary bg-primary/10" : "border-border bg-background/50 hover:border-primary/40"}`}
                              >
                                <button className="w-full text-left" onClick={() => handleSelectOnvifDevice(device)} type="button">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-3">
                                      <div>
                                        <p className="text-sm font-medium text-foreground">{device.name}</p>
                                        <p className="font-mono text-xs text-muted-foreground">{device.ip}</p>
                                      </div>
                                    </div>
                                    <Badge variant="outline">{device.model}</Badge>
                                  </div>
                                  <p className="mt-2 text-xs text-muted-foreground">{device.manufacturer} · {device.location} · {Object.keys(device.services).length} services</p>
                                </button>
                                {selectedOnvifDeviceKey === deviceKey && (
                                  <div className="mt-3 grid gap-3 border-t border-border/60 pt-3 md:grid-cols-2">
                                    <div className="space-y-2">
                                      <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground/70">Testing this camera</p>
                                      <Label className="text-foreground" htmlFor={`onvif-username-${safeDeviceKey}`}>Username for {device.name}</Label>
                                      <Input
                                        id={`onvif-username-${safeDeviceKey}`}
                                        onClick={(event) => event.stopPropagation()}
                                        onChange={(event) => handleSetOnvifDeviceCredentials(device, { username: event.target.value, password: credentialValues.password })}
                                        placeholder="admin"
                                        value={credentialValues.username}
                                      />
                                    </div>
                                    <div className="space-y-2">
                                      <Label className="text-foreground" htmlFor={`onvif-password-${safeDeviceKey}`}>Password for {device.name}</Label>
                                      <Input
                                        id={`onvif-password-${safeDeviceKey}`}
                                        onClick={(event) => event.stopPropagation()}
                                        onChange={(event) => handleSetOnvifDeviceCredentials(device, { username: credentialValues.username, password: event.target.value })}
                                        placeholder="Optional"
                                        type="password"
                                        value={credentialValues.password}
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="rounded-xl border border-dashed border-border bg-background/30 p-3 text-xs text-muted-foreground">
                    Set credentials inside the active camera card above. Those values are used when streams are resolved and when the camera is tested.
                  </div>

                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-end">
                    <div className="space-y-2">
                      <Label className="text-foreground">Transport</Label>
                      <Select onValueChange={(value) => { setOnvifTransport(value as RTSPTransport); setOnvifTestResult(null); }} value={onvifTransport}>
                        <SelectTrigger><SelectValue placeholder="Select RTSP transport" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="tcp">TCP</SelectItem>
                          <SelectItem value="udp">UDP</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <Button onClick={handleResolveOnvifStreams} type="button" variant="outline" disabled={!selectedOnvifDevice || isResolvingOnvifStreams || isTestingOnvif}>
                      {isResolvingOnvifStreams ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      Resolve Streams
                    </Button>
                    <Button onClick={handleTestOnvif} type="button" variant="outline" disabled={!selectedOnvifDevice || isTestingOnvif || isResolvingOnvifStreams}>
                      {isTestingOnvif ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                      Test Camera
                    </Button>
                  </div>

                  {onvifStreams.length > 0 && (
                    <div className="space-y-2">
                      <Label className="text-foreground">Resolved RTSP stream</Label>
                      <Select onValueChange={setFeedSource} value={feedSource}>
                        <SelectTrigger><SelectValue placeholder="Choose the stream to register" /></SelectTrigger>
                        <SelectContent>
                          {onvifStreams.map((stream) => (
                            <SelectItem key={stream.url} value={stream.url}>{stream.url}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {onvifTestResult ? (
                    <div className={`rounded-lg border p-3 ${onvifTestResult.connected ? "border-emerald-500/40 bg-emerald-500/10" : "border-destructive/40 bg-destructive/10"}`}>
                      <div className="flex items-start gap-2">
                        {onvifTestResult.connected ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-400" /> : <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />}
                        <div className="space-y-1 text-sm">
                          <p className="font-medium text-foreground">{onvifTestResult.connected ? "Camera test successful" : "Camera test failed"}</p>
                          <p className="text-muted-foreground">
                            {onvifTestResult.connected
                              ? `${formatResolution(onvifTestResult)} at ${(onvifTestResult.fps ?? 0).toFixed(1)} FPS via ${onvifTestResult.transport.toUpperCase()}.`
                              : onvifTestResult.error ?? "The backend could not validate this ONVIF camera."}
                          </p>
                          <p className="text-xs text-muted-foreground">{onvifTestResult.stream_count} resolved stream{onvifTestResult.stream_count === 1 ? "" : "s"}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">Resolve streams to inspect available RTSP URLs, then run the ONVIF camera test before continuing.</p>
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

            {(stagedSourceSummaries.length > 0 || preparedLocalFileDrafts.length > 0) && (
              <div className="space-y-3 rounded-xl border border-border bg-background/40 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">Configured sources</p>
                    <p className="text-xs text-muted-foreground">These are the sources currently prepared for zone tracing, model assignment, and review.</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{preparedSourceCount} prepared</Badge>
                    <Badge variant="outline">{remainingSourceSlots} remaining</Badge>
                  </div>
                </div>

                <div className="grid gap-2">
                  {stagedSourceSummaries.map((draft) => (
                    <div key={draft.clientId} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                      <div className="min-w-0 space-y-1">
                        <p className="text-sm font-medium text-foreground">{draft.feedName}</p>
                        <p className="truncate text-xs text-muted-foreground">{draft.sourceLabel}</p>
                      </div>
                      <Badge variant="outline">{draft.sourceMode === "file" ? "Video" : draft.sourceMode === "onvif" ? "ONVIF" : "RTSP"}</Badge>
                    </div>
                  ))}
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

            <div className="space-y-3 rounded-xl border border-border bg-background/40 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Selected source</p>
                  <p className="text-xs text-muted-foreground">This is the active source you are building before you continue to zone tracing.</p>
                </div>
                <Badge variant="outline">
                  {sourceMode === "file" ? (uploadedFile ? "1 video" : "0 videos") : sourceMode === "rtsp" ? `${feedSource.trim() ? 1 : 0} stream` : selectedOnvifDevice ? "1 camera" : "0 cameras"}
                </Badge>
              </div>

              <div className="grid gap-2">
                {sourceMode === "file" ? (
                  uploadedFile ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                      <div className="min-w-0 space-y-1">
                        <p className="text-sm font-medium text-foreground">Selected MP4</p>
                        <p className="truncate text-xs text-muted-foreground">{uploadedFile.name}</p>
                      </div>
                      <Badge variant="outline">Video</Badge>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-border bg-background/50 p-3 text-xs text-muted-foreground">
                      Pick one local video to see it listed here.
                    </div>
                  )
                ) : sourceMode === "rtsp" ? (
                  feedSource.trim() ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                      <div className="min-w-0 space-y-1">
                        <p className="text-sm font-medium text-foreground">Selected RTSP stream</p>
                        <p className="truncate text-xs text-muted-foreground">{feedSource.trim()}</p>
                      </div>
                      <Badge variant="outline">Stream</Badge>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-border bg-background/50 p-3 text-xs text-muted-foreground">
                      Enter an RTSP URL to see the selected stream here.
                    </div>
                  )
                ) : selectedOnvifDevice ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 p-3">
                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-medium text-foreground">Selected ONVIF camera</p>
                      <p className="truncate text-xs text-muted-foreground">{selectedOnvifDevice.name} · {selectedOnvifDevice.ip} · {selectedOnvifDevice.model}</p>
                    </div>
                    <Badge variant="outline">ONVIF</Badge>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-border bg-background/50 p-3 text-xs text-muted-foreground">
                    Discover and select one ONVIF camera to see it listed here.
                  </div>
                )}
              </div>
            </div>

            <DialogFooter>
              <Button onClick={resetSetupFlow} type="button" variant="outline">Cancel</Button>
              <Button disabled={!canContinueSourceStep || isTestingCameraSource} type="submit">Continue to Zone</Button>
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
        metadataContent={
          <div className="space-y-4 rounded-xl border border-border bg-background/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">Store metadata</p>
                <p className="text-xs text-muted-foreground">Metadata is saved per selected source. Switching videos or streams restores that source's establishment and caisse.</p>
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
                <Select onValueChange={handleEstablishmentChange} value={selectedEstablishmentId !== null ? String(selectedEstablishmentId) : UNASSIGNED_SELECT_VALUE}>
                  <SelectTrigger>
                    <SelectValue placeholder={establishmentsLoading ? "Loading establishments..." : "Select an establishment"} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={UNASSIGNED_SELECT_VALUE}>No establishment</SelectItem>
                    {establishments.map((establishment) => (
                      <SelectItem key={establishment.id} value={String(establishment.id)}>{establishment.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {establishmentsError && <p className="text-xs text-destructive">Failed to load establishments.</p>}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-foreground">Caisse</Label>
                  <Button onClick={() => setIsCreateCaisseDialogOpen(true)} size="sm" type="button" variant="outline" disabled={selectedEstablishmentId === null}>
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    New
                  </Button>
                </div>
                <Select onValueChange={handleCaisseChange} value={selectedCaisseId !== null ? String(selectedCaisseId) : UNASSIGNED_SELECT_VALUE} disabled={selectedEstablishmentId === null || caissesLoading}>
                  <SelectTrigger>
                    <SelectValue placeholder={selectedEstablishmentId === null ? "Select an establishment first" : caissesLoading ? "Loading caisses..." : "Select a caisse"} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={UNASSIGNED_SELECT_VALUE}>No caisse</SelectItem>
                    {caisses.map((caisse) => (
                      <SelectItem key={caisse.id} value={String(caisse.id)}>{caisse.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedEstablishmentId !== null && !caissesLoading && caisses.length === 0 && <p className="text-xs text-muted-foreground">No caisses yet for this establishment.</p>}
                {caissesError && <p className="text-xs text-destructive">Failed to load caisses for the selected establishment.</p>}
              </div>
            </div>

            <div className="rounded-lg border border-border bg-background/50 p-3 text-xs text-muted-foreground">
              {selectedCaisse?.zone
                ? "This caisse already has a saved zone. The current source can reuse it until you edit the zone."
                : "Metadata is optional, but selecting it now links this source to the SQLite hierarchy and lets saved caisse zones be reused when they exist."}
            </div>
          </div>
        }
        sourceKind={sourceKind}
        sourceLabel={sourceLabel}
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
        canSubmitBatch={canSubmitBatch}
        isSubmitting={isReviewSubmitting}
        items={reviewItems}
        logLevel={batchLogLevel}
        onBack={() => setSetupStep(hasCurrentReviewDraft ? "model" : "source")}
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
        webhookEnabled={batchWebhookEnabled}
      />

      <Dialog open={isCreateEstablishmentDialogOpen} onOpenChange={setIsCreateEstablishmentDialogOpen}>
        <DialogContent className="border-border bg-card sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-foreground">Create Establishment</DialogTitle>
            <DialogDescription className="text-muted-foreground">Add a new establishment so the feed can be grouped under the same store hierarchy used by the desktop GUI.</DialogDescription>
          </DialogHeader>

          <form className="space-y-4" onSubmit={handleCreateEstablishment}>
            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="new-establishment-name">Establishment name</Label>
              <Input id="new-establishment-name" onChange={(event) => setNewEstablishmentName(event.target.value)} placeholder="Store Alpha" value={newEstablishmentName} />
            </div>

            <DialogFooter>
              <Button onClick={() => setIsCreateEstablishmentDialogOpen(false)} type="button" variant="outline">Cancel</Button>
              <Button disabled={isSavingMetadata} type="submit">{createEstablishmentPending ? "Saving..." : "Create Establishment"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isCreateCaisseDialogOpen} onOpenChange={setIsCreateCaisseDialogOpen}>
        <DialogContent className="border-border bg-card sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-foreground">Create Caisse</DialogTitle>
            <DialogDescription className="text-muted-foreground">Add a caisse under the selected establishment. Existing saved zones for that caisse can then be reused by new feeds.</DialogDescription>
          </DialogHeader>

          <form className="space-y-4" onSubmit={handleCreateCaisse}>
            <div className="space-y-2">
              <Label className="text-foreground">Establishment</Label>
              <div className="rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-muted-foreground">{selectedEstablishment?.name ?? "No establishment selected"}</div>
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="new-caisse-name">Caisse name</Label>
              <Input id="new-caisse-name" onChange={(event) => setNewCaisseName(event.target.value)} placeholder="Register 1" value={newCaisseName} />
            </div>

            <DialogFooter>
              <Button onClick={() => setIsCreateCaisseDialogOpen(false)} type="button" variant="outline">Cancel</Button>
              <Button disabled={selectedEstablishmentId === null || isSavingMetadata} type="submit">{createCaissePending ? "Saving..." : "Create Caisse"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}