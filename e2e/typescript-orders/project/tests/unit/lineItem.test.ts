import { describe, expect, it } from "vitest";
import { PricingError } from "../../src/domain/errors";
import { lineSubtotal } from "../../src/domain/lineItem";

describe("lineSubtotal", () => {
  it("multiplies unit price by quantity and rounds", () => {
    expect(lineSubtotal({ sku: "A", unitPrice: 2.5, quantity: 3 })).toBe(7.5);
    expect(lineSubtotal({ sku: "B", unitPrice: 0.1, quantity: 3 })).toBe(0.3);
  });

  it("rejects non-positive or fractional quantities", () => {
    expect(() => lineSubtotal({ sku: "A", unitPrice: 1, quantity: 0 })).toThrow(PricingError);
    expect(() => lineSubtotal({ sku: "A", unitPrice: 1, quantity: -2 })).toThrow(PricingError);
    expect(() => lineSubtotal({ sku: "A", unitPrice: 1, quantity: 1.5 })).toThrow(PricingError);
  });

  it("rejects negative prices", () => {
    expect(() => lineSubtotal({ sku: "A", unitPrice: -1, quantity: 1 })).toThrow(PricingError);
  });

  it("tags a rejected quantity with a stable error code", () => {
    try {
      lineSubtotal({ sku: "A", unitPrice: 1, quantity: 0 });
      expect.unreachable("expected lineSubtotal to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(PricingError);
      expect((error as PricingError).code).toBe("INVALID_QUANTITY");
    }
  });
});
