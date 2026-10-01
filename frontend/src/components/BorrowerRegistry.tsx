import { useState } from "react";
import { Building2, LayoutGrid, Rows3, Gavel } from "lucide-react";
import type { Profile, Schedule } from "../lib/chain";
import { fromAtto, hueFor, pct, usd } from "../lib/finance";
import { Panel, RatingBadge, RunwayBar, StatusPill } from "./ui";

interface Props {
  borrowers: Profile[];
  schedules: Record<string, Schedule>;
  selected?: string;
  onSelect: (key: string) => void;
  onAssess: (p: Profile) => void;
  loading: boolean;
}

const dscrText = (p: Profile) => (p.rating === "UNRATED" ? "—" : p.dscr_ratio >= 99900 ? "∞" : `${(p.dscr_ratio / 100).toFixed(2)}x`);

function Action({ p, onAssess }: { p: Profile; onAssess: (p: Profile) => void }) {
  if (p.status !== "PENDING") return <span className="text-[11px] text-slate-600">—</span>;
  return (
    <button onClick={(e) => { e.stopPropagation(); onAssess(p); }}
      className="flex flex-nowrap items-center gap-1.5 whitespace-nowrap rounded border border-amber-400/50 bg-amber-400/10 px-2.5 py-1 text-[11px] font-semibold text-amber-200 transition hover:bg-amber-400/20">
      <Gavel size={12} />Assess Credit
    </button>
  );
}

export function BorrowerRegistry({ borrowers, schedules, selected, onSelect, onAssess, loading }: Props) {
  const [view, setView] = useState<"table" | "cards">("table");
  const toggle = (v: "table" | "cards", icon: JSX.Element) => (
    <button onClick={() => setView(v)} aria-pressed={view === v} title={v}
      className={`rounded p-1.5 transition ${view === v ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300"}`}>{icon}</button>
  );

  return (
    <Panel title="Corporate Borrower Registry" icon={<Building2 size={13} className="text-sky-400" />}
      right={<div className="flex gap-1">{toggle("table", <Rows3 size={14} />)}{toggle("cards", <LayoutGrid size={14} />)}</div>}>
      {borrowers.length === 0 ? (
        <div className="px-4 py-10 text-center text-sm text-slate-500">
          {loading ? "Reading borrower registry from Studio Next…" : "No borrowers registered on this contract yet."}
        </div>
      ) : view === "table" ? (
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="label text-left">
                <th className="px-4 py-2 font-medium">Entity</th><th className="font-medium">Rating</th><th className="font-medium">Status</th>
                <th className="text-right font-medium">Rate</th><th className="text-right font-medium">DSCR</th>
                <th className="pl-6 font-medium">Runway</th><th className="text-right font-medium">ARR</th>
                <th className="text-right font-medium">Drawn / Limit</th><th className="px-4 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {borrowers.map((p) => (
                <tr key={p.borrower} onClick={() => onSelect(p.borrower)}
                    className={`cursor-pointer border-t border-slate-800/70 transition hover:bg-slate-800/40 ${selected === p.borrower ? "bg-slate-800/50" : ""}`}>
                  <td className="px-4 py-3">
                    <div className="whitespace-nowrap font-medium text-slate-100">{p.company_name}</div>
                    <div className="num text-[10px] text-slate-500">{p.borrower.slice(0, 8)}…{p.borrower.slice(-4)}</div>
                  </td>
                  <td><RatingBadge rating={p.rating} /></td>
                  <td><StatusPill status={p.status} /></td>
                  <td className="num text-right" style={{ color: hueFor(p.rating) }}>{p.interest_rate_bps ? pct(p.interest_rate_bps) : "—"}</td>
                  <td className="num text-right text-slate-200">{dscrText(p)}</td>
                  <td className="pl-6">{p.rating === "UNRATED" ? <span className="num text-xs text-slate-600">awaiting consensus</span> : <RunwayBar months={p.runway_months} />}</td>
                  <td className="num text-right text-slate-300">{p.arr_usd ? usd(p.arr_usd) : "—"}</td>
                  <td className="num whitespace-nowrap text-right text-slate-300">
                    {fromAtto(p.borrowed_amount, 3)} <span className="text-slate-600">/</span> {fromAtto(p.credit_limit, 3)}
                  </td>
                  <td className="px-4 text-right"><Action p={p} onAssess={onAssess} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-3 p-3 md:grid-cols-2 xl:grid-cols-3">
          {borrowers.map((p) => {
            const hue = hueFor(p.rating);
            const s = schedules[p.borrower.toLowerCase()];
            return (
              <article key={p.borrower} onClick={() => onSelect(p.borrower)}
                className={`animate-fadeUp relative cursor-pointer overflow-hidden rounded-lg border bg-slate-950/60 p-4 transition hover:bg-slate-900/80 ${selected === p.borrower ? "border-sky-500/50" : "border-slate-800"}`}>
                <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full blur-3xl" style={{ background: `${hue}22` }} />
                <div className="flex flex-nowrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold text-slate-100">{p.company_name}</h3>
                    <div className="mt-1"><StatusPill status={p.status} /></div>
                  </div>
                  <RatingBadge rating={p.rating} size="lg" />
                </div>
                <dl className="num mt-4 grid grid-cols-3 gap-2 text-xs">
                  <div><dt className="label">APR</dt><dd className="mt-0.5 text-sm" style={{ color: hue }}>{p.interest_rate_bps ? pct(p.interest_rate_bps) : "—"}</dd></div>
                  <div><dt className="label">DSCR</dt><dd className="mt-0.5 text-sm text-slate-200">{dscrText(p)}</dd></div>
                  <div><dt className="label">ARR</dt><dd className="mt-0.5 text-sm text-slate-200">{p.arr_usd ? usd(p.arr_usd) : "—"}</dd></div>
                </dl>
                <div className="mt-3">
                  <div className="label mb-1">Runway</div>
                  {p.rating === "UNRATED" ? <span className="num text-xs text-slate-600">awaiting consensus</span> : <RunwayBar months={p.runway_months} />}
                </div>
                <div className="num mt-3 flex flex-nowrap items-center justify-between gap-2 border-t border-slate-800 pt-3 text-xs text-slate-400">
                  <span className="whitespace-nowrap">Drawn {fromAtto(p.borrowed_amount, 3)} / {fromAtto(p.credit_limit, 3)} GEN</span>
                  {s && s.overdue ? <span className="font-semibold text-red-400">OVERDUE</span> : <Action p={p} onAssess={onAssess} />}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
