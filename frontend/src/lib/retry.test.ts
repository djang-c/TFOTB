import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchWithRetry, isChunkError } from "./retry";

afterEach(() => vi.restoreAllMocks());
const res = (status: number) => new Response("{}", { status });

describe("fetchWithRetry", () => {
  it("tries again after a 429 and returns the answer that follows", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(res(429))
      .mockResolvedValueOnce(res(503))
      .mockResolvedValueOnce(res(200));
    const r = await fetchWithRetry("/x", undefined, { baseMs: 1 });
    expect(r.status).toBe(200);
    expect(f).toHaveBeenCalledTimes(3);
  });

  it("does not retry a real answer such as 404 or 422", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(res(404));
    expect((await fetchWithRetry("/x", undefined, { baseMs: 1 })).status).toBe(404);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("retries a dropped connection, then gives up with the last error", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"));
    await expect(fetchWithRetry("/x", undefined, { attempts: 3, baseMs: 1 })).rejects.toThrow(
      "network",
    );
    expect(f).toHaveBeenCalledTimes(3);
  });

  it("returns the last 429 after the attempts are used up, so the caller can report it", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(res(429));
    expect((await fetchWithRetry("/x", undefined, { attempts: 2, baseMs: 1 })).status).toBe(429);
  });
});

describe("isChunkError", () => {
  it("recognises a script that failed to load", () => {
    expect(
      isChunkError(
        new TypeError("Failed to fetch dynamically imported module: https://x/assets/a.js"),
      ),
    ).toBe(true);
    expect(isChunkError(new Error("Importing a module script failed."))).toBe(true);
    expect(isChunkError(new Error("Cannot read properties of undefined"))).toBe(false);
  });
});
