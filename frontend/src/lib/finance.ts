// Quantitative-finance helpers. The rating table and corridor arithmetic here
// mirror contracts/synapse_liquid.py integer-for-integer; the chain is the
// source of truth and these exist to preview and explain it.

export type Rating = "AAA" | "AA" | "A" | "BBB" | "BB" | "B" | "C";
export const RATINGS: Rating[] = ["AAA", "AA", "A", "BBB", "BB", "B", "C"];

export interface RatingTier {
  rating: Rating;
  label: string;
  rateBps: number;
  advanceBps: number;
  hue: string; // tailwind-safe hex for glow + chart
}

export const TIERS: RatingTier[] = [
  { rating: "AAA", label: "Prime", rateBps: 400, advanceBps: 4000, hue: "#34d399" },
  { rating: "AA", label: "High Grade", rateBps: 600, advanceBps: 3500, hue: "#4ade80" },
  { rating: "A", label: "Upper Medium", rateBps: 850, advanceBps: 3000, hue: "#2dd4bf" },
  { rating: "BBB", label: "Investment Grade", rateBps: 1200, advanceBps: 2500, hue: "#38bdf8" },
  { rating: "BB", label: "Speculative", rateBps: 1800, advanceBps: 1500, hue: "#fbbf24" },
  { rating: "B", label: "High Risk", rateBps: 2500, advanceBps: 800, hue: "#fb923c" },
  { rating: "C", label: "Substantial Risk", rateBps: 3500, advanceBps: 400, hue: "#f87171" },
];

export const NEUTRAL_HUE = "#64748b";
export function tierFor(rating: string): RatingTier | undefined {
  return TIERS.find((t) => t.rating === rating);
}
export function hueFor(rating: string): string {
  if (rating === "DEFAULT") return "#ef4444";
  return tierFor(rating)?.hue ?? NEUTRAL_HUE;
}

export const ATTO = 10n ** 18n;
export const SECONDS_PER_YEAR = 365 * 86400;
export const TERM_MONTHS = 12;
export const MONTH_SECONDS = 30 * 86400;

export function fromAtto(v: string | bigint | number | undefined, digits = 4): string {
  if (v === undefined) return "—";
  const n = typeof v === "bigint" ? v : BigInt(v);
  const whole = n / ATTO;
  const frac = ((n % ATTO) * 10n ** BigInt(digits)) / ATTO;
  return `${whole.toString()}.${frac.toString().padStart(digits, "0")}`;
}
export function gen(v: string | bigint | undefined): number {
  if (v === undefined) return 0;
  const n = typeof v === "bigint" ? v : BigInt(v);
  return Number(n / 10n ** 12n) / 1e6;
}
export const toAtto = (g: number): bigint => BigInt(Math.round(g * 1e6)) * 10n ** 12n;
export const pct = (bps: number, d = 2) => `${(bps / 100).toFixed(d)}%`;
export const usd = (n: number) =>
  n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(1)}K` : `$${n.toFixed(0)}`;

// --------------------------------------------------------- amortisation
export interface AmortRow {
  month: number;
  interest: number;
  principal: number;
  payment: number;
  balance: number;
}

/** Equal-principal schedule over `months`, interest on the declining balance
 *  at `rateBps` per annum for 30-day periods (identical to the contract view). */
export function amortisation(principal: number, rateBps: number, months = TERM_MONTHS): AmortRow[] {
  const rows: AmortRow[] = [];
  const step = principal / months;
  let bal = principal;
  for (let m = 1; m <= months && bal > 1e-12; m++) {
    const interest = (bal * rateBps * MONTH_SECONDS) / (10000 * SECONDS_PER_YEAR);
    const pay = Math.min(step, bal);
    bal -= pay;
    rows.push({ month: m, interest, principal: pay, payment: interest + pay, balance: Math.max(0, bal) });
  }
  return rows;
}

export const totalInterest = (rows: AmortRow[]) => rows.reduce((s, r) => s + r.interest, 0);

// ------------------------------------------------------ corridor mirror
export interface Telemetry {
  monthly_revenue_usd: number;
  monthly_opex_usd: number;
  monthly_burn_usd: number;
  treasury_usd: number;
  existing_annual_debt_service_usd?: number;
  verified_onchain_inflows_usd?: number;
  company?: string;
  narrative?: string;
  transactions?: { tx: string; amount_usd: number }[];
  proof_sha256?: string;
}

export interface Underwriting {
  arr: number;
  runway: number; // months
  dscr: number; // x
  corroborationBps: number;
  ceiling: Rating;
}

const FIXED_CAP = 999;

export function underwrite(t: Telemetry, requestedUsd: number): Underwriting {
  const rev = t.monthly_revenue_usd;
  const arr = 12 * rev;
  const netBurn = t.monthly_burn_usd - rev;
  const runway = netBurn <= 0 ? FIXED_CAP : Math.min(FIXED_CAP, Math.floor((t.treasury_usd * 100) / netBurn) / 100);
  const noi = 12 * (rev - t.monthly_opex_usd);
  const ds = (t.existing_annual_debt_service_usd ?? 0) + Math.floor((requestedUsd * (1200 + 3333)) / 10000);
  const dscr = noi <= 0 ? 0 : ds <= 0 ? FIXED_CAP : Math.min(FIXED_CAP, Math.floor((noi * 100) / ds) / 100);
  const inflows = t.verified_onchain_inflows_usd ?? 0;
  const corr = rev > 0 ? Math.min(10000, Math.floor((inflows * 10000) / rev)) : 0;
  let idx: number;
  if (runway >= 24 && dscr >= 2.5 && arr >= 1_000_000) idx = 0;
  else if (runway >= 18 && dscr >= 2 && arr >= 500_000) idx = 1;
  else if (runway >= 15 && dscr >= 1.5 && arr >= 250_000) idx = 2;
  else if (runway >= 12 && dscr >= 1.25) idx = 3;
  else if (runway >= 6 && dscr >= 1) idx = 4;
  else if (runway >= 3 || dscr >= 0.75) idx = 5;
  else idx = 6;
  if (corr < 1000 && idx < 4) idx = 4;
  return { arr, runway, dscr, corroborationBps: corr, ceiling: RATINGS[idx] };
}
