import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelSelectionDialog } from "@/components/dashboard/ModelSelectionDialog";

describe("ModelSelectionDialog", () => {
  it("shows a source dropdown when multiple selected sources are available", () => {
    render(
      <ModelSelectionDialog
        caisseName={null}
        establishmentName={null}
        feedName="checkout-a"
        isSubmitting={false}
        onBack={() => {}}
        onConfirm={() => {}}
        onModelChange={() => {}}
        onOpenChange={() => {}}
        onSelectedSourceChange={() => {}}
        open
        selectedModel="m"
        selectedSourceKey="file-a"
        sourceMode="file"
        sourceOptions={[
          { key: "file-a", label: "checkout-a.mp4" },
          { key: "file-b", label: "checkout-b.mp4" },
        ]}
        zonePointCount={4}
      />,
    );

    expect(screen.getByText("Selected sources")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText(/assign a different YOLO model to each selected video or stream/i)).toBeInTheDocument();
  });
});
