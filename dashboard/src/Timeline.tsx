import { useEffect, useMemo, useRef, useState } from "react";
import { getTimeline, type Switch, type Timeline } from "./api";
import { fmtDate, num } from "./format";

/* Watch it trade: drag through 2006 to today. The top chart is how tightly the two prices are tied (the
 * 126-session Engle-Granger statistic), the lower one the gap in standard deviations; shaded spans are the
 * realistic rule's trades. Today's state comes from the live service. */

function useWidth<T extends Element>(fallback = 900, ready: unknown = true) {
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
  }, [ready]);
  return [ref, w] as const;
}

const bps = (v: number) =>
  `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(0)} bps`;

export function WatchItTrade({ live }: { live: Switch | null }) {
  const [tl, setTl] = useState<Timeline | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [i, setI] = useState<number | null>(null);
  const [ref, W] = useWidth<HTMLDivElement>(900, tl);
  useEffect(() => {
    getTimeline().then(
      (t) => {
        setTl(t);
        const k = t.dates.findIndex((d) => d >= "2020-02-03");
        setI(k > 0 ? k : t.dates.length - 1);
      },
      (e) => setErr(String(e.message ?? e)),
    );
  }, []);

  const spans = useMemo(() => {
    if (!tl) return [];
    const pos = new Map(tl.dates.map((d, k) => [d, k] as const));
    return tl.trades.map((t) => ({
      ...t,
      a: pos.get(t.open) ?? 0,
      b: pos.get(t.close) ?? 0,
    }));
  }, [tl]);

  if (err) return <p className="loading">Could not load the timeline: {err}</p>;
  if (!tl || i == null)
    return <p className="loading">Loading twenty years of sessions…</p>;

  const n = tl.dates.length;
  const L = 44,
    R = 10;
  const x = (k: number) => L + (k / (n - 1)) * (W - L - R);
  const H1 = 150,
    H2 = 150;
  const yE = (v: number) =>
    22 + ((1 - Math.max(-6, Math.min(1, v))) / 7) * (H1 - 30); // statistic: 1 at top, -6 at bottom
  const yZ = (v: number) =>
    24 + ((4 - Math.max(-4, Math.min(4, v))) / 8) * (H2 - 32);
  const line = (vals: (number | null)[], f: (v: number) => number) => {
    let d = "",
      pen = false;
    const step = Math.max(1, Math.floor(n / (W * 1.5)));
    for (let k = 0; k < n; k += step) {
      const v = vals[k];
      if (v == null) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${x(k).toFixed(1)} ${f(v).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const years = tl.dates
    .map((d, k) => [d.slice(0, 4), k] as const)
    .filter(([y], k, a) => k === 0 || y !== a[k - 1]![0]);
  const gap = W < 600 ? 4 : 2;
  const eg = tl.eg[i],
    z = tl.z[i];
  const open = spans.find((t) => t.a <= i && i < t.b);
  const closed = spans.filter((t) => t.b <= i);
  const cum = closed.reduce((a, t) => a + t.net_bps, 0);
  const gateOpen = eg != null && eg < tl.gate;
  const date = tl.dates[i]!;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.buttons !== 1 && e.pointerType === "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const k = Math.round(
      ((((e.clientX - r.left) / r.width) * W - L) / (W - L - R)) * (n - 1),
    );
    setI(Math.max(0, Math.min(n - 1, k)));
  };

  return (
    <div className="watch">
      <section className="lab-intro">
        <h2 className="serif">
          Watch the rule <em>wait, then trade</em>
        </h2>
        <p className="lede">
          Drag through twenty years. The rule only trades while the top line is
          below the dashed cutoff, when the two prices have been moving
          together. Then it waits for the gap below to pass ±1.5 standard
          deviations and bets it will close. Shaded spans are its trades,
          decided at 16:00 and filled in the closing auction, with dividends
          counted.
        </p>
      </section>

      <div className="watch-state">
        <div>
          <p className="eyebrow">
            {fmtDate(date, {
              weekday: "short",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </p>
          <p className="big serif">{gateOpen ? "Tied together" : "Not tied"}</p>
          <p className="muted small">
            Statistic {eg == null ? "n/a" : num(eg)} against a cutoff of{" "}
            {num(tl.gate, 1)}
          </p>
        </div>
        <div>
          <p className="eyebrow">The gap</p>
          <p className="big serif">{z == null ? "n/a" : `${num(z, 1)} sd`}</p>
          <p className="muted small">
            {z != null && Math.abs(z) > tl.entry
              ? "wide enough to open"
              : "inside the band"}
          </p>
        </div>
        <div>
          <p className="eyebrow">Position</p>
          <p className="big serif">{open ? "In a trade" : "Flat"}</p>
          <p className="muted small">
            {open
              ? `opened ${fmtDate(open.open)}, it will close ${fmtDate(open.close)} at ${bps(open.net_bps)}`
              : "waiting"}
          </p>
        </div>
        <div>
          <p className="eyebrow">Closed trades to this day</p>
          <p className={`big serif${cum < 0 ? " neg" : ""}`}>{closed.length}</p>
          <p className="muted small">
            {closed.length
              ? `${bps(cum)} summed, ${bps(cum / closed.length)} a trade`
              : "none yet"}
          </p>
        </div>
      </div>

      <div ref={ref} className="watch-charts">
        <svg
          viewBox={`0 0 ${W} ${H1 + H2 + 30}`}
          width={W}
          height={H1 + H2 + 30}
          className="chart"
          onPointerDown={onMove}
          onPointerMove={onMove}
          style={{ touchAction: "pan-y", cursor: "ew-resize" }}
          role="img"
          aria-label="The Engle-Granger statistic and the gap, with the rule's trades"
        >
          {spans.map((t) => (
            <rect
              key={t.open}
              x={x(t.a)}
              y={0}
              width={Math.max(1.5, x(t.b) - x(t.a))}
              height={H1 + H2}
              fill={t.net_bps >= 0 ? "var(--positive)" : "var(--negative)"}
              opacity={0.16}
            />
          ))}
          <text x={L} y={12} className="lbl">
            How tightly tied (statistic)
          </text>
          <path
            d={`M${L} ${yE(tl.gate)}H${W - R}`}
            stroke="var(--foreground)"
            strokeDasharray="5 4"
            strokeOpacity={0.6}
          />
          <text x={L - 6} y={yE(tl.gate) + 4} textAnchor="end">
            {num(tl.gate, 1)}
          </text>
          <text x={L - 6} y={yE(0) + 4} textAnchor="end">
            0
          </text>
          <path
            d={line(tl.eg, yE)}
            fill="none"
            stroke="var(--foreground)"
            strokeWidth={1}
          />
          <g transform={`translate(0 ${H1})`}>
            <text x={L} y={14} className="lbl">
              The gap (standard deviations)
            </text>
            {[1.5, -1.5].map((v) => (
              <g key={v}>
                <path
                  d={`M${L} ${yZ(v)}H${W - R}`}
                  stroke="var(--border-strong)"
                  strokeDasharray="3 3"
                />
                <text x={L - 6} y={yZ(v) + 4} textAnchor="end">
                  {v > 0 ? "+1.5" : "−1.5"}
                </text>
              </g>
            ))}
            <path d={`M${L} ${yZ(0)}H${W - R}`} stroke="var(--border)" />
            <path
              d={line(tl.z, yZ)}
              fill="none"
              stroke="#5a6470"
              strokeWidth={0.9}
            />
          </g>
          {years
            .filter(([y]) => Number(y) % gap === 0)
            .map(([y, k]) => (
              <text key={y} x={x(k)} y={H1 + H2 + 20} textAnchor="middle">
                {y}
              </text>
            ))}
          <path
            d={`M${x(i)} 0V${H1 + H2}`}
            stroke="var(--foreground)"
            strokeWidth={1.5}
          />
          <circle cx={x(i)} cy={yE(eg ?? 0)} r={4} fill="var(--foreground)" />
          {z != null && (
            <circle cx={x(i)} cy={H1 + yZ(z)} r={4} fill="var(--foreground)" />
          )}
        </svg>
        <input
          type="range"
          min={0}
          max={n - 1}
          value={i}
          onChange={(e) => setI(Number(e.target.value))}
          aria-label="Date"
          className="watch-slider"
        />
        <p className="note">
          Development record to 31 March 2026: {tl.trades.length} trades. The
          statistic and gap use closing prices; the trades decide on the 16:00
          price, so on a few days they differ slightly.{" "}
          {tl.dates[n - 1] && `Sessions to ${fmtDate(tl.dates[n - 1]!)}.`}
        </p>
      </div>

      {live && (
        <section className="watch-today">
          <p className="eyebrow">
            Today, on live prices ({fmtDate(live.as_of)})
          </p>
          <p>
            The statistic is <b>{num(live.today.eg)}</b>, so the two prices are{" "}
            <b>
              {live.today.eg < live.spread_gate.crit
                ? "tied together"
                : "not tied together"}
            </b>{" "}
            by the rule&apos;s test (cutoff {num(live.spread_gate.crit, 1)}).
            The gap is {num(live.today.z, 1)} sd. It was last tied on{" "}
            {live.today.last_gate_day
              ? fmtDate(live.today.last_gate_day)
              : "no recent day"}
            .
          </p>
        </section>
      )}
    </div>
  );
}
