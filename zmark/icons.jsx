// icons.jsx — Lucide-style thin-line icons as a single <Icon name=…/> component.
// 24×24 grid, currentColor stroke, round caps. No emoji anywhere in the app.

const Z_ICONS = {
  upload: <><path d="M12 15V3" /><path d="m7 8 5-5 5 5" /><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" /></>,
  add: <><path d="M12 5v14M5 12h14" /></>,
  fileText: <><path d="M14 3v5h5" /><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M9 13h6" /><path d="M9 17h4" /></>,
  table: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M9 4v16" /></>,
  sheet: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M3 15h18M9 3v18M15 3v18" /></>,
  barChart: <><line x1="3" y1="20.5" x2="21" y2="20.5" /><line x1="6.5" y1="20" x2="6.5" y2="11" /><line x1="12" y1="20" x2="12" y2="5" /><line x1="17.5" y1="20" x2="17.5" y2="14" /></>,
  trendUp: <><path d="M3 17l6-6 4 4 8-8" /><path d="M17 7h4v4" /></>,
  trendDown: <><path d="M3 7l6 6 4-4 8 8" /><path d="M17 17h4v-4" /></>,
  activity: <><path d="M3 12h4l3 8 4-16 3 8h4" /></>,
  message: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>,
  send: <><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4z" /></>,
  sparkles: <><path d="M12 3l1.7 4.6L18 9l-4.3 1.4L12 15l-1.7-4.6L6 9l4.3-1.4z" /><path d="M19 14l.6 1.7 1.7.6-1.7.6L19 19l-.6-1.5-1.7-.6 1.7-.6z" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" /></>,
  moon: <><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></>,
  zap: <><path d="M13 2 3 14h7l-1 8 10-12h-7z" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></>,
  folder: <><path d="M3 7a2 2 0 0 1 2-2h3.5l2 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></>,
  x: <><path d="M18 6 6 18M6 6l12 12" /></>,
  chevronRight: <><path d="m9 6 6 6-6 6" /></>,
  chevronDown: <><path d="m6 9 6 6 6-6" /></>,
  chevronLeft: <><path d="m15 6-6 6 6 6" /></>,
  check: <><path d="M20 6 9 17l-5-5" /></>,
  checkCircle: <><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  alert: <><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 8h.01" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>,
  sliders: <><path d="M3 6h18M3 12h18M3 18h18" /><circle cx="8" cy="6" r="2.2" fill="var(--surface)" /><circle cx="16" cy="12" r="2.2" fill="var(--surface)" /><circle cx="10" cy="18" r="2.2" fill="var(--surface)" /></>,
  refresh: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></>,
  panelLeft: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" /></>,
  more: <><circle cx="5" cy="12" r="1.4" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1.4" fill="currentColor" stroke="none" /></>,
  arrowUpRight: <><path d="M7 17 17 7" /><path d="M8 7h9v9" /></>,
  arrowDownRight: <><path d="M7 7l10 10" /><path d="M17 8v9H8" /></>,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" /></>,
  scan: <><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" /><path d="M7 12h10" /></>,
  scale: <><path d="M12 3v18" /><path d="M6.5 21h11" /><path d="M5 3h14" /><path d="m3 9 3-5 3 5a3 3 0 0 1-6 0z" /><path d="m15 9 3-5 3 5a3 3 0 0 1-6 0z" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
  user: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="10" r="3" /><path d="M6.5 19.2a6 6 0 0 1 11 0" /></>,
  loader: <><path d="M12 3v3M12 18v3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M3 12h3M18 12h3M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /></>,
  dot: <><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" /></>,
  book: <><path d="M2 4.5h7a2 2 0 0 1 2 2V20a2 2 0 0 0-2-2H2z" /><path d="M22 4.5h-7a2 2 0 0 0-2 2V20a2 2 0 0 1 2-2h7z" /></>,
  download: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  filter: <><path d="M3 5h18l-7 8v5l-4 2v-7z" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="2" /><rect x="9.5" y="9.5" width="5" height="5" rx="1" /><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" /></>,
  flag: <><path d="M5 21V4" /><path d="M5 4h11l-2 4 2 4H5" /></>,
  plug: <><path d="M9 2v5M15 2v5" /><path d="M6 7h12v3a6 6 0 0 1-12 0z" /><path d="M12 16v6" /></>,
  cloud: <><path d="M17.5 19a4.5 4.5 0 0 0 .5-8.97 6 6 0 0 0-11.64-1.2A4 4 0 0 0 6.5 19z" /></>,
  warehouse: <><path d="M3 21V8l9-4 9 4v13" /><path d="M3 21h18" /><path d="M7 21v-7h10v7" /><path d="M7 14h10" /></>,
  funnel: <><path d="M3 5h18l-7 8v6l-4-2v-4z" /></>,
  lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
};

