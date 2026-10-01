import type { ReactNode } from "react";
import { hueFor } from "../lib/finance";

export function Panel({ title, icon, right, children, className = "" }: {
  title: string; icon?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <h2 className="flex flex-nowrap items-center gap-2 whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
          {icon}{title}
        </h2>
        <div className="flex flex-nowrap items-center gap-2 whitespace-nowrap">{right}</div>
      </header>
      {children}
    </section>
  );
}

export function RatingBadge({ rating, size = "md" }: { rating: string; size?: "sm" | "md" | "lg" }) {
  const hue = hueFor(rating);
  const pad = size === "lg" ? "px-3 py-1 text-sm" : size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`num inline-flex items-center justify-center rounded border font-bold tracking-wider ${pad}`}
      style={{ color: hue, borderColor: `${hue}66`, background: `${hue}14`, boxShadow: `0 0 14px ${hue}40, inset 0 0 8px ${hue}1a` }}
    >
      {rating === "UNRATED" ? "NR" : rating}
    </span>
  );
}

const STATUS_STYLE: Record<string, string> = {
  ACTIVE: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
  PENDING: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  FROZEN: "text-sky-300 border-sky-500/40 bg-sky-500/10",
  DEFAULTED: "text-red-300 border-red-500/40 bg-red-500/10",
  REJECTED: "text-red-300 border-red-500/40 bg-red-500/10",
  INCONCLUSIVE: "text-slate-300 border-slate-500/40 bg-slate-500/10",
  CLOSED: "text-slate-400 border-slate-600/40 bg-slate-600/10",
};
export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${STATUS_STYLE[status] ?? STATUS_STYLE.CLOSED}`}>
      {status}
    </span>
  );
}

export function RunwayBar({ months }: { months: number }) {
  const capped = Math.min(36, months);
  const color = months >= 24 ? "#34d399" : months >= 12 ? "#38bdf8" : months >= 6 ? "#fbbf24" : "#f87171";
  return (
    <div className="flex flex-nowrap items-center gap-2" title={`${months} months of runway`}>
      <div className="relative h-1.5 w-24 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full" style={{ width: `${(capped / 36) * 100}%`, background: color, boxShadow: `0 0 8px ${color}99` }} />
        <i className="absolute top-0 h-full w-px bg-slate-500/60" style={{ left: `${(12 / 36) * 100}%` }} />
        <i className="absolute top-0 h-full w-px bg-slate-500/60" style={{ left: `${(24 / 36) * 100}%` }} />
      </div>
      <span className="num w-9 text-right text-xs text-slate-300">{months >= 999 ? "∞" : `${months}mo`}</span>
    </div>
  );
}

export function Stat({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string }) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="label">{label}</div>
      <div className="num mt-1 truncate text-2xl font-medium tracking-tight" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="num mt-0.5 truncate text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}
