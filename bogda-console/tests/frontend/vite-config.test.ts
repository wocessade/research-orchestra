// @vitest-environment node

import { describe, expect, it } from "vitest";

import { resolveDevPorts } from "../../vite.config";

describe("resolveDevPorts", () => {
  it("uses public 3101 and loopback BFF 3102", () => {
    expect(resolveDevPorts({})).toEqual({ publicPort: 3101, bffPort: 3102 });
  });

  it("rejects either port when it is 3100", () => {
    expect(() => resolveDevPorts({ BOGDA_CONSOLE_PUBLIC_PORT: "3100" })).toThrow(/reserved/);
    expect(() => resolveDevPorts({ BOGDA_CONSOLE_BFF_PORT: "3100" })).toThrow(/reserved/);
  });
});
