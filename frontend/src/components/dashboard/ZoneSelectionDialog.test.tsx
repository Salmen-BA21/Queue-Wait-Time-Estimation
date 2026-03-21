import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ZoneSelectionDialog } from "@/components/dashboard/ZoneSelectionDialog";

describe("ZoneSelectionDialog", () => {
  it("shows a single local-video preview", async () => {

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });

    render(
      <ZoneSelectionDialog
        feedName="checkout-a"
        file={null}
        loadPreviewFrame={async () => ({
          frameSrc: "data:image/png;base64,ZmFrZQ==",
          sourceKind: "Selected file",
          sourceLabel: "checkout-a.mp4",
        })}
        onBack={() => {}}
        onContinue={() => {}}
        onOpenChange={() => {}}
        onPointsChange={() => {}}
        open
        points={[]}
      />,
    );

    expect(await screen.findByText("Trace Zone")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("checkout-a.mp4")).toBeInTheDocument();
  });

  it("shows a single ONVIF camera preview", async () => {
    render(
      <ZoneSelectionDialog
        feedName="front-gate"
        file={null}
        loadPreviewFrame={async () => ({
          frameSrc: "data:image/png;base64,ZmFrZQ==",
          sourceKind: "ONVIF snapshot",
          sourceLabel: "front-gate",
        })}
        onBack={() => {}}
        onContinue={() => {}}
        onOpenChange={() => {}}
        onPointsChange={() => {}}
        open
        points={[]}
      />,
    );

    expect(await screen.findByText("Trace Zone")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("front-gate")).toBeInTheDocument();
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
