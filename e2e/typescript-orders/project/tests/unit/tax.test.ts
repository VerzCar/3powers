import { describe, expect, it } from "vitest";
import { taxRuleFor } from "../../src/config/pricing";
import { PricingError } from "../../src/domain/errors";
import { taxFor } from "../../src/domain/tax";

const config = {
  currency: "USD",
  taxRules: [
    { region: "US", rate: 0.07 },
    { region: "EU", rate: 0.2 },
  ],
} as const;

describe("taxFor", () => {
  it("applies the rate and rounds the result", () => {
    expect(taxFor(100, { region: "EU", rate: 0.2 })).toBe(20);
    expect(taxFor(25, { region: "US", rate: 0.07 })).toBe(1.75);
  });
});

describe("taxRuleFor", () => {
  it("returns the rule for a configured region", () => {
    expect(taxRuleFor(config, "US").rate).toBe(0.07);
  });

  it("throws a typed error for an unknown region", () => {
    try {
      taxRuleFor(config, "ZZ");
      expect.unreachable("expected taxRuleFor to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(PricingError);
      expect((error as PricingError).code).toBe("UNKNOWN_TAX_REGION");
    }
  });
});
