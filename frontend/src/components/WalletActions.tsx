import { useState } from "react";
import { Landmark } from "lucide-react";
import { write, explorerTx, type Profile } from "../lib/chain";
import { toAtto } from "../lib/finance";
import { Panel } from "./ui";

export function WalletActions({ account, mine, owed, notify, refresh }: {
  account?: string; mine?: Profile; owed?: string; notify: (m: string, kind?: "ok" | "err", href?: string) => void; refresh: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [vals, setVals] = useState({ deposit: "1", withdraw: "0", draw: "0.5", repay: "0.1" });

  const run = async (key: string, method: string, args: unknown[], value = 0n) => {
    if (!account) return notify("Connect a wallet first", "err");
    setBusy(key);
    try {
      const r = await write(account, method, args, value);
      notify(`${method} ${r.status}`, "ok", explorerTx(r.hash));
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message.slice(0, 160) : `${method} failed`, "err");
    } finally { setBusy(null); }
  };

  const row = (key: keyof typeof vals, label: string, btn: string, onClick: () => void, disabled = false) => (
    <div className="flex flex-nowrap items-end gap-2">
      <label className="min-w-0 flex-1">
        <span className="label">{label}</span>
        <input value={vals[key]} onChange={(e) => setVals({ ...vals, [key]: e.target.value })} inputMode="decimal"
          className="num mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm text-slate-100 outline-none focus:border-sky-500" />
      </label>
      <button onClick={onClick} disabled={!account || busy !== null || disabled}
        className="whitespace-nowrap rounded border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-sky-500 hover:text-sky-300 disabled:opacity-40">
        {busy === key ? "…" : btn}
      </button>
    </div>
  );
  const active = mine?.status === "ACTIVE";
  const num = (s: string) => { const n = Number(s); return Number.isFinite(n) && n >= 0 ? n : 0; };

  return (
    <Panel title="Wallet Actions" icon={<Landmark size={13} className="text-slate-400" />} right={<span className="label">{account ? "connected" : "read-only"}</span>}>
      <div className="grid gap-5 p-4 md:grid-cols-2">
        <div className="space-y-3">
          <div className="label !text-sky-400">Liquidity provider</div>
          {row("deposit", "Deposit (GEN)", "Deposit", () => run("deposit", "deposit_liquidity", [], toAtto(num(vals.deposit))), num(vals.deposit) < 0.001)}
          {row("withdraw", "Withdraw (GEN, 0 = max)", "Withdraw", () => run("withdraw", "withdraw_lp_capital", [toAtto(num(vals.withdraw))]))}
        </div>
        <div className="space-y-3">
          <div className="label !text-emerald-400">Borrower {mine ? `· ${mine.company_name}` : ""}</div>
          {row("draw", "Drawdown (GEN)", "Draw", () => run("draw", "drawdown_credit", [toAtto(num(vals.draw))]), !active || num(vals.draw) <= 0)}
          {row("repay", `Service debt (GEN)${owed ? ` · owed ${(Number(owed) / 1e18).toFixed(4)}` : ""}`, "Repay", () => run("repay", "service_debt", [], toAtto(num(vals.repay))), !mine || num(vals.repay) <= 0)}
          {!mine && account && <p className="text-[11px] text-slate-500">This wallet has no credit profile.</p>}
        </div>
      </div>
    </Panel>
  );
}
