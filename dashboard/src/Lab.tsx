import { useEffect, useMemo, useRef, useState } from "react";
import { getLab, type Lab, type LabSpec } from "./api";
import { num } from "./format";

/* Find your own rule: 216 versions of the spread rule, each with its backtest, a count of how many the visitor
 * has looked at, how good the best of that many would look by luck, and the same rule on 18 unseen pairs. */

type Key = {
  window: number;
  gate: number | null;
  entry: number;
  fill: "same" | "next";
  div: "price" | "total";
};
const keyOf = (k: Key) => `${k.window}|${k.gate}|${k.entry}|${k.fill}|${k.div}`;
const STORE = "jse-pairs-lab-v1";

const WINDOW_LABEL: Record<number, string> = {
  63: "3 months",
  126: "6 months",
  252: "1 year",
};
const GATE_LABEL = (g: number | null) =>
  g == null ? "Always trade" : num(g, 1);
const bps = (v: number | null | undefined) =>
  v == null
    ? "n/a"
    : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(0)} bps`;

function useWidth<T extends Element>(fallback = 700) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(
      ([e]) =>
        e!.contentRect.width > 0 &&
        setW(Math.max(300, Math.round(e!.contentRect.width))),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function Choice<T extends string | number | null>({
  label,
  value,
  options,
  onChange,
  hint,
}: {
  label: string;
  value: T;
  options: { id: T; label: string }[];
  onChange: (v: T) => void;
  hint?: string;
}) {
  return (
    <div className="lab-choice">
      <span className="eyebrow">{label}</span>
      <div className="segmented">
        {options.map((o) => (
          <button
            key={String(o.id)}
            aria-pressed={o.id === value}
            onClick={() => onChange(o.id)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  );
}

function Curve({
  quarters,
  curves,
}: {
  quarters: string[];
  curves: { values: number[]; tone: "main" | "ghost" }[];
}) {
  const [ref, W] = useWidth<SVGSVGElement>();
  const H = 240,
    L = 48,
    R = 12,
    T = 12,
    B = 28;
  const all = curves.flatMap((c) => c.values);
  const lo = Math.min(0, ...all),
    hi = Math.max(5, ...all);
  const x = (i: number) =>
    L + (i / Math.max(1, quarters.length - 1)) * (W - L - R);
  const y = (v: number) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const step = Math.max(10, Math.ceil((hi - lo) / 4 / 10) * 10);
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
  const years = quarters
    .map((q, i) => [q, i] as const)
    .filter(([q]) => q.endsWith("Q1") && Number(q.slice(0, 4)) % 4 === 2);
  return (
    <svg
      ref={ref}
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      role="img"
      aria-label="Cumulative net P&L of the chosen rule"
    >
      {ticks.map((t) => (
        <g key={t}>
          <path
            d={`M${L} ${y(t)}H${W - R}`}
            stroke={t === 0 ? "var(--foreground)" : "var(--border)"}
            strokeOpacity={t === 0 ? 0.5 : 1}
          />
          <text x={L - 8} y={y(t) + 4} textAnchor="end">
            {t > 0 ? "+" : ""}
            {t}%
          </text>
        </g>
      ))}
      {years.map(([q, i]) => (
        <text key={q} x={x(i)} y={H - 8} textAnchor="middle">
          {q.slice(0, 4)}
        </text>
      ))}
      {curves.map((c, k) => (
        <path
          key={k}
          d={c.values
            .map(
              (v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`,
            )
            .join("")}
          fill="none"
          stroke={
            c.tone === "main" ? "var(--foreground)" : "var(--border-strong)"
          }
          strokeWidth={c.tone === "main" ? 2.2 : 1}
          strokeDasharray={c.tone === "ghost" ? "4 3" : undefined}
        />
      ))}
    </svg>
  );
}

