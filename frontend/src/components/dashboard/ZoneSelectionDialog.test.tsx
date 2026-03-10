import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ZoneSelectionDialog } from "@/components/dashboard/ZoneSelectionDialog";

describe("ZoneSelectionDialog", () => {
  it("shows a local-video dropdown when multiple selected videos are available", async () => {

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });

    render(
      <ZoneSelectionDialog
        feedName="checkout-a"
        file={null}
        fileOptions={[
          { key: "file-a", label: "checkout-a.mp4" },
          { key: "file-b", label: "checkout-b.mp4" },
        ]}
        loadPreviewFrame={async () => ({
          frameSrc: "data:image/png;base64,ZmFrZQ==",
          sourceKind: "Selected file",
          sourceLabel: "checkout-a.mp4",
        })}
        onBack={() => {}}
        onContinue={() => {}}
        onOpenChange={() => {}}
        onPointsChange={() => {}}
        onSelectedFileChange={() => {}}
        open
        points={[]}
        selectedFileKey="file-a"
      />,
    );

    expect(await screen.findByText("Selected videos")).toBeInTheDocument();
    expect(screen.getByText(/Switch videos here to load a different frame/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getAllByText("checkout-a.mp4").length).toBeGreaterThan(0);
  });
});
