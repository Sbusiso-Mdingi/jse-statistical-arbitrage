import { useMemo, useRef, useState } from "react";
import { fmtDate, pct } from "./format";

const W = 760;

function scaleLinear(d0: number, d1: number, r0: number, r1: number) {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  return (v: number) => r0 + (v - d0) * k;
}

function ticks(min: number, max: number, count = 4) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-12; v += step) out.push(+v.toFixed(10));
  return out;
}

function yearTicks(dates: string[]) {
  const out: { i: number; label: string }[] = [];
  const years = new Set<string>();
  const spanYears = (Date.parse(dates[dates.length - 1]) - Date.parse(dates[0])) / 3.15e10;
  dates.forEach((d, i) => {
    const y = d.slice(0, 4);
    const m = d.slice(0, 7);
    if (spanYears > 2) {
      if (!years.has(y)) {
        years.add(y);
        if (i > 0 && (+y % (spanYears > 8 ? 2 : 1) === 0)) out.push({ i, label: y });
      }
    } else if (!years.has(m)) {
      years.add(m);
      if (i > 0) out.push({ i, label: fmtDate(d, { month: "short" }) });
    }
  });
  return out;
}

type Hover = { i: number } | null;

export function EquityChart({
  dates,
  equity,
  benchmark,
  position,
  showBenchmark,
  marker,
}: {
  dates: string[];
  equity: number[];
  benchmark: number[];
  position: number[];
  showBenchmark: boolean;
  marker?: string;
}) {
  const H = 300;
  const pad = { l: 46, r: 12, t: 12, b: 46 };
  const [hover, setHover] = useState<Hover>(null);
  const ref = useRef<SVGSVGElement>(null);
  const series = showBenchmark ? [...equity, ...benchmark] : equity;
  const min = Math.min(1, ...series);
  const max = Math.max(1, ...series);
  const x = scaleLinear(0, dates.length - 1, pad.l, W - pad.r);
  const y = scaleLinear(min - (max - min) * 0.05, max + (max - min) * 0.05, H - pad.b, pad.t);
  const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const markerIndex = marker ? dates.findIndex((d) => d >= marker) : -1;
  const ribbon = useMemo(() => {
    const segs: { a: number; b: number; side: number }[] = [];
    let start = 0;
    for (let i = 1; i <= position.length; i++) {
      if (i === position.length || position[i] !== position[start]) {
        if (position[start] !== 0) segs.push({ a: start, b: i, side: position[start] });
        start = i;
      }
    }
    return segs;
  }, [position]);

  const onMove = (e: React.MouseEvent) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const px = ((e.clientX - box.left) / box.width) * W;
    const i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (dates.length - 1));
    setHover(i >= 0 && i < dates.length ? { i } : null);
  };

  return (
    <svg
      ref={ref}
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      onMouseMove={onMove}
      onMouseLeave={() => setHover(null)}
      role="img"
      aria-label="Growth of one rand invested in the strategy"
    >
      {ticks(min, max).map((t) => (
        <g key={t}>
          <path d={`M${pad.l} ${y(t)}H${W - pad.r}`} stroke="var(--border)" />
          <text x={pad.l - 8} y={y(t) + 3} textAnchor="end">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      <path d={`M${pad.l} ${y(1)}H${W - pad.r}`} stroke="var(--border-strong)" strokeDasharray="2 3" />
      {yearTicks(dates).map((t) => (
        <text key={t.i} x={x(t.i)} y={H - pad.b + 16} textAnchor="middle">
          {t.label}
        </text>
      ))}
      {markerIndex > 0 && (
        <g>
          <rect
            x={x(markerIndex)}
            y={pad.t}
            width={W - pad.r - x(markerIndex)}
            height={H - pad.b - pad.t}
            fill="var(--accent)"
            opacity=".35"
          />
          <text x={x(markerIndex) + 6} y={pad.t + 12} style={{ fill: "var(--primary)" }}>
            UNSEEN
          </text>
        </g>
      )}
      {showBenchmark && <path d={path(benchmark)} fill="none" stroke="var(--border-strong)" strokeWidth="1.2" />}
      <path d={path(equity)} fill="none" stroke="var(--primary)" strokeWidth="1.8" />
      {ribbon.map((s) => (
        <rect
          key={s.a}
          x={x(s.a)}
          width={Math.max(1, x(s.b) - x(s.a))}
          y={H - pad.b + 24}
          height={8}
          fill={s.side > 0 ? "var(--primary)" : "#b58b3c"}
        />
      ))}
      <text x={pad.l} y={H - 4}>
        POSITION
      </text>
      {hover && (
        <g pointerEvents="none">
          <path d={`M${x(hover.i)} ${pad.t}V${H - pad.b}`} stroke="var(--foreground)" strokeOpacity=".4" />
          <circle cx={x(hover.i)} cy={y(equity[hover.i])} r="3.5" fill="var(--primary)" />
          <g transform={`translate(${Math.min(x(hover.i) + 10, W - 190)} ${pad.t + 6})`}>
            <rect width="180" height={showBenchmark ? 58 : 44} fill="var(--background)" stroke="var(--border-strong)" />
            <text x="10" y="16" style={{ fill: "var(--foreground)" }}>
              {fmtDate(dates[hover.i])}
            </text>
            <text x="10" y="31">
              Strategy {pct(equity[hover.i] - 1, 1)}
            </text>
            {showBenchmark && (
              <text x="10" y="46">
                Buy and hold {pct(benchmark[hover.i] - 1, 1)}
              </text>
            )}
          </g>
        </g>
      )}
    </svg>
  );
}

export function SignalChart({
  dates,
  h,
  open,
  close,
  position,
}: {
  dates: string[];
  h: number[];
  open: number[];
  close?: number[];
  position: number[];
}) {
  const H = 240;
  const pad = { l: 40, r: 12, t: 10, b: 28 };
  const x = scaleLinear(0, dates.length - 1, pad.l, W - pad.r);
  const y = scaleLinear(0, 1, H - pad.b, pad.t);
  const band = (offsets: number[], sign: number) =>
    offsets.map((o, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(0.5 + sign * o).toFixed(1)}`).join("");
  const step = Math.max(1, Math.floor(dates.length / 600));
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Conditional probability signal">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <path d={`M${pad.l} ${y(t)}H${W - pad.r}`} stroke="var(--border)" />
          <text x={pad.l - 8} y={y(t) + 3} textAnchor="end">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      <path d={band(open, 1)} fill="none" stroke="var(--foreground)" strokeDasharray="3 3" />
      <path d={band(open, -1)} fill="none" stroke="var(--foreground)" strokeDasharray="3 3" />
      {close && <path d={band(close, 1)} fill="none" stroke="var(--border-strong)" />}
      {close && <path d={band(close, -1)} fill="none" stroke="var(--border-strong)" />}
      {h.map((v, i) =>
        i % step === 0 || position[i] !== 0 ? (
          <circle
            key={i}
            cx={x(i)}
            cy={y(v)}
            r={position[i] !== 0 ? 2.6 : 1.6}
            fill={position[i] > 0 ? "var(--primary)" : position[i] < 0 ? "#b58b3c" : "var(--border-strong)"}
          />
        ) : null,
      )}
      {yearTicks(dates).map((t) => (
        <text key={t.i} x={x(t.i)} y={H - 8} textAnchor="middle">
          {t.label}
        </text>
      ))}
    </svg>
  );
}

export function PitScatter({
  history,
  live,
  yLabel = "NED v → 1",
}: {
  history: { u: number[]; v: number[] };
  live: { u: number[]; v: number[] };
  yLabel?: string;
}) {
  const S = 300;
  const pad = 30;
  const x = scaleLinear(0, 1, pad, S - 6);
  const y = scaleLinear(0, 1, S - pad, 6);
  const step = Math.max(1, Math.floor(history.u.length / 1500));
  return (
    <svg className="chart square" viewBox={`0 0 ${S} ${S}`} role="img" aria-label="Probability-integral transforms of the two banks">
      <rect x={pad} y={6} width={S - 6 - pad} height={S - pad - 6} fill="none" stroke="var(--border-strong)" />
      {history.u.map((u, i) =>
        i % step === 0 ? <circle key={i} cx={x(u)} cy={y(history.v[i])} r="1.6" fill="var(--border-strong)" opacity=".55" /> : null,
      )}
      {live.u.map((u, i) => (
        <circle key={`l${i}`} cx={x(u)} cy={y(live.v[i])} r="2.6" fill="var(--primary)" />
      ))}
      <text x={pad} y={S - 10}>
        0
      </text>
      <text x={S - 6} y={S - 10} textAnchor="end">
        SBK u → 1
      </text>
      <text x={14} y={6} transform={`rotate(-90 14 6)`} textAnchor="end">
        {yLabel}
      </text>
    </svg>
  );
}

export function DecayChart({
  dates,
  pairs,
  mean,
  highlight,
}: {
  dates: string[];
  pairs: { a: string; b: string; acf: number[] }[];
  mean: number[];
  highlight: number;
}) {
  const H = 280;
  const pad = { l: 46, r: 12, t: 12, b: 28 };
  const all = pairs.flatMap((p) => p.acf);
  const lo = Math.min(-0.3, ...all);
  const hi = Math.max(0.2, ...all);
  const x = scaleLinear(0, dates.length - 1, pad.l, W - pad.r);
  const y = scaleLinear(lo, hi, H - pad.b, pad.t);
  const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const split = dates.findIndex((d) => d >= "2020-01-01");
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Rolling one-year lag-1 autocorrelation of bank return spreads">
      {split > 0 && <rect x={x(split)} y={pad.t} width={W - pad.r - x(split)} height={H - pad.b - pad.t} fill="var(--accent)" opacity=".35" />}
      {split > 0 && (
        <text x={x(split) + 6} y={pad.t + 12} style={{ fill: "var(--primary)" }}>
          VALIDATION AND LIVE
        </text>
      )}
      {ticks(lo, hi, 5).map((t) => (
        <g key={t}>
          <path d={`M${pad.l} ${y(t)}H${W - pad.r}`} stroke={t === 0 ? "var(--foreground)" : "var(--border)"} strokeOpacity={t === 0 ? 0.5 : 1} />
          <text x={pad.l - 8} y={y(t) + 3} textAnchor="end">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {pairs.map((p, i) => (
        <path key={`${p.a}${p.b}`} d={path(p.acf)} fill="none" stroke={i === highlight ? "#b58b3c" : "var(--border-strong)"} strokeWidth={i === highlight ? 1.6 : 0.8} opacity={i === highlight ? 1 : 0.5} />
      ))}
      <path d={path(mean)} fill="none" stroke="var(--primary)" strokeWidth="2.2" />
      {yearTicks(dates).map((t) => (
        <text key={t.i} x={x(t.i)} y={H - 8} textAnchor="middle">
          {t.label}
        </text>
      ))}
    </svg>
  );
}

export function ReversalBars({ rows }: { rows: { year: number; n: number; bps: number; se: number | null }[] }) {
  const H = 240;
  const pad = { l: 46, r: 12, t: 12, b: 28 };
  const ext = rows.map((r) => [r.bps - 2 * (r.se ?? 0), r.bps + 2 * (r.se ?? 0)]).flat();
  const lo = Math.min(-20, ...ext);
  const hi = Math.max(20, ...ext);
  const y = scaleLinear(lo, hi, H - pad.b, pad.t);
  const bw = (W - pad.l - pad.r) / rows.length;
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Next-day return after an extreme signal, by year">
      {ticks(lo, hi, 5).map((t) => (
        <g key={t}>
          <path d={`M${pad.l} ${y(t)}H${W - pad.r}`} stroke={t === 0 ? "var(--foreground)" : "var(--border)"} strokeOpacity={t === 0 ? 0.5 : 1} />
          <text x={pad.l - 8} y={y(t) + 3} textAnchor="end">
            {t}
          </text>
        </g>
      ))}
      {rows.map((r, i) => {
        const cx = pad.l + bw * (i + 0.5);
        const top = Math.min(y(r.bps), y(0));
        return (
          <g key={r.year}>
            <rect x={cx - bw * 0.3} y={top} width={bw * 0.6} height={Math.abs(y(r.bps) - y(0))} fill={r.bps >= 0 ? "var(--primary)" : "var(--negative)"} opacity={r.year >= 2020 ? 1 : 0.75} />
            {r.se != null && <path d={`M${cx} ${y(r.bps - 2 * r.se)}V${y(r.bps + 2 * r.se)}`} stroke="var(--foreground)" strokeOpacity=".45" />}
            {(i % 2 === 0 || rows.length < 12) && (
              <text x={cx} y={H - 8} textAnchor="middle">
                {r.year}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
