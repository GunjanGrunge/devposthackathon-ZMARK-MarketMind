// components.jsx — shared UI primitives. Styling lives in the HTML <style> block;
// these are thin wrappers so markup stays consistent and direct-editable.

function Button({ variant = "secondary", size = "md", icon, iconRight, active, children, className = "", ...rest }) {
  const cls = ["z-btn", `z-btn--${variant}`, size === "sm" && "z-btn--sm",
    !children && "z-btn--icon", active && "is-active", className].filter(Boolean).join(" ");
  const isz = size === "sm" ? 14 : 16;
  return (
    <button className={cls} {...rest}>
      {icon && <Icon name={icon} size={isz} />}
      {children}
      {iconRight && <Icon name={iconRight} size={isz} />}
    </button>
  );
}

function Badge({ tone = "neutral", dot, icon, children }) {
  return (
    <span className={`z-badge z-badge--${tone}`}>
      {dot && <i className="z-badge-dot" />}
      {icon && <Icon name={icon} size={11} stroke={2} />}
      {children}
    </span>
  );
}

function Card({ title, subtitle, actions, icon, children, className = "", pad = true, ...rest }) {
  return (
    <section className={`z-card ${className}`} {...rest}>
      {(title || actions) && (
        <header className="z-card-hd">
          <div className="z-card-hd-l">
            {icon && <span className="z-card-ic"><Icon name={icon} size={15} /></span>}
            <div>
              <div className="z-card-ttl">{title}</div>
              {subtitle && <div className="z-card-sub">{subtitle}</div>}
            </div>
          </div>
          {actions && <div className="z-card-actions">{actions}</div>}
        </header>
      )}
      <div className={pad ? "z-card-body" : "z-card-body z-card-body--flush"}>{children}</div>
    </section>
  );
}

function Switch({ checked, onChange, id }) {
  return (
    <button type="button" role="switch" aria-checked={!!checked} id={id}
      className="z-switch" data-on={checked ? "1" : "0"}
      onClick={() => onChange(!checked)}><i /></button>
  );
}

function Segmented({ value, options, onChange, size = "md", grow }) {
  return (
    <div className={`z-seg ${size === "sm" ? "z-seg--sm" : ""} ${grow ? "z-seg--grow" : ""}`} role="tablist">
      {options.map((o) => {
        const opt = typeof o === "object" ? o : { value: o, label: o };
        return (
          <button key={opt.value} role="tab" data-on={opt.value === value ? "1" : "0"}
            onClick={() => onChange(opt.value)}>
            {opt.icon && <Icon name={opt.icon} size={14} />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function Logo({ size = 17, showWord = true, tileScale = 1.5 }) {
  const tile = Math.round(size * tileScale);
  return (
    <div className="z-logo">
      <span className="z-logo-mark" style={{ width: tile, height: tile }}>
        <svg viewBox="0 0 24 24" width={Math.round(tile * 0.6)} height={Math.round(tile * 0.6)}>
          <path d="M7 7h10L7 17h10" fill="none" stroke="#fff" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      {showWord && <span className="z-logo-word" style={{ fontSize: size }}>ZmaRk</span>}
    </div>
  );
}

const FILE_ICON = { csv: "table", pdf: "fileText", xlsx: "sheet", xls: "sheet" };
function FileTypeIcon({ type, size = 16 }) {
  return <Icon name={FILE_ICON[type] || "fileText"} size={size} />;
}

function Stat({ label, value, delta, deltaTone = "neutral", sub }) {
  return (
    <div className="z-stat">
      <div className="z-stat-label">{label}</div>
      <div className="z-stat-row">
        <span className="z-stat-value">{value}</span>
        {delta != null && (
          <span className={`z-stat-delta z-stat-delta--${deltaTone}`}>
            <Icon name={deltaTone === "down" ? "arrowDownRight" : "arrowUpRight"} size={13} stroke={2} />
            {delta}
          </span>
        )}
      </div>
      {sub && <div className="z-stat-sub">{sub}</div>}
    </div>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  return (
    <span className="z-conf" title={`${pct}% confidence`}>
      <span className="z-conf-track"><span className="z-conf-fill" style={{ width: pct + "%" }} /></span>
      <span className="z-conf-num">{pct}%</span>
    </span>
  );
}

function RiskPill({ level, score }) {
  return <span className={`z-risk z-risk--${level}`}><span className="z-risk-dot" />{score}</span>;
}

Object.assign(window, { Button, Badge, Card, Switch, Segmented, Logo, FileTypeIcon, Stat, ConfidenceBar, RiskPill });
