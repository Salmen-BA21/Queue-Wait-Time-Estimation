import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("allows retrying when preview loading fails", async () => {
    const loadPreviewFrame = vi
      .fn<() => Promise<{ frameSrc: string; sourceKind: string; sourceLabel: string }>>()
      .mockRejectedValueOnce(new Error("Snapshot failed"))
      .mockResolvedValueOnce({
        frameSrc: "data:image/png;base64,ZmFrZQ==",
        sourceKind: "RTSP preview",
        sourceLabel: "rtsp://camera-1/live",
      });

    render(
      <ZoneSelectionDialog
        feedName="checkout-a"
        file={null}
        loadPreviewFrame={loadPreviewFrame}
        onBack={() => {}}
        onContinue={() => {}}
        onOpenChange={() => {}}
        onPointsChange={() => {}}
        open
        points={[]}
      />,
    );

    expect(await screen.findByText("Snapshot failed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry Snapshot" }));

    await waitFor(() => expect(loadPreviewFrame).toHaveBeenCalledTimes(2));
    expect(await screen.findByAltText("Queue zone preview")).toBeInTheDocument();
  });
});
