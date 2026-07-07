import { roundCurrency } from "./money";

/** A tax rate applied to orders shipped to a given region. */
export interface TaxRule {
  readonly region: string;
  readonly rate: number;
}

/** The rounded tax owed on a subtotal under a given rule. */
export function taxFor(subtotal: number, rule: TaxRule): number {
  return roundCurrency(subtotal * rule.rate);
}
