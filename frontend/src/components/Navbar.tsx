import { ExternalLink, LogOut, Wallet } from "lucide-react";
import { CONTRACT, explorerAddress } from "../lib/chain";

export function Navbar({ account, onConnect, onDisconnect, busy }: {
  account?: string; onConnect: () => void; onDisconnect: () => void; busy: boolean;
}) {
  return (
    <nav className="sticky top-0 z-30 flex h-16 flex-nowrap items-center justify-between gap-4 whitespace-nowrap border-b border-slate-800/80 bg-slate-950/85 px-5 backdrop-blur-md">
      <div className="flex flex-nowrap items-center gap-3 whitespace-nowrap">
        <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#0a1330" stroke="#1e3a8a" />
          <path d="M6 21 12 13l5 5 9-11" fill="none" stroke="#34d399" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[15px] font-semibold tracking-tight text-slate-100">
          Synapse<span className="text-emerald-400">Liquid</span>
        </span>
        <span className="hidden whitespace-nowrap text-[10px] uppercase tracking-[0.2em] text-slate-500 lg:inline">Credit Terminal</span>
      </div>

      <div className="flex flex-nowrap items-center gap-3 whitespace-nowrap">
        <span className="flex flex-nowrap items-center gap-2 whitespace-nowrap rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-300">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulseDot rounded-full bg-emerald-400" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          Studio Next <span className="text-emerald-500/60">•</span> <span className="num">61997</span>
        </span>

        {CONTRACT ? (
          <a href={explorerAddress(CONTRACT)} target="_blank" rel="noreferrer"
             className="flex flex-nowrap items-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700/80 px-3 py-1.5 text-xs text-slate-300 transition hover:border-sky-500/60 hover:text-sky-300">
            Contract <span className="num text-slate-400">{CONTRACT.slice(0, 6)}…{CONTRACT.slice(-4)}</span>
            <ExternalLink size={12} />
          </a>
        ) : (
          <span className="whitespace-nowrap rounded-md border border-dashed border-slate-700 px-3 py-1.5 text-xs text-slate-500">No contract deployed</span>
        )}

        {account ? (
          <button onClick={onDisconnect} title="Disconnect"
            className="flex flex-nowrap items-center gap-2 whitespace-nowrap rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 transition hover:border-red-500/50">
            <span className="num">{account.slice(0, 6)}…{account.slice(-4)}</span><LogOut size={13} />
          </button>
        ) : (
          <button onClick={onConnect} disabled={busy}
            className="flex flex-nowrap items-center gap-2 whitespace-nowrap rounded-md bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-sky-400 disabled:opacity-60">
            <Wallet size={14} />{busy ? "Connecting…" : "Connect Wallet"}
          </button>
        )}
      </div>
    </nav>
  );
}
