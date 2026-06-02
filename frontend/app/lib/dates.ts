/**
 * Date formatting helpers — pinned to `es-MX` locale and `America/Mexico_City`
 * timezone so SSR and CSR produce identical strings (no hydration mismatch).
 *
 * Use these instead of `new Date(x).toLocaleString()` / `.toLocaleDateString()`
 * anywhere a date is reachable from JSX.
 */

const LOCALE = "es-MX";
const TIME_ZONE = "America/Mexico_City";

type DateInput = string | number | Date | null | undefined;

function toDate(input: DateInput): Date | null {
  if (input == null) return null;
  const d = input instanceof Date ? input : new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

const DATE_FMT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const DATETIME_FMT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

const TIME_FMT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

const MONTH_DAY_FMT = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  month: "short",
  day: "numeric",
});

export function formatDate(input: DateInput, fallback = "—"): string {
  const d = toDate(input);
  return d ? DATE_FMT.format(d) : fallback;
}

export function formatDateTime(input: DateInput, fallback = "—"): string {
  const d = toDate(input);
  return d ? DATETIME_FMT.format(d) : fallback;
}

export function formatTime(input: DateInput, fallback = "—"): string {
  const d = toDate(input);
  return d ? TIME_FMT.format(d) : fallback;
}

export function formatMonthDay(input: DateInput, fallback = "—"): string {
  const d = toDate(input);
  return d ? MONTH_DAY_FMT.format(d) : fallback;
}
