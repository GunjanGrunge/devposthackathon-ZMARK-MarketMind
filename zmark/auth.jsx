// auth.jsx — Login + Welcome screens. Premium enterprise feel.

// ── Login ──
function LoginPage({ onLogin, theme, onTheme }) {
  const [email, setEmail] = React.useState("");
  const [pass, setPass] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const submit = (e) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); onLogin(); }, 900);
  };

  return (
    <div className="z-login">
      {/* ── Left brand panel ── */}
      <div className="z-login-brand">
        <div className="z-login-brand-inner">
          <Logo size={22} />
          <h1 className="z-login-h1">From spreadsheets to strategy in&nbsp;seconds.</h1>
          <p className="z-login-tagline">Upload your data. Get cited answers, real-time charts, and AI&#8209;powered simulations — all grounded in what you uploaded, never hallucinated.</p>

          <div className="z-login-features">
            <div className="z-login-feat">
              <span className="z-login-feat-ic"><Icon name="barChart" size={18} /></span>
              <div>
                <div className="z-login-feat-t">Instant EDA</div>
                <div className="z-login-feat-d">Upload CSV, Excel, or PDF — charts and anomaly detection appear in seconds</div>
              </div>
            </div>
            <div className="z-login-feat">
              <span className="z-login-feat-ic"><Icon name="sparkles" size={18} /></span>
              <div>
                <div className="z-login-feat-t">Cited answers</div>
                <div className="z-login-feat-d">Every insight links to the exact rows or pages it came from</div>
              </div>
            </div>
            <div className="z-login-feat">
              <span className="z-login-feat-ic"><Icon name="target" size={18} /></span>
              <div>
                <div className="z-login-feat-t">Monte Carlo simulations</div>
                <div className="z-login-feat-d">10,000-run probabilistic forecasts on your actual revenue data</div>
              </div>
            </div>
          </div>

          {/* decorative abstract grid motif */}
          <div className="z-login-motif" aria-hidden="true">
            <svg viewBox="0 0 280 120" fill="none">
              <line x1="0" y1="100" x2="40" y2="82" stroke="rgba(255,255,255,.12)" strokeWidth="1.5" />
              <line x1="40" y1="82" x2="80" y2="88" stroke="rgba(255,255,255,.12)" strokeWidth="1.5" />
              <line x1="80" y1="88" x2="120" y2="56" stroke="rgba(255,255,255,.18)" strokeWidth="1.5" />
              <line x1="120" y1="56" x2="160" y2="62" stroke="rgba(255,255,255,.18)" strokeWidth="1.5" />
              <line x1="160" y1="62" x2="200" y2="34" stroke="rgba(255,255,255,.22)" strokeWidth="1.5" />
              <line x1="200" y1="34" x2="240" y2="18" stroke="rgba(255,255,255,.28)" strokeWidth="1.5" />
              <line x1="240" y1="18" x2="280" y2="10" stroke="rgba(255,255,255,.28)" strokeWidth="1.5" />
              {[0,40,80,120,160,200,240,280].map((x,i)=>{const y=[100,82,88,56,62,34,18,10][i]; return <circle key={i} cx={x} cy={y} r="3" fill="rgba(255,255,255,.22)"/>;} )}
              {/* gridlines */}
              {[0,30,60,90,120].map(y=><line key={y} x1="0" y1={y} x2="280" y2={y} stroke="rgba(255,255,255,.04)" strokeWidth="1" />)}
            </svg>
          </div>
        </div>
        <div className="z-login-brand-foot">
          <span>Gemini 2.5 Pro</span>
          <span className="z-login-dot" />
          <span>Elastic hybrid search</span>
          <span className="z-login-dot" />
          <span>Google Cloud</span>
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="z-login-form-wrap">
        <div className="z-login-form-top">
          <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
        </div>
        <div className="z-login-form-center">
          <div className="z-login-form-hd">
            <h2 className="z-login-form-ttl">Sign in to ZmaRk</h2>
            <p className="z-login-form-sub">Enter your credentials to access the platform</p>
          </div>

          <div className="z-sso-group">
            <button className="z-sso-btn" onClick={submit} type="button">
              <svg width="16" height="16" viewBox="0 0 48 48"><path d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z" fill="#4285F4"/><path d="M4.7 14.7l7 5.1C13.4 16 18.3 13 24 13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 15.4 2 8 7.2 4.7 14.7z" fill="#EA4335"/><path d="M24 46c5.4 0 10.3-1.8 14.1-5l-6.9-5.6C29.2 37 26.7 38 24 38c-6 0-11.2-4-13-9.7l-7 5.4C7.5 40.6 15.2 46 24 46z" fill="#34A853"/><path d="M46 24c0-1.3-.2-2.7-.5-4H24v8.5h11.8c-1 3-2.9 5.4-5.4 7l6.9 5.6C41.5 37.5 46 31.5 46 24z" fill="#4285F4"/></svg>
              Continue with Google
            </button>
            <button className="z-sso-btn" onClick={submit} type="button">
              <svg width="16" height="16" viewBox="0 0 23 23"><path fill="#f25022" d="M0 0h11v11H0z"/><path fill="#00a4ef" d="M0 12h11v11H0z"/><path fill="#7fba00" d="M12 0h11v11H12z"/><path fill="#ffb900" d="M12 12h11v11H12z"/></svg>
              Continue with Microsoft
            </button>
          </div>

          <div className="z-login-divider"><span>or sign in with email</span></div>

          <form className="z-login-fields" onSubmit={submit}>
            <label className="z-field">
              <span className="z-field-lbl">Work email</span>
              <input type="email" className="z-field-input" placeholder="you@company.com"
                value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </label>
            <label className="z-field">
              <div className="z-field-lbl-row">
                <span className="z-field-lbl">Password</span>
                <a href="#" className="z-field-link" onClick={(e) => e.preventDefault()}>Forgot password?</a>
              </div>
              <input type="password" className="z-field-input" placeholder="Enter your password"
                value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="current-password" />
            </label>
            <Button variant="primary" style={{ width: "100%", height: 40, marginTop: 4 }}
              disabled={loading} onClick={submit}>
              {loading ? <><Spinner size={15} /> Signing in…</> : "Sign in"}
            </Button>
          </form>

          <div className="z-login-saml">
            <Icon name="lock" size={13} />
            <span>Enterprise SSO (SAML / OIDC) available</span>
          </div>
        </div>
        <div className="z-login-form-foot">
          Don't have an account? <a href="#" className="z-link" onClick={(e) => { e.preventDefault(); submit(e); }}>Request access</a>
        </div>
      </div>
    </div>
  );
}

