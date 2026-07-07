/**
 * Typed error handling for the order-pricing domain. Every failure path raises a
 * `PricingError` carrying a stable machine-readable `code`, so callers branch on
 * the code rather than parsing messages.
 */

export type PricingErrorCode =
  | "EMPTY_ORDER"
  | "INVALID_PRICE"
  | "INVALID_QUANTITY"
  | "UNKNOWN_TAX_REGION";

export class PricingError extends Error {
  readonly code: PricingErrorCode;

  constructor(message: string, code: PricingErrorCode) {
    super(message);
    this.name = "PricingError";
    this.code = code;
  }
}
