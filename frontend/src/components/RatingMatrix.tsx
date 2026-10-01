import { useState } from "react";
import { LineChart } from "lucide-react";
import { TIERS, pct } from "../lib/finance";
import { Panel } from "./ui";

const W = 640, H = 230, PX = 44, PY = 28;

export function RatingMatrix({ highlight, onPick }: { highlight?: string; onPick?: (r: string) => void }) {
  const [hover, setHover] = useState<string | undefined>();
  const active = hover ?? highlight;
  const maxRate = 4000;
  const x = (i: number) => PX + (i * (W - PX * 2)) / (TIERS.length - 1);
  const y = (bps: number) => H - PY - (bps / maxRate) * (H - PY * 2);
  const path = TIERS.map((t, i) => `${i ? "L" : "M"}${x(i)},${y(t.rateBps)}`).join(" ");
  const area = `${path} L${x(TIERS.length - 1)},${H - PY} L${x(0)},${H - PY} Z`;
  const aaa = TIERS[0].rateBps;

  return (
    <Panel title="Credit Rating Matrix" icon={<LineChart size={13} className="text-sky-400" />}
      right={<span className="label">APR by tier · spread to AAA</span>}>
      <div className="px-3 pt-3">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Interest rate curve from AAA to C">
          <defs>
            <linearGradient id="curveFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="curveStroke" x1="0" x2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="55%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#f87171" />
            </linearGradient>
          </defs>
          {[0, 1000, 2000, 3000, 4000].map((g) => (
            <g key={g}>
              <line x1={PX} x2={W - PX} y1={y(g)} y2={y(g)} stroke="#1e293b" strokeDasharray="3 5" />
              <text x={PX - 8} y={y(g) + 3} textAnchor="end" className="num" fontSize="10" fill="#64748b">{g / 100}%</text>
            </g>
          ))}
          {/* investment-grade boundary */}
          <line x1={(x(3) + x(4)) / 2} x2={(x(3) + x(4)) / 2} y1={PY - 8} y2={H - PY} stroke="#f59e0b" strokeDasharray="2 4" opacity="0.5" />
          <text x={(x(3) + x(4)) / 2 + 6} y={PY - 2} fontSize="9" fill="#f59e0b" opacity="0.8" letterSpacing="1.5">SPECULATIVE →</text>
          <text x={(x(3) + x(4)) / 2 - 6} y={PY - 2} fontSize="9" fill="#38bdf8" opacity="0.8" textAnchor="end" letterSpacing="1.5">← INVESTMENT GRADE</text>
          <path d={area} fill="url(#curveFill)" />
          <path d={path} fill="none" stroke="url(#curveStroke)" strokeWidth="2.5" strokeLinejoin="round" />
          {TIERS.map((t, i) => {
            const on = active === t.rating;
            return (
              <g key={t.rating} className="cursor-pointer" onMouseEnter={() => setHover(t.rating)} onMouseLeave={() => setHover(undefined)}
                 onClick={() => onPick?.(t.rating)}>
                <circle cx={x(i)} cy={y(t.rateBps)} r={on ? 11 : 7} fill={t.hue} opacity={on ? 0.25 : 0.14} style={{ transition: "all .2s" }} />
                <circle cx={x(i)} cy={y(t.rateBps)} r={on ? 5.5 : 4} fill={t.hue} stroke="#020617" strokeWidth="1.5" />
                <text x={x(i)} y={y(t.rateBps) - 14} textAnchor="middle" className="num" fontSize="11" fontWeight="700" fill={t.hue}>{pct(t.rateBps, t.rateBps % 100 ? 1 : 0)}</text>
                <text x={x(i)} y={H - 8} textAnchor="middle" className="num" fontSize="12" fontWeight="700" fill={on ? t.hue : "#94a3b8"}>{t.rating}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="scroll-thin overflow-x-auto px-3 pb-3">
        <table className="num w-full min-w-[520px] text-xs">
          <thead>
            <tr className="label text-left">
              <th className="py-1.5 font-medium">Tier</th><th className="font-medium">Grade</th>
              <th className="text-right font-medium">APR</th><th className="text-right font-medium">Spread</th>
              <th className="text-right font-medium">Advance / ARR</th>
            </tr>
          </thead>
          <tbody>
            {TIERS.map((t) => (
              <tr key={t.rating} onMouseEnter={() => setHover(t.rating)} onMouseLeave={() => setHover(undefined)} onClick={() => onPick?.(t.rating)}
                  className={`cursor-pointer border-t border-slate-800/70 transition ${active === t.rating ? "bg-slate-800/50" : ""}`}>
                <td className="py-1.5 font-bold" style={{ color: t.hue }}>{t.rating}</td>
                <td className="font-sans text-slate-400">{t.label}</td>
                <td className="text-right text-slate-200">{pct(t.rateBps)}</td>
                <td className="text-right text-slate-400">{t.rateBps === aaa ? "—" : `+${t.rateBps - aaa} bps`}</td>
                <td className="text-right text-slate-400">{pct(t.advanceBps, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
