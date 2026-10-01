import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { BookOpen, Check, Copy, ExternalLink, Github, Landmark, Layers, Scale, ShieldCheck, X } from "lucide-react";
import { CONTRACT, explorerAddress } from "../lib/chain";
import { TIERS, pct } from "../lib/finance";

const REPO = "https://github.com/SOBEK96/SynapseLiquid";

const TABS = [
  { id: "overview", n: 1, label: "Overview & Mission", icon: Landmark },
  { id: "arch", n: 2, label: "GenVM Consensus Architecture", icon: Layers },
  { id: "risk", n: 3, label: "Quantitative Risk Formulas", icon: Scale },
  { id: "safe", n: 4, label: "Economic Security & Trust Model", icon: ShieldCheck },
] as const;
type TabId = (typeof TABS)[number]["id"];

const H = ({ children }: { children: ReactNode }) => (
  <h3 className="mb-2 mt-6 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 first:mt-0">{children}</h3>
);
const P = ({ children }: { children: ReactNode }) => <p className="text-sm leading-relaxed text-slate-300">{children}</p>;
const Mono = ({ children }: { children: ReactNode }) => <span className="num text-slate-100">{children}</span>;
const Formula = ({ children }: { children: ReactNode }) => (
  <pre className="num overflow-x-auto rounded-md border border-slate-800 bg-black/40 px-4 py-3 text-[13px] leading-relaxed text-emerald-300">{children}</pre>
);

function Overview() {
  return (
    <>
      <H>The missing market</H>
      <P>
        Web3 companies earn real revenue (subscriptions, protocol fees, treasury inflows) yet have no institutional way to
        borrow against it. Crypto lending is almost entirely over-collateralised, which leaves the corporate debt market that
        underpins every mature economy, measured in the trillions of dollars, without an on-chain counterpart.
      </P>
      <H>What SynapseLiquid does</H>
      <P>
        An autonomous <Mono>under-collateralised</Mono> credit protocol. A startup posts a proportional bond and a
        cash-flow telemetry feed; independent GenVM validators re-derive its financial ratios and reach consensus on a credit
        rating from <Mono>AAA</Mono> to <Mono>C</Mono>. The rating alone sets the interest rate, credit limit and repayment
        schedule, and liquidity providers earn the resulting yield from a shared pool.
      </P>
      <div className="mt-5 grid grid-cols-3 gap-2">
        {[["7", "rating tiers"], ["4% – 35%", "APR range"], ["12 mo", "absolute maturity"]].map(([v, l]) => (
          <div key={l} className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2.5">
            <div className="num text-base text-sky-300">{v}</div>
            <div className="label mt-0.5">{l}</div>
          </div>
        ))}
      </div>
      <H>Read this first</H>
      <P>
        This deployment runs on a <Mono>test network</Mono>. Cash-flow telemetry is <Mono>self-asserted</Mono> JSON used to
        exercise multi-validator consensus; it is not an attested data source and ratings issued here are not evidence of
        anyone&apos;s creditworthiness. See the Economic Security tab.
      </P>
    </>
  );
}

const STEPS: { t: string; d: ReactNode }[] = [
  { t: "Address-Bound Telemetry Ingestion", d: <>The borrower publishes a JSON financial feed (revenue, opex, burn, treasury, on-chain inflow log). It must name the borrower it rates in <Mono>borrower_address</Mono>; a file served for another address reverts <Mono>ERR_BORROWER_MISMATCH</Mono>. Only public https DNS hosts are fetched.</> },
  { t: "Deterministic Pre-flight & Bounded Ceilings", d: <>Every validator runs the same integer arithmetic: negative or impossible figures, duplicate transactions and a broken <Mono>sha256</Mono> proof digest are fraud (bond slashed); an unreachable or malformed feed is fail-closed (bond refunded). Runway, DSCR and ARR then fix a hard rating <em>ceiling</em>.</> },
  { t: "GenVM Multi-Validator Equivalence Consensus", d: <>The leader and validators each fetch and re-derive the figures, and an LLM credit committee may only <em>lower</em> the rating by up to two notches. Validators agree only if the outcome matches, the metrics are within 2% and the notches within one. The contract then recomputes the ceiling itself, so no model output can raise a rating.</> },
  { t: "Autonomous Liquidity Pool & Amortization Settlement", d: <>The rating binds the APR, credit limit and a 12-month amortizing schedule. Drawdowns come from the LP pool; interest is split 90% to LP net asset value and 10% to an insurance reserve. Delinquent loans are marked down and liquidated: bond, then reserve, then LPs.</> },
];

