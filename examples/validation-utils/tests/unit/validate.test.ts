import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { inRange, isEmail, isNonEmpty, isSlug, parseIntStrict } from "../../src/validate";

describe("VUTIL-FR-001: rejects empty or whitespace-only strings", () => {
  it("rejects empty and whitespace", () => {
    expect(isNonEmpty("")).toBe(false);
    expect(isNonEmpty("   ")).toBe(false);
  });
  it("accepts non-empty", () => {
    expect(isNonEmpty("a")).toBe(true);
  });
});

describe("VUTIL-FR-002: validates email syntax", () => {
  it("accepts a valid email", () => {
    expect(isEmail("a@b.com")).toBe(true);
  });
  it("rejects malformed emails", () => {
    expect(isEmail("a@b")).toBe(false);
    expect(isEmail("a b@c.com")).toBe(false);
    expect(isEmail("@b.com")).toBe(false);
  });
});

describe("VUTIL-FR-003: validates slugs", () => {
  it("accepts lowercase hyphenated slugs", () => {
    expect(isSlug("hello-world-2")).toBe(true);
  });
  it("rejects invalid slugs", () => {
    expect(isSlug("Hello")).toBe(false);
    expect(isSlug("a--b")).toBe(false);
    expect(isSlug("-a")).toBe(false);
  });
});

describe("VUTIL-FR-004: inclusive integer range", () => {
  it("checks bounds inclusively", () => {
    expect(inRange(5, 1, 10)).toBe(true);
    expect(inRange(1, 1, 10)).toBe(true);
    expect(inRange(0, 1, 10)).toBe(false);
  });
});

describe("VUTIL-FR-005: strict base-10 integer parsing", () => {
  it("parses canonical integers and rejects the rest", () => {
    expect(parseIntStrict("42")).toBe(42);
    expect(parseIntStrict("-7")).toBe(-7);
    expect(parseIntStrict("0")).toBe(0);
    for (const bad of ["007", "1.0", " 1 ", "x", "", "-0"]) {
      expect(parseIntStrict(bad)).toBeNull();
    }
  });

  // Property-based test (3PWR-FR-024): the parser round-trips every integer.
  it("round-trips every integer", () => {
    fc.assert(fc.property(fc.integer(), (n) => parseIntStrict(String(n)) === n));
  });
});
