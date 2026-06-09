// power.jsx — Power Mode modules + presentation wrapper.

// ── Sparkline chart (pure SVG, no library) ──
function SparklineChart({ data }) {
  if (!data || data.length < 2) {
    return (
      <div className="z-sparkline-wrap" style={{ height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>Not enough data points to render trend</span>
      </div>
    );
  }
  const W = 500, H = 80, PAD = 8;
  const values = data.map(d => d.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const pts = data.map((d, i) => ({
    x: PAD + (i / (data.length - 1)) * (W - PAD * 2),
    y: PAD + (1 - (d.value - minVal) / range) * (H - PAD * 2),
    label: d.label,
    value: d.value,
  }));

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L ${pts[pts.length - 1].x.toFixed(1)} ${H} L ${pts[0].x.toFixed(1)} ${H} Z`;

  const half = Math.floor(values.length / 2);
  const firstAvg = values.slice(0, half).reduce((a, b) => a + b, 0) / (half || 1);
  const secondAvg = values.slice(half).reduce((a, b) => a + b, 0) / ((values.length - half) || 1);
  const declining = secondAvg < firstAvg * 0.97;
  const strokeColor = declining ? 'var(--danger)' : 'var(--success)';

  const labelIdxs = [0, Math.floor(data.length / 2), data.length - 1];
  const fmt = (v) => v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toLocaleString()}`;

  return (
    <div className="z-sparkline-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 88, display: 'block' }} preserveAspectRatio="none">
        <defs>
          <linearGradient id="sg-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.22" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.03" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#sg-fill)" />
        <path d={linePath} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={pts[0].x} cy={pts[0].y} r="3.5" fill={strokeColor} />
        <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r="3.5" fill={strokeColor} />
      </svg>
      <div className="z-sparkline-labels">
        {labelIdxs.map(idx => (
          <span key={idx}>
            {data[idx]?.label}
            <span className="z-spk-val">{fmt(data[idx]?.value || 0)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Single breakdown bar row ──
function BreakdownBar({ label, score, max, color }) {
  const pct = Math.min(100, Math.round((score / max) * 100));
  return (
    <div className="z-breakdown-row">
      <div className="z-breakdown-row-hd">
        <span className="z-breakdown-row-label">{label}</span>
        <span className="z-breakdown-row-score" style={{ color }}>{score} / {max} pts</span>
      </div>
      <div className="z-breakdown-track">
        <div className="z-breakdown-fill" style={{ width: pct + '%', background: color }} />
      </div>
    </div>
  );
}

// ── ⓘ info button + floating tooltip ──
function RiskInfoButton({ product, onShowMore }) {
  const btnRef = React.useRef(null);
  const tipRef = React.useRef(null);
  const [pos, setPos] = React.useState(null);

  const toggle = (e) => {
    e.stopPropagation();
    if (pos) { setPos(null); return; }
    const rect = btnRef.current.getBoundingClientRect();
    const tipW = 292;
    let left = rect.left;
    if (left + tipW > window.innerWidth - 12) left = window.innerWidth - tipW - 12;
    setPos({ top: rect.bottom + 8, left });
  };

  React.useEffect(() => {
    if (!pos) return;
    const handler = (e) => {
      if (!btnRef.current?.contains(e.target) && !tipRef.current?.contains(e.target)) setPos(null);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [pos]);

  const bd = product.breakdown;
  const actionTone = { Liquidate: 'var(--danger)', Discontinue: 'var(--danger)', Discount: 'var(--warn)', Monitor: 'var(--success)' };

  return (
    <>
      <button ref={btnRef} className="z-info-btn" onClick={toggle} title="Why this risk score?">
        <Icon name="info" size={11} stroke={2} />
      </button>

      {pos && (
        <div ref={tipRef} className="z-risk-tooltip" style={{ top: pos.top, left: pos.left }}>
          {/* Header */}
          <div className="z-risk-tooltip-hd">
            <span className="z-risk-tooltip-title">{product.name}</span>
            <RiskPill level={product.level} score={product.risk} />
          </div>

          {/* Short rationale */}
          <p className="z-risk-tooltip-rationale">{product.rationale}</p>

          {/* Score breakdown bars */}
          {bd && (
            <div className="z-breakdown-list">
              <BreakdownBar label="Velocity decline" score={bd.velocity_score} max={40} color="var(--danger)" />
              <BreakdownBar label="Category trend" score={bd.category_score} max={30} color="var(--warn)" />
              <BreakdownBar label="Depreciation" score={bd.depreciation_score} max={30} color="var(--text-3)" />
            </div>
          )}

          {/* Top 2 signals */}
          {product.signals?.length > 0 && (
            <ul className="z-risk-signals">
              {product.signals.slice(0, 2).map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}

          {/* Show more → drilldown */}
          <button className="z-tooltip-more-btn" onClick={() => { setPos(null); onShowMore(product); }}>
            Show more <Icon name="chevronRight" size={11} stroke={2} />
          </button>
        </div>
      )}
    </>
  );
}

// ── Full drilldown modal ──
function ProductDrilldown({ product, onClose }) {
  if (!product) return null;
  const bd = product.breakdown;
  const actionTone = { Liquidate: 'danger', Discontinue: 'danger', Discount: 'warn', Monitor: 'success', Maintain: 'neutral' };

  return (
    <div className="z-drilldown-overlay" onClick={onClose}>
      <div className="z-drilldown" onClick={e => e.stopPropagation()}>
        {/* Sticky header */}
        <div className="z-drilldown-hd">
          <div className="z-drilldown-hd-info">
            <div className="z-drilldown-hd-title">{product.name}</div>
            <div className="z-drilldown-hd-sub">
              {product.category && <>{product.category} · </>}
              Velocity decline: {product.velocity_decline_pct?.toFixed(1)}%
            </div>
          </div>
          <div className="z-drilldown-hd-badges">
            <RiskPill level={product.level} score={product.risk} />
            <Badge tone={actionTone[product.action] || 'neutral'} dot>{product.action}</Badge>
          </div>
          <button className="z-info-btn" onClick={onClose} style={{ flexShrink: 0 }}>
            <Icon name="x" size={13} stroke={2} />
          </button>
        </div>

        <div className="z-drilldown-body">
          {/* Revenue / units trend sparkline */}
          {product.trend?.length >= 3 && (
            <div className="z-drilldown-section">
              <div className="z-drilldown-section-title">Revenue trend</div>
              <div className="z-drilldown-card" style={{ padding: '12px 14px' }}>
                <SparklineChart data={product.trend} />
              </div>
            </div>
          )}

          {/* Score breakdown */}
          {bd && (
            <div className="z-drilldown-section">
              <div className="z-drilldown-section-title">Risk score breakdown — {product.risk}/100</div>
              <div className="z-drilldown-card">
                <BreakdownBar label="Velocity decline  (weight 40%)" score={bd.velocity_score} max={40} color="var(--danger)" />
                <BreakdownBar label="Category trend  (weight 30%)" score={bd.category_score} max={30} color="var(--warn)" />
                <BreakdownBar label="Depreciation factor  (weight 30%)" score={bd.depreciation_score} max={30} color="var(--text-3)" />
              </div>
              <p className="z-formula-note">
                Score = (velocity_decline × 0.4) + (category_decline × 0.3) + (depreciation × 0.3)
              </p>
            </div>
          )}

          {/* All signals */}
          {product.signals?.length > 0 && (
            <div className="z-drilldown-section">
              <div className="z-drilldown-section-title">Identified signals</div>
              <div className="z-drilldown-card">
                <ul className="z-drilldown-signals">
                  {product.signals.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            </div>
          )}

          {/* Full analysis */}
          <div className="z-drilldown-section">
            <div className="z-drilldown-section-title">Analysis summary</div>
            <div className="z-drilldown-card">
              <p className="z-drilldown-rationale">{product.rationale}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Select({ value, onChange, options, width }) {
  return (
    <div className="z-select" style={width ? { width } : null}>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => {
          const opt = typeof o === "object" ? o : { value: o, label: o };
          return <option key={opt.value} value={opt.value}>{opt.label}</option>;
        })}
      </select>
      <Icon name="chevronDown" size={14} stroke={2} />
    </div>
  );
}

// ── Monte Carlo Investment Simulator ──
function MonteCarlo() {
  const D = window.ZDATA.MONTECARLO;
  const [product, setProduct] = React.useState(D.product);
  const [budget, setBudget] = React.useState(D.budgetChange);
  const [horizon, setHorizon] = React.useState(String(D.horizon));
  const [state, setState] = React.useState("ready"); // ready | running | done
  const products = window.ZDATA.PRODUCTS.map((p) => p.name);

  const run = () => {
    setState("running");
    setTimeout(() => setState("done"), 950);
  };
  React.useEffect(() => { setState("ready"); }, [product, budget, horizon]);

  const markers = {
    worst: { value: D.worst, label: "Worst", color: "var(--danger)", dash: true },
    expected: { value: D.expected, label: "Expected", color: "var(--accent)" },
    best: { value: 1.47, label: "Best", color: "var(--success)", dash: true },
  };

  return (
    <div className="z-mc">
      <div className="z-mc-controls">
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Product / channel</span>
          <Select value={product} onChange={setProduct} options={products} />
        </label>
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Budget change <b className="z-ctrl-val">{budget > 0 ? "+" : ""}{budget}%</b></span>
          <input type="range" className="z-range" min={-50} max={100} step={5} value={budget}
            onChange={(e) => setBudget(Number(e.target.value))} />
        </label>
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Time horizon</span>
          <Select value={horizon} onChange={setHorizon} options={[{ value: "30", label: "30 days" }, { value: "60", label: "60 days" }, { value: "90", label: "90 days" }, { value: "180", label: "180 days" }]} />
        </label>
        <Button variant="primary" icon={state === "running" ? undefined : "target"} onClick={run} disabled={state === "running"}>
          {state === "running" ? <><Spinner size={15} /> Simulating…</> : "Run 10,000 sims"}
        </Button>
      </div>

      {state !== "done" ? (
        <div className="z-mc-placeholder">
          <Icon name="target" size={22} />
          <p>{state === "running" ? "Running Monte Carlo simulation…" : "Configure parameters and run the simulation."}</p>
          <span className="z-muted-xs">Uses historical revenue variance from your uploaded data.</span>
        </div>
      ) : (
        <div className="z-mc-result">
          <div className="z-mc-stats">
            <Stat label="Expected return" value={`${D.expected}×`} delta="+18%" deltaTone="up" />
            <Stat label="Best case (95th)" value="1.47×" sub="upside" />
            <Stat label="Worst case (5th)" value={`${D.worst}×`} sub="downside" />
            <Stat label="Prob. of growth" value="78%" delta="favorable" deltaTone="up" />
          </div>
          <div className="z-mc-chart">
            <div className="z-mini-axislabel">Revenue multiple · distribution of {D.simulations.toLocaleString()} simulations</div>
            <Histogram bins={D.bins} counts={D.counts} markers={markers} ci={[D.worst, 1.47]} height={210} />
          </div>
          <div className="z-interp">
            <span className="z-interp-ic"><Icon name="sparkles" size={14} /></span>
            <div>
              <div className="z-interp-lbl">Interpretation</div>
              <p>{D.interpretation}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Obsolescence & Depreciation Radar ──
function Obsolescence() {
  const [items, setItems] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [drilldown, setDrilldown] = React.useState(null);
  const actionTone = { Liquidate: "danger", Discontinue: "danger", Discount: "warn", Maintain: "neutral", Monitor: "success" };

  React.useEffect(() => {
    window.API.getObsolescence()
      .then((data) => setItems(data.items || []))
      .catch((err) => {
        console.warn("Obsolescence fetch failed:", err);
        setError("Could not load obsolescence data. Make sure a data file is uploaded.");
        setItems([]);
      });
  }, []);

  if (items === null) {
    return (
      <div className="z-radar">
        <div className="z-mc-placeholder"><Icon name="scan" size={22} /><p>Loading obsolescence data…</p></div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="z-radar">
        <div className="z-mc-placeholder"><Icon name="scan" size={22} /><p>{error}</p></div>
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="z-radar">
        <div className="z-mc-placeholder"><Icon name="scan" size={22} /><p>Upload a CSV with product data to see the obsolescence radar.</p></div>
      </div>
    );
  }

  return (
    <>
      <div className="z-radar">
        <table className="z-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Category</th>
              <th className="z-num">Velocity Δ</th>
              <th>
                Risk score
                <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 4, color: 'var(--text-3)', fontSize: '0.68rem' }}>
                  (vel×0.4 + cat×0.3 + dep×0.3)
                </span>
              </th>
              <th>Action</th>
              <th style={{ width: 36 }}></th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.name}>
                <td><div className="z-td-strong">{p.name}</div></td>
                <td className="z-td-muted">{p.category || "—"}</td>
                <td className="z-num">
                  <span className={p.velocity_decline_pct > 0 ? "z-neg" : "z-pos"}>
                    {p.velocity_decline_pct > 0 ? "−" : "+"}{Math.abs(p.velocity_decline_pct).toFixed(1)}%
                  </span>
                </td>
                <td>
                  <div className="z-riskcell">
                    <RiskPill level={p.level} score={p.risk} />
                    <span className="z-riskbar">
                      <span className={`z-riskbar-fill z-riskbar-fill--${p.level}`} style={{ width: p.risk + "%" }} />
                    </span>
                  </div>
                </td>
                <td><Badge tone={actionTone[p.action] || "neutral"} dot>{p.action}</Badge></td>
                <td style={{ padding: '0 10px' }}>
                  <RiskInfoButton product={p} onShowMore={setDrilldown} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Full drilldown modal */}
      {drilldown && <ProductDrilldown product={drilldown} onClose={() => setDrilldown(null)} />}
    </>
  );
}

// ── Budget Reallocation Recommender ──
function BudgetRec() {
  const [budgetData, setBudgetData] = React.useState(null);  // null = loading
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    window.API.getBudgetRecs()
      .then((data) => setBudgetData(data))
      .catch((err) => {
        console.warn("Budget recs fetch failed:", err);
        setError("Could not load budget recommendations. Make sure a data file is uploaded.");
        setBudgetData({ increase: [], maintain: [], reduce: [] });
      });
  }, []);

  if (budgetData === null) {
    return (
      <div className="z-budget">
        <div className="z-mc-placeholder"><Icon name="scale" size={22} /><p>Loading budget recommendations…</p></div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="z-budget">
        <div className="z-mc-placeholder"><Icon name="scale" size={22} /><p>{error}</p></div>
      </div>
    );
  }

  const cols = [
    { key: "increase", title: "Increase", icon: "trendUp", tone: "success", items: budgetData.increase || [] },
    { key: "maintain", title: "Maintain", icon: "activity", tone: "neutral", items: budgetData.maintain || [] },
    { key: "reduce", title: "Reduce", icon: "trendDown", tone: "danger", items: budgetData.reduce || [] },
  ];

  const hasData = cols.some((c) => c.items.length > 0);
  if (!hasData) {
    return (
      <div className="z-budget">
        <div className="z-mc-placeholder"><Icon name="scale" size={22} /><p>Upload a CSV with product and revenue data to see budget recommendations.</p></div>
      </div>
    );
  }

  return (
    <div className="z-budget">
      {cols.map((c) => (
        <div key={c.key} className="z-budget-col">
          <div className="z-budget-hd">
            <span className={`z-budget-ic z-budget-ic--${c.tone}`}><Icon name={c.icon} size={14} stroke={2} /></span>
            <span className="z-budget-ttl">{c.title}</span>
            <span className="z-budget-count">{c.items.length}</span>
          </div>
          <div className="z-budget-cards">
            {c.items.length === 0
              ? <div className="z-td-muted" style={{ padding: "8px 0", fontSize: "0.8rem" }}>None in this category</div>
              : c.items.map((it, i) => (
                  <div key={i} className="z-budget-card">
                    <div className="z-budget-card-hd">
                      <span className="z-budget-prod">{it.product}</span>
                      <Badge tone={it.confidence === "high" ? "accent" : "neutral"}>{it.confidence}</Badge>
                    </div>
                    <p className="z-budget-rat">{it.rationale}</p>
                  </div>
                ))
            }
          </div>
        </div>
      ))}
    </div>
  );
}

const POWER_TABS = [
  { value: "montecarlo", label: "Monte Carlo", icon: "target" },
  { value: "obsolescence", label: "Obsolescence radar", icon: "scan" },
  { value: "budget", label: "Budget recommender", icon: "scale" },
];

function PowerSection({ mode = "inline", tab, onTab }) {
  const Module = { montecarlo: MonteCarlo, obsolescence: Obsolescence, budget: BudgetRec }[tab];

  if (mode === "inline") {
    return (
      <div className="z-power-inline">
        <Card title="Monte Carlo investment simulator" subtitle="Probabilistic outcome of a budget change" icon="target"><MonteCarlo /></Card>
        <Card title="Obsolescence & depreciation radar" subtitle="Risk-scored end-of-life signals" icon="scan"><Obsolescence /></Card>
        <Card title="Budget reallocation recommender" subtitle="ROI-ranked investment guidance" icon="scale"><BudgetRec /></Card>
      </div>
    );
  }
  // tabbed + focus share the tabbed body
  return (
    <Card className="z-power-tabbed" pad={false}>
      <div className="z-power-tabs">
        <Segmented value={tab} options={POWER_TABS} onChange={onTab} />
      </div>
      <div className="z-power-tabbody"><Module /></div>
    </Card>
  );
}

Object.assign(window, {
  MonteCarlo, Obsolescence, BudgetRec, PowerSection, POWER_TABS, Select,
  SparklineChart, BreakdownBar, RiskInfoButton, ProductDrilldown,
});
