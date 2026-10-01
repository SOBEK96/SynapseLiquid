import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Circle, Cpu, Database, Loader2, Terminal, TrendingUp, X } from "lucide-react";
import { connectWallet, explorerTx, loadSnapshot, read, write, type Profile } from "../lib/chain";
import { fromAtto, pct, underwrite, usd, type Telemetry } from "../lib/finance";
import { RatingBadge } from "./ui";

type LogLine = { t: string; msg: string; tone?: "ok" | "warn" | "err" | "dim" };
const STAGES = [
  { n: 1, title: "Cash Flow Telemetry Ingestion", icon: Database },
  { n: 2, title: "Multi-Validator Financial Ratio Extraction", icon: Cpu },
  { n: 3, title: "Autonomous Rate Curve Settlement", icon: TrendingUp },
];

// Canonical JSON identical to Python's json.dumps(sort_keys=True, separators=(",", ":"))
function canon(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canon).join(",")}]`;
  if (v && typeof v === "object")
    return `{${Object.keys(v as object).sort().map((k) => `${JSON.stringify(k)}:${canon((v as Record<string, unknown>)[k])}`).join(",")}}`;
  return JSON.stringify(v);
}
async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function AssessModal({ profile, account, usdPerGen, onClose, onDone, onConnect }: {
  profile: Profile; account?: string; usdPerGen: number; onClose: () => void; onDone: () => void; onConnect: (a: string) => void;
}) {
  const [stage, setStage] = useState(0); // 0 idle, 1..3 active, 4 complete
  const [log, setLog] = useState<LogLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Profile | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const push = (msg: string, tone?: LogLine["tone"]) =>
    setLog((l) => [...l, { t: new Date().toISOString().slice(11, 19), msg, tone }]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [log]);
  useEffect(() => {
    push(`Borrower ${profile.company_name} · ${profile.borrower}`, "dim");
    push(`Telemetry source: ${profile.metadata_uri}`, "dim");
    push("Awaiting steward authorisation. Validators will independently re-fetch and re-derive every figure.", "dim");
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function execute() {
    setBusy(true);
    try {
      let acct = account;
      if (!acct) { acct = await connectWallet(); onConnect(acct); }

      setStage(1);
      push("STAGE 1 · fetching cash-flow telemetry…");
      let tel: Telemetry | null = null;
      try {
        const res = await fetch(profile.metadata_uri, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        tel = (await res.json()) as Telemetry;
        push(`telemetry received: revenue ${usd(tel.monthly_revenue_usd)}/mo · opex ${usd(tel.monthly_opex_usd)}/mo · treasury ${usd(tel.treasury_usd)}`, "ok");
        if (tel.transactions && tel.proof_sha256) {
          const d = await sha256Hex(canon(tel.transactions));
          const sum = tel.transactions.reduce((s, t) => s + t.amount_usd, 0);
          const dup = new Set(tel.transactions.map((t) => t.tx)).size !== tel.transactions.length;
          push(`proof digest ${d.slice(0, 16)}… ${d === tel.proof_sha256.toLowerCase().replace(/^0x/, "") ? "MATCHES committed sha256" : "MISMATCH — fraud path (bond slash)"}`, d === tel.proof_sha256 ? "ok" : "err");
          push(`${tel.transactions.length} on-chain inflow records · ${usd(sum)} verified · ${dup ? "DUPLICATE tx ids" : "no duplicate tx ids"}`, dup ? "err" : "ok");
        }
      } catch {
        push("browser-side preview unavailable (feed not CORS-readable); validators fetch server-side", "warn");
      }

      setStage(2);
      push("STAGE 2 · deterministic ratio extraction (integer arithmetic)");
      if (tel) {
        const reqUsd = Math.floor(Number((BigInt(profile.requested_limit) * BigInt(usdPerGen)) / 10n ** 18n));
        const u = underwrite(tel, reqUsd);
        push(`ARR = 12 × revenue = ${usd(u.arr)}`, "ok");
        push(`Runway = treasury ÷ net burn = ${u.runway >= 999 ? "unbounded" : `${u.runway.toFixed(2)} months`}`, "ok");
        push(`DSCR = NOI ÷ annual debt service = ${u.dscr.toFixed(2)}x`, "ok");
        push(`on-chain corroboration ${pct(u.corroborationBps, 1)} · mathematical ceiling ${u.ceiling}`, "ok");
      }
      push("submitting assess_credit_consensus — validators + LLM committee deliberate (may take a few minutes)…");

      setStage(3);
      push("STAGE 3 · awaiting multi-LLM consensus under the Equivalence Principle…");
      const out = await write(acct, "assess_credit_consensus", [profile.borrower], 0n, (h) =>
        push(`tx ${h.slice(0, 18)}… ${explorerTx(h)}`, "dim"));
      push(`consensus reached · ${out.status}`, "ok");
      const fresh = await read<Profile>("get_credit_profile", [profile.borrower]);
      if (fresh) {
        setResult(fresh);
        push(`SETTLED → rating ${fresh.rating} · ${pct(fresh.interest_rate_bps)} APR · DSCR ${(fresh.dscr_ratio / 100).toFixed(2)}x · limit ${fromAtto(fresh.credit_limit, 4)} GEN · status ${fresh.status}`,
          fresh.status === "REJECTED" ? "err" : "ok");
      }
      setStage(4);
      await loadSnapshot();
      onDone();
    } catch (e) {
      push(e instanceof Error ? e.message : "assessment failed", "err");
      setStage(0);
    } finally {
      setBusy(false);
    }
  }

  const tone = (t?: LogLine["tone"]) => t === "ok" ? "text-emerald-300" : t === "warn" ? "text-amber-300" : t === "err" ? "text-red-400" : t === "dim" ? "text-slate-500" : "text-slate-300";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Credit assessment">
      <div className="animate-fadeUp flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-slate-700 bg-slate-950 shadow-2xl shadow-sky-950/50">
        <header className="flex flex-nowrap items-center justify-between gap-3 border-b border-slate-800 px-5 py-3">
          <div className="flex min-w-0 flex-nowrap items-center gap-3">
            <Terminal size={16} className="text-sky-400" />
            <h3 className="truncate text-sm font-semibold text-slate-100">Live Credit Assessment · {profile.company_name}</h3>
            <RatingBadge rating={result?.rating ?? profile.rating} size="sm" />
          </div>
          <button onClick={onClose} disabled={busy} aria-label="Close" className="rounded p-1 text-slate-500 hover:text-slate-200 disabled:opacity-40"><X size={16} /></button>
        </header>

        <ol className="grid grid-cols-3 gap-2 border-b border-slate-800 px-5 py-4">
          {STAGES.map((s) => {
            const done = stage > s.n || stage === 4, active = stage === s.n;
            const Icon = done ? CheckCircle2 : active ? Loader2 : Circle;
            return (
              <li key={s.n} className={`rounded-md border p-2.5 transition ${done ? "border-emerald-500/40 bg-emerald-500/5" : active ? "border-sky-500/50 bg-sky-500/5" : "border-slate-800"}`}>
                <div className="flex flex-nowrap items-center gap-1.5">
                  <Icon size={14} className={done ? "text-emerald-400" : active ? "animate-spin text-sky-400" : "text-slate-600"} />
                  <span className="label !text-slate-500">Stage {s.n}</span>
                </div>
                <div className="mt-1 text-[11px] font-medium leading-snug text-slate-300">{s.title}</div>
              </li>
            );
          })}
        </ol>

        <div className="scroll-thin num min-h-[200px] flex-1 overflow-y-auto bg-black/40 px-5 py-3 text-[11.5px] leading-relaxed" aria-live="polite">
          {log.map((l, i) => (
            <div key={i} className={`flex gap-3 ${tone(l.tone)}`}><span className="shrink-0 text-slate-600">{l.t}</span><span className="break-all">{l.msg}</span></div>
          ))}
          <div ref={endRef} />
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-5 py-3">
          <span className="text-[11px] text-slate-500">Any steward may trigger consensus · bond is slashed only on provably impossible telemetry.</span>
          {stage === 4 ? (
            <button onClick={onClose} className="rounded-md bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400">Close</button>
          ) : (
            <button onClick={execute} disabled={busy}
              className="flex flex-nowrap items-center gap-2 whitespace-nowrap rounded-md bg-sky-500 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-sky-400 disabled:opacity-60">
              {busy && <Loader2 size={14} className="animate-spin" />}
              {account ? "Execute Validator Credit Assessment" : "Connect Wallet & Execute Assessment"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
