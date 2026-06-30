/**
 * Validation utilities — the 3Powers walking-skeleton sample.
 *
 * Each export traces to a requirement in specs/001-validation-utils/spec.md
 * (Spec ID VUTIL). Tests reference these IDs so the spec-conformance gate can
 * prove every requirement has a linked test (3PWR-FR-030).
 */

/** VUTIL-FR-001 — reject empty / whitespace-only strings. */
export function isNonEmpty(s: string): boolean {
  return s.trim().length > 0;
}

/** VUTIL-FR-002 — single `@`, non-empty local/domain, domain contains a dot, no spaces. */
export function isEmail(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

/** VUTIL-FR-003 — lowercase alphanumeric groups joined by single hyphens. */
export function isSlug(s: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(s);
}

/** VUTIL-FR-004 — inclusive integer range check. */
export function inRange(n: number, min: number, max: number): boolean {
  return n >= min && n <= max;
}

/** VUTIL-FR-005 — parse a canonical base-10 integer, else `null`. */
export function parseIntStrict(s: string): number | null {
  if (!/^(0|-?[1-9][0-9]*)$/.test(s)) {
    return null;
  }
  return Number.parseInt(s, 10);
}

export interface UserRecord {
  name: string;
  email: string;
  slug: string;
  age: string;
}

/** Compose the predicates into one record validation (used by integration/e2e tests). */
export function validateRecord(r: UserRecord): { ok: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!isNonEmpty(r.name)) errors.push("name");
  if (!isEmail(r.email)) errors.push("email");
  if (!isSlug(r.slug)) errors.push("slug");
  const age = parseIntStrict(r.age);
  if (age === null || !inRange(age, 0, 150)) errors.push("age");
  return { ok: errors.length === 0, errors };
}