export function RuleLab() {
  const [lab, setLab] = useState<Lab | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [k, setK] = useState<Key>({
    window: 126,
    gate: -2.8,
    entry: 1.5,
    fill: "same",
    div: "price",
  });
  const [seen, setSeen] = useState<string[]>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(STORE) ?? "[]");
    } catch {
      return [];
    }
  });
  const [showPairs, setShowPairs] = useState(false);

  useEffect(() => {
    getLab().then(setLab, (e) => setErr(String(e.message ?? e)));
  }, []);

  const index = useMemo(
    () => new Map((lab?.specs ?? []).map((s) => [keyOf(s), s] as const)),
    [lab],
  );
  const spec = index.get(keyOf(k));
  const found = lab ? index.get(keyOf(lab.found as Key)) : undefined;

  useEffect(() => {
    if (!spec) return;
    const id = keyOf(k);
    setShowPairs(false);
    setSeen((old) => {
      if (old.includes(id)) return old;
      const next = [...old, id];
      sessionStorage.setItem(STORE, JSON.stringify(next));
      return next;
    });
  }, [spec]); // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <p className="loading">Could not load the rule lab: {err}</p>;
  if (!lab || !spec)
    return <p className="loading">Loading 216 versions of the rule…</p>;

  const tried = seen.map((id) => index.get(id)).filter(Boolean) as LabSpec[];
  const best = tried.reduce(
    (a, b) => (b.dev.sharpe > a.dev.sharpe ? b : a),
    tried[0] ?? spec,
  );
  const n = Math.min(tried.length || 1, lab.luck.n.length);
  const p50 = lab.luck.p50[n - 1]!,
    p95 = lab.luck.p95[n - 1]!;
  const verdict =
    best.dev.sharpe > p95
      ? "better than luck alone gives nineteen times in twenty"
      : best.dev.sharpe > p50
        ? "inside the range luck alone produces"
        : "no better than luck alone typically gives";
  const set = <K extends keyof Key>(f: K, v: Key[K]) => setK({ ...k, [f]: v });
  const isFound = keyOf(k) === keyOf(lab.found as Key);
  const s = spec.dev;
  const maxS = Math.max(1, p95 * 1.25, best.dev.sharpe * 1.1);

  return (
    <div className="lab">
      <section className="lab-intro">
        <h2 className="serif">
          Search for a rule, <em>and see what the search costs</em>
        </h2>
        <p className="lede">
          The spread rule waits until the two prices have been tied together
          over a recent window, then bets that a wide gap will close. Every
          setting below changes it. Each version is backtested on 2006 to March
          2026 after institutional futures costs. The more versions you look at,
          the better the best one looks, even if none of them works.
        </p>
      </section>

      <div className="lab-grid">
        <div className="lab-controls">
          <Choice
            label="Window the tie is measured over"
            value={k.window}
            options={lab.dims.window.map((w) => ({
              id: w,
              label: WINDOW_LABEL[w] ?? `${w}`,
            }))}
            onChange={(v) => set("window", v)}
          />
          <Choice
            label="How tightly tied (Engle-Granger statistic below)"
            value={k.gate}
            options={lab.dims.gate.map((g) => ({
              id: g,
              label: GATE_LABEL(g),
            }))}
            onChange={(v) => set("gate", v)}
            hint="More negative is stricter: fewer days qualify."
          />
          <Choice
            label="Open when the gap is wider than"
            value={k.entry}
            options={lab.dims.entry.map((e) => ({ id: e, label: `${e} sd` }))}
            onChange={(v) => set("entry", v)}
          />
          <Choice
            label="Filled at"
            value={k.fill}
            options={[
              { id: "same", label: "The close that triggers it" },
              { id: "next", label: "The next close" },
            ]}
            onChange={(v) => set("fill", v)}
            hint="Nobody can trade at the close that triggered the decision."
          />
          <Choice
            label="Prices"
            value={k.div}
            options={[
              { id: "price", label: "Price only" },
              { id: "total", label: "With dividends" },
            ]}
            onChange={(v) => set("div", v)}
          />
          <div className="lab-presets">
            <button className="reset" onClick={() => setK(lab.found as Key)}>
              The rule as I first found it
            </button>
            <button
              className="reset"
              onClick={() =>
                setK({ ...(lab.found as Key), fill: "next", div: "total" })
              }
            >
              The same rule, tradeable
            </button>
          </div>
        </div>

        <div className="lab-result">
          <div className="metrics lab-metrics">
            <div className="metric">
              <div className={`value${(s.mean ?? 0) < 0 ? " neg" : ""}`}>
                {bps(s.mean)}
              </div>
              <div className="label">Net a trade</div>
              <div className="sub">
                {s.n} trades{s.t != null ? `, t ${num(s.t, 1)}` : ""}
              </div>
            </div>
            <div className="metric">
              <div className="value">
                {s.win != null ? `${Math.round(s.win * 100)}%` : "n/a"}
              </div>
              <div className="label">Trades that made money</div>
            </div>
            <div className="metric">
              <div className={`value${s.sharpe < 0 ? " neg" : ""}`}>
                {num(s.sharpe)}
              </div>
              <div className="label">Sharpe ratio</div>
              <div className="sub">of the book, flat when not trading</div>
            </div>
          </div>
          <p className="eyebrow">Net P&L, % of capital, summed since 2006</p>
          <Curve
            quarters={lab.quarters}
            curves={[
              ...(found && !isFound
                ? [{ values: found.curve, tone: "ghost" as const }]
                : []),
              { values: spec.curve, tone: "main" },
            ]}
          />
          <p className="note">
            By period: {bps(s.eras[0])} a trade in 2006–12, {bps(s.eras[1])} in
            2013–19, {bps(s.eras[2])} in 2020 to March 2026.
            {found && !isFound
              ? " The dashed line is the rule as first found."
              : ""}
            {spec.unseen.n
              ? ` Since 1 April 2026, unseen by every choice here: ${spec.unseen.n} trades, ${bps(spec.unseen.mean)} a trade.`
              : " Since 1 April 2026, unseen by every choice here: no trades yet."}
          </p>
        </div>
      </div>

      <section className="lab-luck">
        <div>
          <p className="eyebrow">You have looked at</p>
          <p className="big serif">
            {tried.length} {tried.length === 1 ? "version" : "versions"}
          </p>
          <p className="muted small">
            Best so far: {WINDOW_LABEL[best.window]}, {GATE_LABEL(best.gate)},{" "}
            {best.entry} sd,{" "}
            {best.fill === "same" ? "same close" : "next close"},{" "}
            {best.div === "price" ? "price only" : "with dividends"}.
          </p>
        </div>
        <div className="luck-bar">
          <p className="eyebrow">
            Sharpe ratio of your best version against luck
          </p>
          <div className="luck-track">
            <span
              className="luck-zone"
              style={{ left: 0, width: `${(Math.max(0, p95) / maxS) * 100}%` }}
            />
            <span
              className="luck-mark p50"
              style={{ left: `${(Math.max(0, p50) / maxS) * 100}%` }}
              title="typical best by luck"
            />
            <span
              className="luck-mark p95"
              style={{ left: `${(Math.max(0, p95) / maxS) * 100}%` }}
              title="one time in twenty by luck"
            />
            <span
              className="luck-you"
              style={{
                left: `${(Math.max(0, best.dev.sharpe) / maxS) * 100}%`,
              }}
            />
          </div>
          <div className="luck-legend small muted">
            <span>
              <i className="sw zone" /> what luck alone reaches
            </span>
            <span>
              <i className="sw dot" /> your best
            </span>
          </div>
          <p className="small">
            Your best: <b>{num(best.dev.sharpe)}</b>. If none of the 216
            versions had any edge, the best of {n} would typically reach{" "}
            {num(p50)}, and {num(p95)} one time in twenty. Your best is{" "}
            {verdict}.
          </p>
        </div>
        <div className="pairs-reveal">
          {!showPairs ? (
            <button className="run" onClick={() => setShowPairs(true)}>
              Try this rule on 18 pairs it never saw
            </button>
          ) : (
            <>
              <p className="eyebrow">
                The same rule on 18 other JSE pairs, with dividends
              </p>
              <p
                className={`big serif${(spec.pairs.mean ?? 0) < 0 ? " neg" : ""}`}
              >
                {bps(spec.pairs.mean)} a trade
              </p>
              <p className="muted small">
                {spec.pairs.n} trades from 2006, t {num(spec.pairs.t, 1)};{" "}
                {spec.pairs.positive} of {spec.pairs.of} pairs made money.
                Banks, insurers, gold, platinum, telecoms, food and clothing
                retail, hospitals.
              </p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
