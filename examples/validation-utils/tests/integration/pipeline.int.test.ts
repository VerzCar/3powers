import { describe, expect, it } from "vitest";
import { validateRecord } from "../../src/validate";

// Integration layer (3PWR-FR-064): the predicates composed into one record check.
describe("VUTIL-FR-002 + VUTIL-FR-003: record validation composes predicates", () => {
  it("accepts a fully valid record", () => {
    const r = { name: "Ada", email: "ada@example.com", slug: "ada-lovelace", age: "36" };
    expect(validateRecord(r)).toEqual({ ok: true, errors: [] });
  });

  it("collects every failing field", () => {
    const r = { name: " ", email: "nope", slug: "Bad Slug", age: "12.5" };
    expect(validateRecord(r).ok).toBe(false);
    expect(validateRecord(r).errors).toEqual(["name", "email", "slug", "age"]);
  });
});
