import { useCallback, useReducer } from "react";

import type { ModelSize, ZonePoint } from "@/lib/api";

export interface DashboardLocalFileConfig {
  feedName?: string;
  modelSize?: ModelSize;
  establishmentId?: number | null;
  caisseId?: number | null;
  zonePoints?: ZonePoint[];
}

interface DashboardLocalFilesState {
  queuedFiles: File[];
  configs: Record<string, DashboardLocalFileConfig>;
}

type DashboardLocalFilesAction =
  | {
      type: "merge-config";
      fileKey: string;
      config: DashboardLocalFileConfig;
    }
  | {
      type: "remove-file";
      fileKey: string;
    }
  | {
      type: "reset";
    }
  | {
      type: "set-queued-files";
      files: File[];
    };

const initialState: DashboardLocalFilesState = {
  queuedFiles: [],
  configs: {},
};

function dashboardLocalFilesReducer(
  state: DashboardLocalFilesState,
  action: DashboardLocalFilesAction,
): DashboardLocalFilesState {
  if (action.type === "set-queued-files") {
    return {
      ...state,
      queuedFiles: action.files,
    };
  }

  if (action.type === "merge-config") {
    return {
      ...state,
      configs: {
        ...state.configs,
        [action.fileKey]: {
          ...state.configs[action.fileKey],
          ...action.config,
        },
      },
    };
  }

  if (action.type === "remove-file") {
    const nextConfigs = { ...state.configs };
    delete nextConfigs[action.fileKey];

    return {
      queuedFiles: state.queuedFiles,
      configs: nextConfigs,
    };
  }

  return initialState;
}

/**
 * Stores queued local files and their per-file setup metadata outside the dashboard page component.
 */
export function useDashboardLocalFiles({
  getFileKey,
}: {
  getFileKey: (file: File) => string;
}) {
  const [state, dispatch] = useReducer(dashboardLocalFilesReducer, initialState);

  const setQueuedLocalFiles = useCallback(
    (next: File[] | ((current: File[]) => File[])) => {
      const files = typeof next === "function" ? next(state.queuedFiles) : next;
      dispatch({ type: "set-queued-files", files });
    },
    [state.queuedFiles],
  );

  const mergeLocalFileConfig = useCallback((fileKey: string, config: DashboardLocalFileConfig) => {
    dispatch({ type: "merge-config", fileKey, config });
  }, []);

  const removeLocalFile = useCallback(
    (fileKey: string) => {
      dispatch({
        type: "set-queued-files",
        files: state.queuedFiles.filter((file) => getFileKey(file) !== fileKey),
      });
      dispatch({ type: "remove-file", fileKey });
    },
    [getFileKey, state.queuedFiles],
  );

  const resetLocalFiles = useCallback(() => {
    dispatch({ type: "reset" });
  }, []);

  return {
    queuedLocalFiles: state.queuedFiles,
    localFileConfigs: state.configs,
    setQueuedLocalFiles,
    mergeLocalFileConfig,
    removeLocalFile,
    resetLocalFiles,
  };
}