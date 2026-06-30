import { describe, expect, it } from "vitest";
// e2e layer (3PWR-FR-064): exercise the public package entrypoint, as a consumer would.
import { inRange, isNonEmpty, validateRecord } from "../../src/index";

describe("VUTIL-FR-001 + VUTIL-FR-004 + VUTIL-FR-005: end-to-end via public API", () => {
  it("validates a realistic signup record through the package entrypoint", () => {
    expect(isNonEmpty("Grace")).toBe(true);
    expect(inRange(85, 0, 150)).toBe(true);
    const result = validateRecord({
      name: "Grace",
      email: "grace@navy.mil",
      slug: "grace-hopper",
      age: "85",
    });
    expect(result.ok).toBe(true);
  });

  it("rejects an out-of-range age end-to-end", () => {
    const result = validateRecord({
      name: "X",
      email: "x@y.io",
      slug: "x",
      age: "999",
    });
    expect(result.ok).toBe(false);
    expect(result.errors).toContain("age");
  });
});
