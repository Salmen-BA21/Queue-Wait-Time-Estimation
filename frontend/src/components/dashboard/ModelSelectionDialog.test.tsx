import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelSelectionDialog } from "@/components/dashboard/ModelSelectionDialog";

describe("ModelSelectionDialog", () => {
  it("renders the model picker for a single source", () => {
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
        open
        selectedModel="m"
        sourceMode="file"
        zonePointCount={4}
      />,
    );

    expect(screen.getByText("Choose Model")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText(/Finalize checkout-a/i)).toBeInTheDocument();
  });
});
