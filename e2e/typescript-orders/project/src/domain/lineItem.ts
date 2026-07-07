import { PricingError } from "./errors";
import { roundCurrency } from "./money";

/** A single priced line on an order: a SKU, its unit price, and a quantity. */
export interface LineItem {
  readonly sku: string;
  readonly unitPrice: number;
  readonly quantity: number;
}

/** The rounded extended price of one line — unit price times quantity. */
export function lineSubtotal(item: LineItem): number {
  if (!Number.isInteger(item.quantity) || item.quantity <= 0) {
    throw new PricingError(
      `quantity must be a positive integer, got ${item.quantity}`,
      "INVALID_QUANTITY",
    );
  }
  if (!Number.isFinite(item.unitPrice) || item.unitPrice < 0) {
    throw new PricingError(
      `unitPrice must be a non-negative number, got ${item.unitPrice}`,
      "INVALID_PRICE",
    );
  }
  return roundCurrency(item.unitPrice * item.quantity);
}
