import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useFeedWebRtc } from "@/hooks/use-feed-webrtc";
import { submitFeedWebRtcOffer } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  submitFeedWebRtcOffer: vi.fn(),
}));

describe("useFeedWebRtc", () => {
  const originalPeerConnection = globalThis.RTCPeerConnection;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(globalThis, "RTCPeerConnection", {
      configurable: true,
      writable: true,
      value: originalPeerConnection,
    });
  });

  it("reports unsupported mode when RTCPeerConnection is missing", async () => {
    Object.defineProperty(globalThis, "RTCPeerConnection", {
      configurable: true,
      writable: true,
      value: undefined,
    });

    const { result } = renderHook(() => useFeedWebRtc({ feedId: "feed-1", enabled: true }));

    await waitFor(() => {
      expect(result.current.isSupported).toBe(false);
    });

    expect(result.current.streamReady).toBe(false);
    expect(result.current.connectionError).toBe("WebRTC is not supported in this browser environment.");
    expect(submitFeedWebRtcOffer).not.toHaveBeenCalled();
  });

  it("does not signal when the hook is disabled", async () => {
    const { result } = renderHook(() => useFeedWebRtc({ feedId: "feed-1", enabled: false }));

    await waitFor(() => {
      expect(result.current.streamReady).toBe(false);
    });

    expect(result.current.connectionError).toBeNull();
    expect(submitFeedWebRtcOffer).not.toHaveBeenCalled();
  });
});
