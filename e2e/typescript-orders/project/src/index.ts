/**
 * Order-pricing service — the public surface of the sample project.
 *
 * A layered, I/O-free service: `config` holds pricing configuration, `domain`
 * holds pure pricing rules (line items, tax, currency rounding), and `service`
 * composes them into an order pricer. `logging` is the small structured-logging
 * abstraction the service depends on.
 */

export type { PricingConfig } from "./config/pricing";
export { taxRuleFor } from "./config/pricing";
export { PricingError } from "./domain/errors";
export type { PricingErrorCode } from "./domain/errors";
export type { LineItem } from "./domain/lineItem";
export { lineSubtotal } from "./domain/lineItem";
export { roundCurrency } from "./domain/money";
export type { TaxRule } from "./domain/tax";
export { taxFor } from "./domain/tax";
export type { LogEntry, LogFields, Logger, LogLevel } from "./logging/logger";
export { logInfo, MemoryLogger } from "./logging/logger";
export type { Order, PricedOrder } from "./service/orderService";
export { OrderService } from "./service/orderService";
