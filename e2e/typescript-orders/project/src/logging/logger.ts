/**
 * A small structured-logging abstraction. The service depends on the `Logger`
 * interface only, so callers can supply an in-memory recorder in tests or a
 * transport-backed implementation in production without touching domain code.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogFields {
  readonly [key: string]: string | number | boolean;
}

export interface LogEntry {
  readonly level: LogLevel;
  readonly message: string;
  readonly fields: LogFields;
}

export interface Logger {
  log(entry: LogEntry): void;
}

/** Collects log entries in memory — the default for tests and I/O-free contexts. */
export class MemoryLogger implements Logger {
  readonly entries: LogEntry[] = [];

  log(entry: LogEntry): void {
    this.entries.push(entry);
  }
}

/** Emit an info-level entry through any logger. */
export function logInfo(logger: Logger, message: string, fields: LogFields = {}): void {
  logger.log({ level: "info", message, fields });
}
