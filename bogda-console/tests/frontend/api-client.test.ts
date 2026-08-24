import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiClientError } from "../../frontend/src/api/client";


afterEach(() => vi.unstubAllGlobals());


describe("api client", () => {
  it("throws the closed envelope without treating a 503 as success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: null,
      sources: {},
      errors: [{ code: "PREFECT_UNAVAILABLE", message: "offline", source: "prefect", retryable: true }],
    }), { status: 503, headers: { "Content-Type": "application/json" } })));

    await expect(api.get("/api/v1/runs")).rejects.toMatchObject({
      status: 503,
      errors: [{ code: "PREFECT_UNAVAILABLE" }],
    });
  });

  it("does not retry or mutate a failed command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: null,
      sources: {},
      errors: [{ code: "RESOURCE_CHANGED", message: "changed", source: "prefect", retryable: false }],
    }), { status: 409, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.command("/api/v1/runs/r1/cancel", { expectedCommandVersion: "old" })).rejects.toBeInstanceOf(ApiClientError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
