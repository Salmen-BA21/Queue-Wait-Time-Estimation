import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";
import { toast } from "sonner";

import type {
  BatchFeedDraft as ApiBatchFeedDraft,
  BatchFeedLaunchInput,
  BatchFeedLaunchResult,
  LogLevel,
} from "@/lib/api";
import { uploadVideo } from "@/lib/api";
import { createDraftId, type SetupStep, type StagedFeedDraft } from "@/lib/dashboard-setup";

interface UseDashboardBatchSubmissionArgs {
  stagedFeeds: StagedFeedDraft[];
  preparedLocalFileDrafts: StagedFeedDraft[];
  currentReviewDraft: StagedFeedDraft | null;
  batchLogLevel: LogLevel;
  batchWebhookEnabled: boolean;
  allSelectedLocalFiles: File[];
  setStagedFeeds: Dispatch<SetStateAction<StagedFeedDraft[]>>;
  setUploadedFile: (file: File | null) => void;
  setQueuedLocalFiles: (next: File[] | ((current: File[]) => File[])) => void;
  applyLocalFileSelection: (file: File | null) => void;
  setCurrentDraftId: (id: string) => void;
  setSetupStep: (step: SetupStep) => void;
  setIsFinalizingSetup: (value: boolean) => void;
  resetSetupFlow: () => void;
  createLocalFileDraftId: (file: File) => string;
  isLocalFileDraftId: (clientId: string) => boolean;
  submitBatch: (input: BatchFeedLaunchInput) => Promise<BatchFeedLaunchResult>;
}

function getLaunchSuccessMessage(result: BatchFeedLaunchResult, launchAfterCreate: boolean): string {
  return launchAfterCreate
    ? `Batch launched successfully: ${result.summary.started} source${result.summary.started === 1 ? "" : "s"} started.`
    : `Batch saved successfully: ${result.summary.created} source${result.summary.created === 1 ? "" : "s"} created.`;
}

function getLaunchFailureMessage(
  result: BatchFeedLaunchResult,
  launchAfterCreate: boolean,
  recoveredDraftCount: number,
  firstFailureReason: string | null,
): string {
  const summaryPrefix = launchAfterCreate
    ? `${result.summary.started} source${result.summary.started === 1 ? "" : "s"} started, ${result.summary.failed} failed.`
    : `${result.summary.created} source${result.summary.created === 1 ? "" : "s"} saved, ${result.summary.failed} failed.`;

  if (recoveredDraftCount > 0) {
    if (firstFailureReason) {
      return `${summaryPrefix} Failed drafts remain staged for correction. First error: ${firstFailureReason}`;
    }
    return `${summaryPrefix} Failed drafts remain staged for correction.`;
  }

  if (firstFailureReason) {
    return `${summaryPrefix} No recoverable draft was found in the setup form. First error: ${firstFailureReason}`;
  }

  return `${summaryPrefix} No recoverable draft was found in the setup form.`;
}

async function prepareBatchFeeds(drafts: StagedFeedDraft[]): Promise<ApiBatchFeedDraft[]> {
  const preparedFeeds: ApiBatchFeedDraft[] = [];

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

  return preparedFeeds;
}

function recoverFailedDrafts({
  drafts,
  failedIds,
  allSelectedLocalFiles,
  setStagedFeeds,
  setUploadedFile,
  setQueuedLocalFiles,
  applyLocalFileSelection,
  setCurrentDraftId,
  setSetupStep,
  createLocalFileDraftId,
  isLocalFileDraftId,
}: {
  drafts: StagedFeedDraft[];
  failedIds: Set<string>;
  allSelectedLocalFiles: File[];
  setStagedFeeds: Dispatch<SetStateAction<StagedFeedDraft[]>>;
  setUploadedFile: (file: File | null) => void;
  setQueuedLocalFiles: (next: File[] | ((current: File[]) => File[])) => void;
  applyLocalFileSelection: (file: File | null) => void;
  setCurrentDraftId: (id: string) => void;
  setSetupStep: (step: SetupStep) => void;
  createLocalFileDraftId: (file: File) => string;
  isLocalFileDraftId: (clientId: string) => boolean;
}) {
  const failedCameraDrafts = drafts.filter((draft) => failedIds.has(draft.clientId) && !isLocalFileDraftId(draft.clientId));
  const failedLocalFiles = allSelectedLocalFiles.filter((file) => failedIds.has(createLocalFileDraftId(file)));
  const nextActiveLocalFile = failedLocalFiles[0] ?? null;

  setStagedFeeds(failedCameraDrafts);
  setUploadedFile(nextActiveLocalFile);
  setQueuedLocalFiles(nextActiveLocalFile ? failedLocalFiles.slice(1) : []);
  applyLocalFileSelection(nextActiveLocalFile);
  setCurrentDraftId(createDraftId());
  setSetupStep("review");

  return failedCameraDrafts.length + failedLocalFiles.length;
}

export function useDashboardBatchSubmission({
  stagedFeeds,
  preparedLocalFileDrafts,
  currentReviewDraft,
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
  submitBatch,
}: UseDashboardBatchSubmissionArgs) {
  const handleFinalizeBatch = useCallback(async (launchAfterCreate: boolean) => {
    const drafts = [...stagedFeeds, ...preparedLocalFileDrafts, ...(currentReviewDraft ? [currentReviewDraft] : [])];

    if (drafts.length === 0) {
      toast.error("Stage at least one source before submitting the batch.");
      return;
    }

    setIsFinalizingSetup(true);

    try {
      const preparedFeeds = await prepareBatchFeeds(drafts);
      const result = await submitBatch({
        launch_mode: launchAfterCreate ? "create_and_start" : "save_only",
        runtime: {
          log_level: batchLogLevel,
          webhook_enabled: batchWebhookEnabled,
        },
        feeds: preparedFeeds,
      });

      const failedIds = new Set(result.results.filter((item) => item.status === "failed").map((item) => item.client_id));
      if (failedIds.size > 0) {
        const recoveredDraftCount = recoverFailedDrafts({
          drafts,
          failedIds,
          allSelectedLocalFiles,
          setStagedFeeds,
          setUploadedFile,
          setQueuedLocalFiles,
          applyLocalFileSelection,
          setCurrentDraftId,
          setSetupStep,
          createLocalFileDraftId,
          isLocalFileDraftId,
        });
        const firstFailureReason = result.results.find((item) => item.status === "failed")?.error ?? null;
        toast.error(getLaunchFailureMessage(result, launchAfterCreate, recoveredDraftCount, firstFailureReason));
        return;
      }

      toast.success(getLaunchSuccessMessage(result, launchAfterCreate));
      resetSetupFlow();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to submit the staged batch.");
    } finally {
      setIsFinalizingSetup(false);
    }
  }, [
    allSelectedLocalFiles,
    applyLocalFileSelection,
    batchLogLevel,
    batchWebhookEnabled,
    createLocalFileDraftId,
    currentReviewDraft,
    isLocalFileDraftId,
    preparedLocalFileDrafts,
    resetSetupFlow,
    setCurrentDraftId,
    setIsFinalizingSetup,
    setQueuedLocalFiles,
    setSetupStep,
    setStagedFeeds,
    setUploadedFile,
    stagedFeeds,
    submitBatch,
  ]);

  return { handleFinalizeBatch };
}