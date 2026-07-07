import { PricingError } from "../domain/errors";
import type { TaxRule } from "../domain/tax";

/** Static pricing configuration for the order service: currency and tax rules. */
export interface PricingConfig {
  readonly currency: string;
  readonly taxRules: readonly TaxRule[];
}

/** The tax rule for a region, or a typed error when none is configured. */
export function taxRuleFor(config: PricingConfig, region: string): TaxRule {
  const rule = config.taxRules.find((r) => r.region === region);
  if (rule === undefined) {
    throw new PricingError(`no tax rule configured for region ${region}`, "UNKNOWN_TAX_REGION");
  }
  return rule;
}
