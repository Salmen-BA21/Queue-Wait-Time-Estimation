import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  NetworkError,
  ValidationError,
  createEstablishment,
  listFeeds,
} from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("throws NetworkError when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(listFeeds()).rejects.toBeInstanceOf(NetworkError);
  });

  it("throws ValidationError for validation responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({
          detail: [{ msg: "Name is required" }],
        }),
      } satisfies Partial<Response>),
    );

    await expect(createEstablishment({ name: "" })).rejects.toMatchObject({
      name: "ValidationError",
      message: "Name is required",
    } satisfies Partial<ValidationError>);
  });

  it("throws ApiError when a successful response is malformed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({ success: true }),
      } satisfies Partial<Response>),
    );

    await expect(listFeeds()).rejects.toMatchObject({
      name: "ApiError",
      message: "Malformed API response.",
    } satisfies Partial<ApiError>);
  });
});