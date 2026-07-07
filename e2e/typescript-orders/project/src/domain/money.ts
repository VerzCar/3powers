import { PricingError } from "./errors";

/**
 * Round a monetary amount to two decimal places using half-up rounding. The
 * small epsilon nudge keeps values like `1.785` from falling short of their
 * exact half boundary under IEEE-754 arithmetic.
 */
export function roundCurrency(amount: number): number {
  if (!Number.isFinite(amount)) {
    throw new PricingError(`amount must be a finite number, got ${amount}`, "INVALID_PRICE");
  }
  return Math.round((amount + Number.EPSILON) * 100) / 100;
}
