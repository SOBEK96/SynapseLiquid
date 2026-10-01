import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { CONTRACT, DEPLOYMENT, connectWallet, explorerTx, loadSnapshot, type Profile, type Snapshot } from "./lib/chain";
import { Navbar } from "./components/Navbar";
import { PoolHud } from "./components/PoolHud";
import { RatingMatrix } from "./components/RatingMatrix";
import { BorrowerRegistry } from "./components/BorrowerRegistry";
import { AssessModal } from "./components/AssessModal";
import { Calculator } from "./components/Calculator";
import { WalletActions } from "./components/WalletActions";
import { AboutDrawer } from "./components/AboutDrawer";

interface Toast { id: number; msg: string; kind: "ok" | "err"; href?: string }

export default function App() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [account, setAccount] = useState<string | undefined>();
  const [connecting, setConnecting] = useState(false);
  const [selected, setSelected] = useState<string | undefined>();
  const [assessing, setAssessing] = useState<Profile | null>(null);
  const [about, setAbout] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    const s = await loadSnapshot();
    if (!alive.current) return;
    setLoading(false);
    if (s) { setSnap(s); setFailed(false); } else setFailed(true);
  }, []);

  useEffect(() => {
    alive.current = true;
    void refresh();
    // 60 s and only while visible: the public RPC is rate limited (~30 requests/minute)
    const t = window.setInterval(() => { if (!document.hidden) void refresh(); }, 60000);
    return () => { alive.current = false; window.clearInterval(t); };
  }, [refresh]);

  const notify = useCallback((msg: string, kind: "ok" | "err" = "ok", href?: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind, href }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 7000);
  }, []);

  const connect = async () => {
    setConnecting(true);
    try { setAccount(await connectWallet()); } catch (e) { notify(e instanceof Error ? e.message : "Wallet connection failed", "err"); }
    finally { setConnecting(false); }
  };

  const borrowers = snap?.borrowers ?? [];
  const sel = useMemo(() => borrowers.find((b) => b.borrower === selected) ?? borrowers.find((b) => b.status === "ACTIVE") ?? borrowers[0], [borrowers, selected]);
  const mine = account ? borrowers.find((b) => b.borrower.toLowerCase() === account.toLowerCase()) : undefined;
  const owed = mine && snap ? snap.schedules[mine.borrower.toLowerCase()]?.total_owed : undefined;

  return (
    <div className="min-h-full">
      <Navbar account={account} onConnect={connect} onDisconnect={() => setAccount(undefined)} busy={connecting} onAbout={() => setAbout(true)} />
      <main className="mx-auto flex max-w-[1400px] flex-col gap-4 px-4 py-5 lg:px-6">
        {!CONTRACT && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            <AlertTriangle size={16} /> No contract recorded. Run <code className="num">scripts/deploy.py</code> then rebuild, or set <code className="num">VITE_CONTRACT_ADDRESS</code>.
          </div>
        )}
        {CONTRACT && failed && !snap && (
          <div className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
            <AlertTriangle size={16} className="text-amber-300" /> Studio Next RPC did not answer; retrying every 60 s.
          </div>
        )}

        <PoolHud pool={snap?.pool ?? null} />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <RatingMatrix highlight={sel?.rating} />
          <BorrowerRegistry borrowers={borrowers} schedules={snap?.schedules ?? {}} selected={sel?.borrower}
            onSelect={setSelected} onAssess={setAssessing} loading={loading} />
        </div>

        <Calculator rating={sel?.rating ?? "AAA"} borrower={sel} utilisationBps={snap?.pool.utilization_bps ?? 0} />
        <WalletActions account={account} mine={mine} owed={owed} notify={notify} refresh={() => void refresh()} />

        {DEPLOYMENT.transactions && DEPLOYMENT.transactions.length > 0 && (
          <section className="panel">
            <header className="panel-head"><h2 className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">On-chain proofs</h2>
              <span className="label">{DEPLOYMENT.transactions.length} transactions</span></header>
            <ul className="scroll-thin max-h-48 divide-y divide-slate-800/70 overflow-y-auto">
              {DEPLOYMENT.transactions.map((t) => (
                <li key={t.hash} className="flex flex-nowrap items-center justify-between gap-3 px-4 py-2 text-xs">
                  <span className="truncate text-slate-300">{t.label}</span>
                  <a href={explorerTx(t.hash)} target="_blank" rel="noreferrer" className="num flex shrink-0 items-center gap-1 text-sky-400 hover:text-sky-300">
                    {t.hash.slice(0, 10)}…{t.hash.slice(-6)} <ExternalLink size={11} /></a>
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer className="pb-6 pt-2 text-center text-[11px] text-slate-600">
          SynapseLiquid · GenLayer Studio Next (chain 61997) · test network, no market value. Ratings are model-assisted and bounded by deterministic corridors; not investment advice.
        </footer>
      </main>

      {about && <AboutDrawer onClose={() => setAbout(false)} />}

      {assessing && (
        <AssessModal profile={assessing} account={account} usdPerGen={snap?.pool.usd_per_gen ?? 250000}
          onClose={() => setAssessing(null)} onConnect={setAccount} onDone={() => void refresh()} />
      )}

      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`animate-fadeUp pointer-events-auto rounded-md border px-3 py-2 text-xs shadow-lg backdrop-blur ${t.kind === "ok" ? "border-emerald-500/40 bg-emerald-950/80 text-emerald-200" : "border-red-500/40 bg-red-950/80 text-red-200"}`}>
            {t.msg} {t.href && <a href={t.href} target="_blank" rel="noreferrer" className="underline">view</a>}
          </div>
        ))}
      </div>
    </div>
  );
}
