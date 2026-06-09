// charts.jsx — hand-built SVG charts. Theme-reactive via CSS vars.
// Style variants ("minimal" | "grid" | "area") drive the chart-styling tweak.

function useMeasure() {
  const ref = React.useRef(null);
  const [w, setW] = React.useState(0);
  React.useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((es) => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    setW(ref.current.clientWidth);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

const fmtUSD = (n) => {
  if (Math.abs(n) >= 1000) return "$" + (n / 1000).toFixed(Math.abs(n) >= 10000 ? 0 : 1) + "k";
  return "$" + Math.round(n);
};
const fmtKReais = (n) => "$" + n + "k";

// ── Line chart (revenue trend) ───────────────────────────────────────────────
function LineChart({ labels, values, anomalyIndex = -1, style = "grid", height = 232, format = fmtKReais }) {
  const [ref, w] = useMeasure();
  const [hover, setHover] = React.useState(-1);
  const showGrid = style !== "minimal";
  const padL = showGrid ? 44 : 12, padR = 14, padT = 16, padB = 26;
  const W = Math.max(w, 10), H = height;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const max = Math.max(...values) * 1.12, min = 0;
  const x = (i) => padL + (innerW * i) / (values.length - 1);
  const y = (v) => padT + innerH * (1 - (v - min) / (max - min));
  const linePath = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${x(values.length - 1).toFixed(1)} ${(padT + innerH).toFixed(1)} L${x(0).toFixed(1)} ${(padT + innerH).toFixed(1)} Z`;
  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => min + ((max - min) * i) / ticks);
  const labelStep = Math.ceil(labels.length / 6);

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const i = Math.round(((px - padL) / innerW) * (values.length - 1));
    setHover(Math.max(0, Math.min(values.length - 1, i)));
  };

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      <svg width={W} height={H} style={{ display: "block" }}>
        <defs>
          <linearGradient id="zArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.20" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {showGrid && yTicks.map((t, i) => (
          <g key={i}>
            <line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)} stroke="var(--chart-grid)" strokeWidth="1" />
            <text x={padL - 8} y={y(t) + 3.5} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--mono)">{format(Math.round(t))}</text>
          </g>
        ))}
        {style === "area" && <path d={areaPath} fill="url(#zArea)" />}
        <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {anomalyIndex >= 0 && (
          <g>
            <line x1={x(anomalyIndex)} y1={padT} x2={x(anomalyIndex)} y2={padT + innerH} stroke="var(--danger)" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
            <circle cx={x(anomalyIndex)} cy={y(values[anomalyIndex])} r="5.5" fill="var(--surface)" stroke="var(--danger)" strokeWidth="2" />
          </g>
        )}
        {labels.map((l, i) => (i % labelStep === 0 || i === labels.length - 1) && (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="var(--text-3)" fontFamily="var(--mono)">{l}</text>
        ))}
        {hover >= 0 && (
          <g>
            <line x1={x(hover)} y1={padT} x2={x(hover)} y2={padT + innerH} stroke="var(--text-3)" strokeWidth="1" opacity="0.5" />
            <circle cx={x(hover)} cy={y(values[hover])} r="4" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" />
          </g>
        )}
        <rect x={padL} y={padT} width={innerW} height={innerH} fill="transparent"
          onMouseMove={onMove} onMouseLeave={() => setHover(-1)} />
      </svg>
      {hover >= 0 && W > 10 && (
        <div className="z-tip" style={{ left: Math.min(Math.max(x(hover), 48), W - 48), top: y(values[hover]) - 14 }}>
          <span className="z-tip-l">{labels[hover]}</span>
          <span className="z-tip-v">{format(values[hover])}{anomalyIndex === hover ? " · anomaly" : ""}</span>
        </div>
      )}
    </div>
  );
}

// ── Horizontal bar chart (top products / categories) ──────────────────────────
function BarChart({ items, style = "grid", format = fmtUSD, height }) {
  const [ref, w] = useMeasure();
  const [hover, setHover] = React.useState(-1);
  const rowH = 30, gap = 8, padL = 0, labelW = 116, valW = 56;
  const H = height || items.length * (rowH + gap);
  const max = Math.max(...items.map((d) => d.value));
  const trackX = padL + labelW, trackW = Math.max((w || 300) - trackX - valW, 20);

  return (
    <div ref={ref} style={{ width: "100%" }}>
      <svg width={Math.max(w, 10)} height={H} style={{ display: "block" }}>
        {items.map((d, i) => {
          const yTop = i * (rowH + gap);
          const bw = Math.max((d.value / max) * trackW, 2);
          const hot = hover === i;
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(-1)}>
              <text x={padL} y={yTop + rowH / 2 + 4} fontSize="12" fill="var(--text-2)" fontFamily="var(--sans)">{d.label}</text>
              {style !== "minimal" && <rect x={trackX} y={yTop + 3} width={trackW} height={rowH - 6} rx="4" fill="var(--chart-track)" />}
              <rect x={trackX} y={yTop + 3} width={bw} height={rowH - 6} rx="4"
                fill={d.color || "var(--accent)"} opacity={hot ? 1 : i === 0 ? 0.95 : 0.78 - i * 0.05}
                style={{ transition: "opacity .15s" }} />
              <text x={Math.max(w, 10)} y={yTop + rowH / 2 + 4} textAnchor="end" fontSize="11.5" fill="var(--text)" fontFamily="var(--mono)" fontWeight="500">{format(d.value)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Vertical bar chart (sales velocity) ───────────────────────────────────────
function ColumnChart({ items, style = "grid", height = 200, unit = "" }) {
  const [ref, w] = useMeasure();
  const [hover, setHover] = React.useState(-1);
  const padT = 16, padB = 40, padL = 6, padR = 6;
  const W = Math.max(w, 10), H = height, innerH = H - padT - padB;
  const max = Math.max(...items.map((d) => d.value)) * 1.1;
  const slot = (W - padL - padR) / items.length;
  const bw = Math.min(slot * 0.56, 34);

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      <svg width={W} height={H} style={{ display: "block" }}>
        {style !== "minimal" && [0, 0.5, 1].map((f, i) => (
          <line key={i} x1={padL} y1={padT + innerH * f} x2={W - padR} y2={padT + innerH * f} stroke="var(--chart-grid)" strokeWidth="1" />
        ))}
        {items.map((d, i) => {
          const cx = padL + slot * i + slot / 2;
          const bh = (d.value / max) * innerH;
          const hot = hover === i;
          return (
            <g key={d.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(-1)}>
              <rect x={cx - bw / 2} y={padT + innerH - bh} width={bw} height={bh} rx="3"
                fill={d.color || "var(--accent)"} opacity={hot ? 1 : 0.85} style={{ transition: "opacity .15s" }} />
              <text x={cx} y={H - 24} textAnchor="middle" fontSize="9.5" fill="var(--text-3)" fontFamily="var(--sans)">{d.label}</text>
              <text x={cx} y={H - 11} textAnchor="middle" fontSize="10" fill="var(--text-2)" fontFamily="var(--mono)" fontWeight="500">{d.value}{unit}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Histogram (Monte Carlo distribution) ──────────────────────────────────────
function Histogram({ bins, counts, markers = {}, ci = null, height = 240 }) {
  const [ref, w] = useMeasure();
  const padT = 14, padB = 34, padL = 8, padR = 8;
  const W = Math.max(w, 10), H = height, innerH = H - padT - padB;
  const max = Math.max(...counts);
  const slot = (W - padL - padR) / counts.length;
  const x = (val) => padL + ((val - bins[0]) / (bins[bins.length - 1] - bins[0])) * (W - padL - padR);

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      <svg width={W} height={H} style={{ display: "block" }}>
        {ci && (
          <rect x={x(ci[0])} y={padT} width={x(ci[1]) - x(ci[0])} height={innerH} fill="var(--accent)" opacity="0.08" />
        )}
        {counts.map((c, i) => {
          const bh = (c / max) * innerH;
          const inCI = ci && bins[i] >= ci[0] && bins[i] <= ci[1];
          return <rect key={i} x={padL + slot * i + 1} y={padT + innerH - bh} width={slot - 2} height={bh} rx="1.5"
            fill="var(--accent)" opacity={inCI ? 0.85 : 0.4} />;
        })}
        <line x1={padL} y1={padT + innerH} x2={W - padR} y2={padT + innerH} stroke="var(--chart-grid)" strokeWidth="1" />
        {Object.entries(markers).map(([k, m]) => (
          <g key={k}>
            <line x1={x(m.value)} y1={padT - 2} x2={x(m.value)} y2={padT + innerH} stroke={m.color} strokeWidth="1.5" strokeDasharray={m.dash ? "4 3" : "0"} />
            <text x={x(m.value)} y={H - 18} textAnchor="middle" fontSize="9.5" fill={m.color} fontFamily="var(--sans)" fontWeight="600">{m.label}</text>
            <text x={x(m.value)} y={H - 6} textAnchor="middle" fontSize="9.5" fill="var(--text-3)" fontFamily="var(--mono)">{m.value}×</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

Object.assign(window, { LineChart, BarChart, ColumnChart, Histogram, useMeasure, fmtUSD, fmtKReais });