// ── Welcome ──
const WELCOME_FEATURES = [
  {
    icon: "upload", title: "Upload anything",
    desc: "Drag in CSVs, spreadsheets, and PDFs. ZmaRk parses, detects schemas, and indexes everything into Elastic — ready to query in seconds.",
    tag: "Core",
  },
  {
    icon: "barChart", title: "Instant analysis",
    desc: "Revenue trends, product rankings, channel performance, and anomaly detection — generated automatically from your data, no configuration required.",
    tag: "Auto EDA",
  },
  {
    icon: "sparkles", title: "AI chat with citations",
    desc: "Ask any question in plain English. Answers are retrieved via hybrid search (BM25 + vector) and cite the exact rows and pages they came from.",
    tag: "Grounded",
  },
  {
    icon: "target", title: "Monte Carlo simulator",
    desc: "Run 10,000 probabilistic simulations on budget changes. See expected return, best/worst cases, and 95% confidence intervals — all from your actuals.",
    tag: "Power Mode",
  },
  {
    icon: "scan", title: "Obsolescence radar",
    desc: "Risk-scored product table tracking velocity declines, age-based depreciation, and compliance exposure. Stop investing before it's too late.",
    tag: "Power Mode",
  },
  {
    icon: "scale", title: "Budget recommender",
    desc: "ROI-ranked reallocation guidance: where to increase, maintain, or reduce spend — with confidence levels and the data behind each recommendation.",
    tag: "Power Mode",
  },
];

function WelcomePage({ onContinue, theme, onTheme, userName }) {
  return (
    <div className="z-welcome">
      <header className="z-welcome-top">
        <Logo size={17} />
        <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
      </header>

      <main className="z-welcome-main">
        <div className="z-welcome-hero">
          <div className="z-welcome-eyebrow"><Icon name="sparkles" size={13} /> Welcome to ZmaRk</div>
          <h1 className="z-welcome-h1">Intelligence, grounded in your&nbsp;data.</h1>
          <p className="z-welcome-sub">ZmaRk is a business intelligence agent that reads your spreadsheets, indexes them for semantic search, and turns raw numbers into cited, actionable insights — in real time.</p>
        </div>

        <div className="z-welcome-usp">
          <div className="z-welcome-usp-item">
            <div className="z-welcome-usp-num">10k</div>
            <div className="z-welcome-usp-lbl">Monte Carlo sims per run</div>
          </div>
          <div className="z-welcome-usp-sep" />
          <div className="z-welcome-usp-item">
            <div className="z-welcome-usp-num">100%</div>
            <div className="z-welcome-usp-lbl">Answers cited to source</div>
          </div>
          <div className="z-welcome-usp-sep" />
          <div className="z-welcome-usp-item">
            <div className="z-welcome-usp-num">0</div>
            <div className="z-welcome-usp-lbl">Data stored post-session</div>
          </div>
        </div>

        <div className="z-welcome-grid">
          {WELCOME_FEATURES.map((f) => (
            <div key={f.title} className="z-wcard">
              <div className="z-wcard-top">
                <span className="z-wcard-ic"><Icon name={f.icon} size={18} /></span>
                <Badge tone={f.tag === "Power Mode" ? "accent" : "neutral"}>{f.tag}</Badge>
              </div>
              <div className="z-wcard-ttl">{f.title}</div>
              <p className="z-wcard-desc">{f.desc}</p>
            </div>
          ))}
        </div>

        <div className="z-welcome-cta">
          <Button variant="primary" iconRight="chevronRight" onClick={onContinue}
            style={{ height: 44, padding: "0 28px", fontSize: 15 }}>
            Start your first session
          </Button>
          <p className="z-welcome-cta-sub">No credit card required. Your data is never stored beyond the session.</p>
        </div>
      </main>

      <footer className="z-welcome-foot">
        <span>Powered by</span>
        <b>Gemini 2.5 Pro</b>
        <span className="z-login-dot" />
        <b>Elastic</b>
        <span className="z-login-dot" />
        <b>Google Cloud Agent Builder</b>
      </footer>
    </div>
  );
}

Object.assign(window, { LoginPage, WelcomePage, WELCOME_FEATURES });