function Icon({ name, size = 16, stroke = 1.75, className, style }) {
  if (name === "sqlDatabase") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <ellipse cx="12" cy="5" rx="9" ry="3" fill="#336791" fillOpacity="0.8" />
        <path d="M3 5v6c0 1.66 4.03 3 9 3s9-1.34 9-3V5" stroke="#336791" strokeWidth="1.5" />
        <ellipse cx="12" cy="11" rx="9" ry="3" fill="#00758F" fillOpacity="0.8" />
        <path d="M3 11v6c0 1.66 4.03 3 9 3s9-1.34 9-3v-6" stroke="#00758F" strokeWidth="1.5" />
        <path d="M3 17v2c0 1.66 4.03 3 9 3s9-1.34 9-3v-2" stroke="#f29111" strokeWidth="1.5" strokeDasharray="3 2" />
      </svg>
    );
  }
  if (name === "googleAnalytics") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <rect x="3" y="13" width="4" height="8" rx="1.5" fill="#F9AB00" />
        <rect x="10" y="8" width="4" height="13" rx="1.5" fill="#E37400" />
        <rect x="17" y="3" width="4" height="18" rx="1.5" fill="#F4B400" />
      </svg>
    );
  }
  if (name === "bigQuery") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <path d="M12 2L3 7.2v9.6L12 22l9-5.2V7.2L12 2z" stroke="#4285F4" strokeWidth="1.5" fill="#4285F4" fillOpacity="0.1" />
        <circle cx="12" cy="12" r="3.5" fill="#EA4335" />
        <circle cx="7.5" cy="9.5" r="2.5" fill="#FBBC05" />
        <circle cx="16.5" cy="9.5" r="2.5" fill="#34A853" />
        <path d="M12 12l-4.5-2.5M12 12l4.5-2.5" stroke="#4285F4" strokeWidth="1.5" />
      </svg>
    );
  }
  if (name === "salesforce") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <path d="M19.4 10.4a3.7 3.7 0 0 0-3.7-3.7c-.3 0-.7 0-1 .1a5.1 5.1 0 0 0-9.2 1.8 3.4 3.4 0 0 0-3.3 3.4 3.4 3.4 0 0 0 3.4 3.4h13.7a2.9 2.9 0 0 0 2.9-2.9 2.9 2.9 0 0 0-2.8-2.1z" fill="#00A1E0" />
      </svg>
    );
  }
  if (name === "hubspot") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <circle cx="12" cy="12" r="3.5" stroke="#FF7A59" strokeWidth="2.5" />
        <path d="M12 8.5V4M9.5 14.5l-3.5 2M14.5 14.5l3.5 2" stroke="#FF7A59" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="12" cy="4" r="2" fill="#FF7A59" />
        <circle cx="5" cy="17.5" r="2" fill="#FF7A59" />
        <circle cx="19" cy="17.5" r="2" fill="#FF7A59" />
      </svg>
    );
  }
  if (name === "snowflake") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
        <path d="M12 2v20M2 12h20M19 5L5 19M19 19L5 5" stroke="#29B6F6" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M12 6l-2.5-2.5M12 6L14.5 3.5M12 18l-2.5 2.5M12 18l2.5-2.5M6 12L3.5 9.5M6 12l-2.5 2.5M18 12l2.5-2.5M18 12l2.5 2.5" stroke="#29B6F6" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }

  const inner = Z_ICONS[name] || Z_ICONS.dot;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={stroke} strokeLinecap="round"
      strokeLinejoin="round" className={className} style={style} aria-hidden="true">
      {inner}
    </svg>
  );
}

function Spinner({ size = 16, stroke = 1.75, style }) {
  return <Icon name="loader" size={size} stroke={stroke} style={{ animation: "zspin 0.9s linear infinite", ...style }} />;
}

Object.assign(window, { Icon, Spinner, Z_ICONS });