function Architecture() {
  return (
    <>
      <H>Four-step pipeline</H>
      <ol className="space-y-3">
        {STEPS.map((s, i) => (
          <li key={s.t} className="flex gap-3 rounded-md border border-slate-800 bg-slate-950/50 p-3">
            <span className="num flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-sky-500/50 bg-sky-500/10 text-xs font-bold text-sky-300">{i + 1}</span>
            <div>
              <div className="text-sm font-semibold text-slate-100">{s.t}</div>
              <div className="mt-1 text-[13px] leading-relaxed text-slate-400">{s.d}</div>
            </div>
          </li>
        ))}
      </ol>
      <H>Consensus rule</H>
      <Formula>{`agree ⇔ outcome(leader) = outcome(validator)
       ∧ |metric_l − metric_v| ≤ 2%
       ∧ |notches_l − notches_v| ≤ 1`}</Formula>
    </>
  );
}

function Risk() {
  return (
    <>
      <H>Core ratios</H>
      <Formula>{`DSCR    = Net Operating Income / Debt Service
          (AAA requires ≥ 2.5x)

Runway  = Liquid Treasury / Net Monthly Burn
          (AAA requires ≥ 24 months)

ARR     = 12 × monthly revenue   (AAA requires ≥ $1,000,000)`}</Formula>
      <P>
        Annual debt service is existing service plus the requested line at a <Mono>12%</Mono> reference coupon and a
        36-month straight-line amortisation. Net burn is outflows less revenue, and runway is unbounded when cash-flow
        positive. Every ratio is computed in integers, so each validator derives identical values.
      </P>
      <H>Risk matrix</H>
      <div className="overflow-hidden rounded-md border border-slate-800">
        <table className="num w-full text-xs">
          <thead className="bg-slate-950/70">
            <tr className="label text-left"><th className="px-3 py-2 font-medium">Tier</th><th className="font-medium">Grade</th><th className="text-right font-medium">APR</th><th className="px-3 text-right font-medium">Advance / ARR</th></tr>
          </thead>
          <tbody>
            {TIERS.map((t) => (
              <tr key={t.rating} className="border-t border-slate-800/70">
                <td className="px-3 py-1.5 font-bold" style={{ color: t.hue }}>{t.rating}</td>
                <td className="font-sans text-slate-400">{t.label}</td>
                <td className="text-right text-slate-200">{pct(t.rateBps)}</td>
                <td className="px-3 text-right text-slate-400">{pct(t.advanceBps, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <H>Corridor rules</H>
      <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-slate-300">
        <li>Investment grade (AAA to BBB) needs Runway ≥ 12 mo and DSCR ≥ 1.25x; failing it bounds the rating to BB, B or C.</li>
        <li>Revenue under 10% corroborated by on-chain inflows is capped at <Mono>BB</Mono>.</li>
        <li>Limit = <Mono>min(request, ARR × advance rate, 60% of pool)</Mono>.</li>
        <li>Pool utilisation above 80% adds up to <Mono>+500 bps</Mono>, locked at assessment.</li>
      </ul>
    </>
  );
}

const SAFEGUARDS: [string, string][] = [
  ["60% global utilisation cap", "Total borrowed never exceeds 60% of pool assets across all borrowers, so Sybil identities share one budget."],
  ["30-day tranche lock + 35% amortization", "Only 50% of a line is available first. Tranche 2 needs a paid installment, 30 days since the first drawdown and 35% of the first tranche repaid as principal."],
  ["Proportional 15% bond", "Bond = max(0.1 GEN, 15% of the requested limit), slashed on provable fraud and seized on default."],
  ["Bad-debt haircut", "Loans past their due date are marked to zero in LP value, so exits cannot dump losses on the last LP."],
  ["Cooldowns and bounds", "24 h from assessment to first draw, a 72 h pause after a major liquidation, 12-month maturity, and a bounded active-borrower set."],
];

function Safeguards() {
  return (
    <>
      <H>Active safeguards</H>
      <ul className="space-y-2">
        {SAFEGUARDS.map(([t, d]) => (
          <li key={t} className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
            <div className="num text-[13px] font-semibold text-emerald-300">{t}</div>
            <div className="mt-1 text-[13px] leading-relaxed text-slate-400">{d}</div>
          </li>
        ))}
      </ul>
      <H>Testnet assumptions: disclosure</H>
      <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-4 text-[13px] leading-relaxed text-amber-100">
        <p>
          <strong>Telemetry is self-asserted.</strong> The JSON feeds are hosted by the borrower and exist to exercise GenVM
          multi-validator consensus on Studio Next. The contract proves a document names this borrower, is internally
          consistent and that validators derived the same numbers. It cannot prove the revenue is real.
        </p>
        <p className="mt-2">
          Production would require cryptographic attestations (TLSNotary proofs, issued verifiable credentials or authorised
          on-chain oracle signers), not self-submitted URLs. GEN has no market value here and nothing on this page is
          investment advice.
        </p>
      </div>
    </>
  );
}

export function AboutDrawer({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<TabId>("overview");
  const [shown, setShown] = useState(false);
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(document.activeElement);

  const close = useCallback(() => {
    setShown(false);
    window.setTimeout(onClose, 220); // let the slide-out finish
  }, [onClose]);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setShown(true));
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const back = opener.current;
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      if (back instanceof HTMLElement) back.focus();
    };
  }, [close]);

  const copy = async () => {
    if (!CONTRACT) return;
    try {
      await navigator.clipboard.writeText(CONTRACT);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable: the address is selectable below */
    }
  };

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Protocol specifications">
      <div onClick={close} className={`absolute inset-0 bg-slate-950/70 transition-opacity duration-200 ${shown ? "opacity-100" : "opacity-0"}`} />
      <aside className={`absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-slate-800 bg-slate-900/95 p-6 text-slate-200 shadow-2xl backdrop-blur-xl transition-transform duration-200 ease-out ${shown ? "translate-x-0" : "translate-x-full"}`}>
        <header className="flex flex-nowrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-nowrap items-center gap-2 whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-400">
              <BookOpen size={14} /> Protocol Specs
            </div>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-100">About SynapseLiquid</h2>
          </div>
          <button ref={closeRef} onClick={close} aria-label="Close protocol specs"
            className="rounded p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"><X size={18} /></button>
        </header>

        <div role="tablist" aria-label="Protocol sections" className="mt-5 grid grid-cols-2 gap-1.5">
          {TABS.map((t) => {
            const Icon = t.icon, on = tab === t.id;
            return (
              <button key={t.id} role="tab" id={`about-tab-${t.id}`} aria-selected={on} aria-controls={`about-panel-${t.id}`}
                onClick={() => setTab(t.id)}
                className={`flex flex-nowrap items-center gap-2 rounded-md border px-2.5 py-2 text-left text-[11px] font-medium leading-tight transition ${on ? "border-sky-500/60 bg-sky-500/10 text-sky-200" : "border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-200"}`}>
                <Icon size={14} className="shrink-0" /><span><span className="num mr-1 text-slate-500">{t.n}.</span>{t.label}</span>
              </button>
            );
          })}
        </div>

        <div role="tabpanel" id={`about-panel-${tab}`} aria-labelledby={`about-tab-${tab}`} tabIndex={0}
          className="scroll-thin mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
          {tab === "overview" && <Overview />}
          {tab === "arch" && <Architecture />}
          {tab === "risk" && <Risk />}
          {tab === "safe" && <Safeguards />}
        </div>

        <footer className="mt-4 space-y-3 border-t border-slate-800 pt-4">
          {CONTRACT && (
            <div className="flex flex-nowrap items-center gap-2">
              <code className="num min-w-0 flex-1 select-all truncate rounded border border-slate-800 bg-black/40 px-2.5 py-1.5 text-[11px] text-slate-300">{CONTRACT}</code>
              <button onClick={() => void copy()} aria-live="polite"
                className="flex shrink-0 flex-nowrap items-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700 px-2.5 py-1.5 text-xs font-medium text-slate-200 transition hover:border-sky-500 hover:text-sky-300">
                {copied ? <><Check size={13} className="text-emerald-400" />Copied</> : <><Copy size={13} />Copy Contract Address</>}
              </button>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {CONTRACT && (
              <a href={explorerAddress(CONTRACT)} target="_blank" rel="noreferrer"
                className="flex flex-nowrap items-center gap-1.5 whitespace-nowrap rounded-md bg-sky-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-sky-400">
                Studio Next Explorer <ExternalLink size={12} /></a>
            )}
            <a href={REPO} target="_blank" rel="noreferrer"
              className="flex flex-nowrap items-center gap-1.5 whitespace-nowrap rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-slate-500">
              <Github size={13} /> GitHub</a>
          </div>
        </footer>
      </aside>
    </div>
  );
}
