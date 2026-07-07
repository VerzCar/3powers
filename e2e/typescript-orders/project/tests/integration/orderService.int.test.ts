import { describe, expect, it } from "vitest";
import type { PricingConfig } from "../../src/config/pricing";
import { PricingError } from "../../src/domain/errors";
import { MemoryLogger } from "../../src/logging/logger";
import { OrderService } from "../../src/service/orderService";

const config: PricingConfig = {
  currency: "USD",
  taxRules: [
    { region: "US", rate: 0.07 },
    { region: "EU", rate: 0.2 },
  ],
};

describe("OrderService.price", () => {
  it("prices an order across the pricing domain", () => {
    const logger = new MemoryLogger();
    const service = new OrderService(config, logger);

    const priced = service.price({
      region: "US",
      items: [
        { sku: "A", unitPrice: 10, quantity: 2 },
        { sku: "B", unitPrice: 5, quantity: 1 },
      ],
    });

    expect(priced).toEqual({ currency: "USD", subtotal: 25, tax: 1.75, total: 26.75 });
  });

  it("records one structured log entry per priced order", () => {
    const logger = new MemoryLogger();
    const service = new OrderService(config, logger);

    service.price({ region: "EU", items: [{ sku: "A", unitPrice: 100, quantity: 1 }] });

    expect(logger.entries).toHaveLength(1);
    expect(logger.entries[0]?.message).toBe("priced order");
    expect(logger.entries[0]?.fields.total).toBe(120);
  });

  it("rejects an order with no line items", () => {
    const service = new OrderService(config, new MemoryLogger());
    try {
      service.price({ region: "US", items: [] });
      expect.unreachable("expected price to throw on an empty order");
    } catch (error) {
      expect(error).toBeInstanceOf(PricingError);
      expect((error as PricingError).code).toBe("EMPTY_ORDER");
    }
  });

  it("propagates an unknown-region error from the config layer", () => {
    const service = new OrderService(config, new MemoryLogger());
    expect(() =>
      service.price({ region: "ZZ", items: [{ sku: "A", unitPrice: 1, quantity: 1 }] }),
    ).toThrow(PricingError);
  });
});
