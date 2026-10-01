import { Activity, ShieldCheck } from "lucide-react";
import type { Pool } from "../lib/chain";
import { fromAtto, gen, pct } from "../lib/finance";
import { Panel, Stat } from "./ui";

export function PoolHud({ pool }: { pool: Pool | null }) {
  const util = pool ? pool.utilization_bps / 100 : 0;
  return (
    <Panel title="Pool Health" icon={<Activity size={13} className="text-emerald-400" />}
      right={<span className="label">live · gen_call</span>}>
      <div className="grid grid-cols-2 divide-x divide-slate-800/80 lg:grid-cols-4">
        <Stat label="Total Pool Liquidity" value={pool ? `${fromAtto(pool.lp_nav ?? pool.total_deposited, 3)}` : "—"} sub={pool && pool.delinquent_principal && pool.delinquent_principal !== "0" ? "GEN · marked down for delinquent loans" : "GEN · LP net asset value"} />
        <Stat label="Active Debt Deployed" value={pool ? `${fromAtto(pool.borrowed_liquidity, 3)}` : "—"} sub={pool ? `${util.toFixed(1)}% utilisation` : "GEN"} accent="#38bdf8" />
        <Stat label="Blended LP APY" value={pool ? pct(pool.lp_apy_bps) : "—"} sub="net of 10% reserve cut" accent="#34d399" />
        <Stat label="Protocol Default Rate" value={pool ? pct(pool.default_rate_bps, 1) : "—"} sub={pool ? `${fromAtto(pool.cumulative_originated, 2)} GEN originated` : ""} accent={pool && pool.default_rate_bps > 0 ? "#f87171" : "#e2e8f0"} />
      </div>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2 border-t border-slate-800/80 px-4 py-3">
        <div className="flex min-w-[220px] flex-1 flex-nowrap items-center gap-3">
          <span className="label whitespace-nowrap">Utilisation</span>
          <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-700" style={{ width: `${Math.min(100, util)}%` }} />
            <i className="absolute top-0 h-full w-px bg-amber-400/80" style={{ left: "60%" }} title="60% protocol utilisation cap" />
          </div>
          <span className="num text-xs text-slate-400">{util.toFixed(1)}%</span>
        </div>
        <div className="flex flex-nowrap items-center gap-2 whitespace-nowrap text-xs text-slate-400">
          <ShieldCheck size={13} className="text-emerald-400" />
          Insurance reserve <span className="num text-slate-200">{pool ? gen(pool.insurance_reserve).toFixed(4) : "—"}</span> GEN
          <span className="mx-1 text-slate-700">|</span>
          Bonds held <span className="num text-slate-200">{pool ? gen(pool.bonds_held).toFixed(4) : "—"}</span> GEN
          <span className="mx-1 text-slate-700">|</span>
          $<span className="num text-slate-200">{pool ? pool.usd_per_gen.toLocaleString() : "—"}</span>/GEN notional
        </div>
      </div>
    </Panel>
  );
}
