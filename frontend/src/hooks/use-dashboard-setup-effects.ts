import { useEffect } from "react";

import type { ModelSize, ZonePoint } from "@/lib/api";
import type { SetupStep, SourceMode } from "@/lib/dashboard-setup";

interface CaisseLike {
  id: number;
  zone?: {
    points: ZonePoint[];
  } | null;
}

/**
 * Keeps the dashboard setup flow state synchronized while the page component focuses on orchestration.
 */
export function useDashboardSetupEffects({
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
  isLoadingCaisses,
  setSelectedCaisseId,
}: {
  setupStep: SetupStep;
  zonePoints: ZonePoint[];
  selectedCaisse: CaisseLike | null;
  setZonePoints: (points: ZonePoint[]) => void;
  sourceMode: SourceMode;
  uploadedFile: File | null;
  getLocalFileKey: (file: File) => string;
  mergeLocalFileConfig: (fileKey: string, config: {
    feedName: string;
    modelSize: ModelSize;
    establishmentId: number | null;
    caisseId: number | null;
    zonePoints: ZonePoint[];
  }) => void;
  feedName: string;
  selectedModel: ModelSize;
  selectedEstablishmentId: number | null;
  selectedCaisseId: number | null;
  caisses: CaisseLike[];
  isLoadingCaisses: boolean;
  setSelectedCaisseId: (value: number | null) => void;
}) {
  useEffect(() => {
    if (setupStep === null || zonePoints.length > 0 || !selectedCaisse?.zone?.points?.length) {
      return;
    }

    setZonePoints(selectedCaisse.zone.points);
  }, [selectedCaisse, setZonePoints, setupStep, zonePoints.length]);

  useEffect(() => {
    if (sourceMode !== "file" || !uploadedFile) {
      return;
    }

    mergeLocalFileConfig(getLocalFileKey(uploadedFile), {
      feedName,
      modelSize: selectedModel,
      establishmentId: selectedEstablishmentId,
      caisseId: selectedCaisseId,
      zonePoints,
    });
  }, [
    feedName,
    getLocalFileKey,
    mergeLocalFileConfig,
    selectedCaisseId,
    selectedEstablishmentId,
    selectedModel,
    sourceMode,
    uploadedFile,
    zonePoints,
  ]);

  useEffect(() => {
    if (selectedEstablishmentId === null) {
      if (selectedCaisseId !== null) {
        setSelectedCaisseId(null);
      }
      return;
    }

    if (isLoadingCaisses) {
      return;
    }

    if (selectedCaisseId !== null && !caisses.some((caisse) => caisse.id === selectedCaisseId)) {
      setSelectedCaisseId(null);
    }
  }, [caisses, isLoadingCaisses, selectedCaisseId, selectedEstablishmentId, setSelectedCaisseId]);
}