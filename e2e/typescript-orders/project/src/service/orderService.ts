import { type PricingConfig, taxRuleFor } from "../config/pricing";
import { PricingError } from "../domain/errors";
import { type LineItem, lineSubtotal } from "../domain/lineItem";
import { roundCurrency } from "../domain/money";
import { taxFor } from "../domain/tax";
import { type Logger, logInfo } from "../logging/logger";

/** An order awaiting pricing: a destination region and its line items. */
export interface Order {
  readonly region: string;
  readonly items: readonly LineItem[];
}

/** The priced result: subtotal, tax, and grand total in the config currency. */
export interface PricedOrder {
  readonly currency: string;
  readonly subtotal: number;
  readonly tax: number;
  readonly total: number;
}

/** Prices orders by composing the line-item, tax, and rounding domain rules. */
export class OrderService {
  private readonly config: PricingConfig;
  private readonly logger: Logger;

  constructor(config: PricingConfig, logger: Logger) {
    this.config = config;
    this.logger = logger;
  }

  price(order: Order): PricedOrder {
    if (order.items.length === 0) {
      throw new PricingError("cannot price an order with no line items", "EMPTY_ORDER");
    }
    const subtotal = roundCurrency(order.items.reduce((sum, item) => sum + lineSubtotal(item), 0));
    const rule = taxRuleFor(this.config, order.region);
    const tax = taxFor(subtotal, rule);
    const total = roundCurrency(subtotal + tax);
    logInfo(this.logger, "priced order", {
      region: order.region,
      items: order.items.length,
      total,
    });
    return { currency: this.config.currency, subtotal, tax, total };
  }
}
