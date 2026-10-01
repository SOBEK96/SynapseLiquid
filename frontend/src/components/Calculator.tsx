import { useMemo, useState } from "react";
import { Calculator as CalcIcon } from "lucide-react";
import { TIERS, amortisation, fromAtto, hueFor, tierFor, totalInterest } from "../lib/finance";
import type { Profile } from "../lib/chain";
import { Panel } from "./ui";

export function Calculator({ rating, borrower, utilisationBps }: { rating: string; borrower?: Profile; utilisationBps: number }) {
  const [amount, setAmount] = useState(1.5);
  const [override, setOverride] = useState<string | undefined>();
  const active = override ?? (tierFor(rating) ? rating : "AAA");
  const tier = tierFor(active) ?? TIERS[0];
  const limit = borrower && borrower.rating === active ? Number(borrower.credit_limit) / 1e18 : 4;
  const max = Math.max(0.1, limit || 4);
  const amt = Math.min(amount, max);
  // surcharge mirrors the contract: 0 below 80% utilisation, up to +500 bps at 100%
  const surcharge = utilisationBps <= 8000 ? 0 : Math.min(500, Math.floor(((utilisationBps - 8000) * 500) / 2000));
  const rate = tier.rateBps + surcharge;
  const rows = useMemo(() => amortisation(amt, rate), [amt, rate]);
  const interest = totalInterest(rows);
  const peak = Math.max(...rows.map((r) => r.payment), 1e-9);
  const hue = hueFor(active);

  return (
    <Panel title="Amortisation & Repayment Calculator" icon={<CalcIcon size={13} className="text-amber-300" />}
      right={borrower ? <span className="label">{borrower.company_name}</span> : undefined}>
      <div className="grid gap-5 p-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
        <div className="space-y-4">
          <div>
            <div className="mb-1.5 flex flex-nowrap items-baseline justify-between"><span className="label">Loan amount</span>
              <span className="num text-lg" style={{ color: hue }}>{amt.toFixed(3)} GEN</span></div>
            <input type="range" aria-label="Loan amount in GEN" min={0.05} max={max} step={0.05} value={amt} onChange={(e) => setAmount(Number(e.target.value))} className="w-full" />
            <div className="num mt-1 flex justify-between text-[10px] text-slate-600"><span>0.05</span><span>{max.toFixed(2)} GEN {borrower && borrower.rating === active ? "(credit limit)" : "(illustrative)"}</span></div>
          </div>
          <div>
            <div className="label mb-1.5">Rating tier</div>
            <div className="flex flex-wrap gap-1.5">
              {TIERS.map((t) => (
                <button key={t.rating} onClick={() => setOverride(t.rating)} aria-pressed={active === t.rating}
                  className="num rounded border px-2 py-1 text-[11px] font-bold transition"
                  style={{ color: t.hue, borderColor: active === t.rating ? t.hue : "#1e293b", background: active === t.rating ? `${t.hue}1f` : "transparent" }}>{t.rating}</button>
              ))}
            </div>
          </div>
          <dl className="num grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
            <div><dt className="label">APR</dt><dd className="text-base" style={{ color: hue }}>{(rate / 100).toFixed(2)}%</dd></div>
            <div><dt className="label">Term</dt><dd className="text-base text-slate-200">12 mo</dd></div>
            <div><dt className="label">First payment</dt><dd className="text-base text-slate-200">{rows[0]?.payment.toFixed(4) ?? "—"}</dd></div>
            <div><dt className="label">Total interest</dt><dd className="text-base text-slate-200">{interest.toFixed(4)}</dd></div>
          </dl>
          {surcharge > 0 && <p className="text-[11px] text-amber-300">Utilisation above the 80% kink adds +{surcharge} bps at assessment.</p>}
          {borrower && borrower.rating !== active && borrower.rating !== "UNRATED" && (
            <p className="text-[11px] text-slate-500">{borrower.company_name} is rated {borrower.rating} ({(borrower.interest_rate_bps / 100).toFixed(2)}% APR, limit {fromAtto(borrower.credit_limit, 3)} GEN).</p>
          )}
        </div>

        <div className="min-w-0">
          <div className="label mb-2">Monthly debt service · interest vs principal (GEN)</div>
          <div className="flex h-40 items-end gap-1.5" role="img" aria-label="Monthly payment chart">
            {rows.map((r) => (
              <div key={r.month} className="group relative flex h-full flex-1 flex-col justify-end" title={`Month ${r.month}: ${r.payment.toFixed(4)} GEN`}>
                <div className="rounded-t-sm" style={{ height: `${(r.interest / peak) * 100}%`, minHeight: 2, background: hue }} />
                <div style={{ height: `${(r.principal / peak) * 100}%`, background: `${hue}40` }} />
              </div>
            ))}
          </div>
          <div className="num mt-1 flex gap-1.5 text-[10px] text-slate-600">{rows.map((r) => <span key={r.month} className="flex-1 text-center">{r.month}</span>)}</div>
          <div className="scroll-thin mt-3 max-h-40 overflow-y-auto">
            <table className="num w-full text-[11px]">
              <thead className="sticky top-0 bg-slate-900"><tr className="label text-right"><th className="py-1 text-left font-medium">Mo</th><th className="font-medium">Interest</th><th className="font-medium">Principal</th><th className="font-medium">Payment</th><th className="font-medium">Balance</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.month} className="border-t border-slate-800/60 text-right text-slate-400">
                  <td className="py-1 text-left text-slate-500">{r.month}</td><td style={{ color: hue }}>{r.interest.toFixed(5)}</td><td>{r.principal.toFixed(4)}</td><td className="text-slate-200">{r.payment.toFixed(4)}</td><td>{r.balance.toFixed(4)}</td></tr>))}</tbody>
            </table>
          </div>
        </div>
      </div>
    </Panel>
  );
}
