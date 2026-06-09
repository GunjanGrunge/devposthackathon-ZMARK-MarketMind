/* ZmaRk — demo dataset (gaming / electronics marketing analytics).
   Plain script: sets window.ZDATA before the React/Babel scripts run. */
(function () {
  // ── Revenue trend: 24 months, thousands of USD, one injected anomaly ──
  const MONTHS = [
    "Jan ’24","Feb ’24","Mar ’24","Apr ’24","May ’24","Jun ’24",
    "Jul ’24","Aug ’24","Sep ’24","Oct ’24","Nov ’24","Dec ’24",
    "Jan ’25","Feb ’25","Mar ’25","Apr ’25","May ’25","Jun ’25",
    "Jul ’25","Aug ’25","Sep ’25","Oct ’25","Nov ’25","Dec ’25",
  ];
  const TREND = [
    96,102,99,108,114,111,119,124,121,132,145,158,
    138,142,149,151,147,156,162,104,168,174,188,201,
  ];
  const ANOMALY_INDEX = 19; // Aug ’25 — ~37% drop vs expected

  // ── Products ──
  const PRODUCTS = [
    { name: "RTX 4070",          sku: "GPU-4070",  category: "GPUs",        channel: "Online",      revenue: 84200, velocity: 42, growth:  18, risk: 22, level: "low",    action: "Monitor" },
    { name: "PS5 DualSense",     sku: "ACC-DS5",   category: "Accessories", channel: "Marketplace", revenue: 62400, velocity: 38, growth:  22, risk: 18, level: "low",    action: "Monitor" },
    { name: "Gaming Monitor 27”",sku: "DSP-27Q",   category: "Displays",    channel: "Retail",      revenue: 51800, velocity: 24, growth:   6, risk: 34, level: "low",    action: "Monitor" },
    { name: "Mech Keyboard TKL", sku: "PER-TKL",   category: "Peripherals", channel: "Online",      revenue: 38600, velocity: 31, growth:   3, risk: 41, level: "medium", action: "Maintain" },
    { name: "NVMe SSD 2TB",      sku: "STG-2TB",   category: "Storage",     channel: "Online",      revenue: 33200, velocity: 19, growth:  -4, risk: 52, level: "medium", action: "Discount" },
    { name: "Headset Pro X",     sku: "ACC-HSX",   category: "Accessories", channel: "Retail",      revenue: 27500, velocity: 22, growth:  -9, risk: 58, level: "medium", action: "Discount" },
    { name: "RTX 3060",          sku: "GPU-3060",  category: "GPUs",        channel: "Marketplace", revenue: 21400, velocity:  9, growth: -61, risk: 84, level: "high",   action: "Liquidate" },
    { name: "1080p Webcam",      sku: "PER-CAM1",  category: "Peripherals", channel: "Online",      revenue: 12800, velocity:  6, growth: -38, risk: 71, level: "high",   action: "Discontinue" },
  ];

  const CHANNELS = [
    { label: "Online",      value: 312400 },
    { label: "Retail",      value: 168200 },
    { label: "Marketplace", value:  96800 },
  ];

  const CATEGORIES = [
    { label: "GPUs",        value: 105600 },
    { label: "Accessories", value:  89900 },
    { label: "Displays",    value:  51800 },
    { label: "Peripherals", value:  51400 },
    { label: "Storage",     value:  33200 },
  ];

  // ── Monte Carlo distribution (revenue multiple), pre-baked bell curve ──
  const MC_BINS = [];
  const MC_COUNTS = [];
  (function () {
    const mean = 1.18, sd = 0.17;
    for (let i = 0; i < 26; i++) {
      const x = 0.55 + i * 0.05;
      MC_BINS.push(Number(x.toFixed(2)));
      const z = (x - mean) / sd;
      MC_COUNTS.push(Math.round(9600 * Math.exp(-0.5 * z * z)));
    }
  })();

  // ── Files in the session ──
  const FILES = [
    { id: "f1", name: "sales_2024_2025.csv", type: "csv", size: "1.8 MB", rows: 1000, status: "indexed" },
    { id: "f2", name: "eu_packaging_directive.pdf", type: "pdf", size: "412 KB", pages: 12, status: "indexed" },
    { id: "f3", name: "q4_marketing_budget.xlsx", type: "xlsx", size: "286 KB", rows: 64, status: "indexed" },
  ];

  const SCHEMA = {
    file: "sales_2024_2025.csv",
    rows: 1000,
    columns: [
      { name: "order_date",   type: "date",     role: "Date",        confidence: 0.98 },
      { name: "product_name", type: "string",   role: "Product",     confidence: 0.96 },
      { name: "category",     type: "string",   role: "Category",    confidence: 0.93 },
      { name: "channel",      type: "string",   role: "Channel",     confidence: 0.88 },
      { name: "units_sold",   type: "numeric",  role: "Quantity",    confidence: 0.95 },
      { name: "unit_price",   type: "currency", role: "Unit price",  confidence: 0.91 },
      { name: "revenue",      type: "currency", role: "Revenue",     confidence: 0.97 },
    ],
  };

  const SUMMARY =
    "Revenue is up 23% across the two-year window, led by your GPUs and Accessories lines — the RTX 4070 and PS5 DualSense are your strongest performers this quarter. A sharp 37% revenue drop in Aug ’25 was flagged as an anomaly and is worth investigating. Two SKUs are trending toward end-of-life: the RTX 3060 is down 61% and the 1080p Webcam down 38% over 90 days, both showing age-based depreciation risk.";

  const SUGGESTED = [
    "What was my best-performing month?",
    "Which product has the highest sales velocity?",
    "Are there any at-risk products?",
  ];

  // ── Seeded chat thread (shown in the in-depth chat view) ──
  const CHAT = [
    { role: "user", content: "Which products should I stop investing in?" },
    {
      role: "assistant",
      content:
        "Based on your uploaded data, two SKUs show clear stop-loss signals. The RTX 3060 has declined 61% over the last 90 days, with sales velocity down to 9 units/month — well below its category average. The 1080p Webcam is down 38% and carries age-based depreciation risk on an 18-month cycle. Both also fall under the new EU packaging directive, which adds compliance cost to these lower-margin SKUs. I’d recommend liquidating RTX 3060 inventory and discontinuing the webcam.",
      citations: [
        { source: "sales_2024_2025.csv", ref: "rows 142–189", excerpt: "RTX 3060 revenue declined 41% QoQ; units_sold fell from 23 to 9 over the trailing 90-day window." },
        { source: "eu_packaging_directive.pdf", ref: "page 3", excerpt: "Electronic peripherals placed on the market after Q1 2026 are subject to revised recyclable-packaging declarations." },
      ],
      followups: ["What discount strategy would help?", "Which channel is underperforming?"],
    },
  ];

  // ── Monte Carlo result ──
  const MONTECARLO = {
    product: "RTX 4070",
    budgetChange: 30,
    horizon: 90,
    simulations: 10000,
    best: 1.42,
    expected: 1.18,
    worst: 0.83,
    ci95: [0.91, 1.47],
    bins: MC_BINS,
    counts: MC_COUNTS,
    interpretation:
      "With a 30% budget increase over 90 days, there is a 78% probability of revenue growth, with an expected return of 1.18× current revenue. Downside risk is modest — even the 5th-percentile case retains 83% of current revenue.",
  };

  // ── Budget reallocation ──
  const BUDGET = {
    increase: [
      { product: "PS5 DualSense", rationale: "Revenue CAGR +22% over 6 months; velocity holding above category mean.", confidence: "high" },
      { product: "RTX 4070",      rationale: "+18% growth and the highest absolute revenue contribution this quarter.", confidence: "high" },
    ],
    maintain: [
      { product: "Gaming Monitor 27”", rationale: "Stable velocity; +6% growth with no decline signal.", confidence: "medium" },
      { product: "Mech Keyboard TKL",  rationale: "Flat but profitable; no reallocation trigger met.", confidence: "medium" },
    ],
    reduce: [
      { product: "RTX 3060",     rationale: "Sales velocity down 61% over 90 days; high obsolescence risk.", confidence: "high" },
      { product: "1080p Webcam", rationale: "Down 38% with age-based depreciation on an 18-month cycle.", confidence: "high" },
    ],
  };

  window.ZDATA = {
    MONTHS, TREND, ANOMALY_INDEX, PRODUCTS, CHANNELS, CATEGORIES,
    FILES, SCHEMA, SUMMARY, SUGGESTED, CHAT, MONTECARLO, BUDGET,
  };
})();
