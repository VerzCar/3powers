import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { PricingError } from "../../src/domain/errors";
import { roundCurrency } from "../../src/domain/money";

describe("roundCurrency", () => {
  it("rounds half-up at the cent boundary", () => {
    expect(roundCurrency(0.125)).toBe(0.13);
    expect(roundCurrency(0.375)).toBe(0.38);
  });

  it("collapses floating-point noise", () => {
    expect(roundCurrency(0.1 + 0.2)).toBe(0.3);
  });

  it("leaves already-clean amounts unchanged", () => {
    expect(roundCurrency(10)).toBe(10);
    expect(roundCurrency(0)).toBe(0);
  });

  it("rejects non-finite amounts", () => {
    expect(() => roundCurrency(Number.POSITIVE_INFINITY)).toThrow(PricingError);
    expect(() => roundCurrency(Number.NaN)).toThrow(PricingError);
  });

  it("is idempotent for cent-aligned amounts", () => {
    fc.assert(
      fc.property(fc.integer({ min: -1_000_000, max: 1_000_000 }), (cents) => {
        const amount = cents / 100;
        return roundCurrency(roundCurrency(amount)) === roundCurrency(amount);
      }),
    );
  });
});
