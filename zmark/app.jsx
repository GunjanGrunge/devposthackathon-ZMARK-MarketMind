// app.jsx — ZmaRk root: flow state machine, dashboard layout composition,
// chat responder, theme/accent/density application, and Tweaks panel.
// v2: wired to FastAPI backend via window.API

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "dark": false,
  "accent": "#4f46e5",
  "density": "compact",
  "dashLayout": "standard",
  "chartStyle": "grid",
  "chatPlacement": "right",
  "powerPresentation": "tabbed"
}/*EDITMODE-END*/;

const LS = {
  get: (k, d) => { try { const v = localStorage.getItem("zmark." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set: (k, v) => { try { localStorage.setItem("zmark." + k, JSON.stringify(v)); } catch (e) {} },
};

// ── Session-aware data state ──────────────────────────────────────────────
// dashData mirrors the /api/v1/dashboard response; starts as null (loading).
// sessionFiles mirrors /api/v1/session/files.
// Both are loaded/refreshed after every file upload.

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [screen, setScreenRaw] = React.useState(() => LS.get("screen", "login"));
  const [powerMode, setPowerModeRaw] = React.useState(() => LS.get("power", false));
  const [powerTab, setPowerTab] = React.useState("montecarlo");
  const [focusView, setFocusView] = React.useState("power");
  const [messages, setMessages] = React.useState([]);
  const [sending, setSending] = React.useState(false);
  const [overlayOpen, setOverlayOpen] = React.useState(false);

  // ── Live data from backend ──
  const [dashData, setDashData] = React.useState(null);     // null = not yet loaded
  const [sessionFiles, setSessionFiles] = React.useState([]); // []  = no files yet
  const [dashLoading, setDashLoading] = React.useState(false);
  const [backendUp, setBackendUp] = React.useState(true);

  // ── Uploaded file state (for schema screen) ──
  const [lastUpload, setLastUpload] = React.useState(null);  // { file_id, filename, … }
  const [schemaData, setSchemaData] = React.useState(null);  // { columns: [] }

  // ── Upload progress: track files being dropped ──
  const [pendingFiles, setPendingFiles] = React.useState([]); // File[] objects

  const timer = React.useRef(null);

  const setScreen = (s) => { setScreenRaw(s); LS.set("screen", s); };
  const setPowerMode = (v) => { setPowerModeRaw(v); LS.set("power", v); if (v) setFocusView("power"); };

  // ── Theme application ──
  React.useEffect(() => {
    const r = document.documentElement;
    r.classList.add("z-theme-switching");
    r.setAttribute("data-theme", t.dark ? "dark" : "light");
    r.setAttribute("data-density", t.density);
    r.style.setProperty("--accent", t.accent);
    void r.offsetHeight;
    const id = requestAnimationFrame(() => r.classList.remove("z-theme-switching"));
    return () => cancelAnimationFrame(id);
  }, [t.dark, t.density, t.accent]);

  // ── Refresh dashboard + files from backend ──
  const refreshDashboard = React.useCallback(async () => {
    setDashLoading(true);
    try {
      const [dash, files] = await Promise.all([
        window.API.getDashboard(),
        window.API.getSessionFiles(),
      ]);
      setDashData(dash);
      setSessionFiles(files.files || []);
    } catch (err) {
      console.warn("Dashboard refresh failed:", err);
    } finally {
      setDashLoading(false);
    }
  }, []);

  // ── Chat: call real backend ──
  const handleSend = async (text) => {
    setMessages((m) => [...m, { role: "user", content: text }]);
    setSending(true);
    clearTimeout(timer.current);
    try {
      const history = messages.slice(-8).map((m) => ({ role: m.role, content: m.content }));
      const res = await window.API.chat(text, history);
      const msg = res.message || {};
      setMessages((m) => [...m, {
        role: "assistant",
        content: msg.content || "Sorry, I couldn't get an answer.",
        citations: msg.citations || undefined,
        followups: msg.followups || undefined,
      }]);
    } catch (err) {
      // Fallback to canned local respond() when backend is unreachable
      setMessages((m) => [...m, respondFallback(text)]);
    } finally {
      setSending(false);
    }
  };

  // ── Upload flow: triggered by Landing drop zone or "Add files" ──
  const handleFilesSelected = async (files) => {
    if (!files || files.length === 0) return;
    setPendingFiles(Array.from(files));
    setScreen("uploading");
    // Actual upload happens inside UploadProgress via the onUploadFiles callback
  };

  const handleUploadComplete = async (uploadResults) => {
    // uploadResults = array of { file_id, filename, … }
    if (uploadResults && uploadResults.length > 0) {
      setLastUpload(uploadResults[0]);
      // Fetch schema for the first file
      try {
        const schema = await window.API.getSchema(uploadResults[0].file_id);
        setSchemaData(schema);
      } catch (err) {
        setSchemaData(null);
      }
    }
    setScreen("schema");
  };

  const handleSchemaConfirm = async () => {
    setScreen("dashboard");
    await refreshDashboard();
  };

  const newSession = () => {
    window.API.resetSession();
    setMessages([]);
    setSending(false);
    setPowerMode(false);
    setOverlayOpen(false);
    setDashData(null);
    setSessionFiles([]);
    setLastUpload(null);
    setSchemaData(null);
    setPendingFiles([]);
    setScreen("landing");
  };

  const themeToggle = () => setTweak("dark", !t.dark);
  const themeName = t.dark ? "dark" : "light";

  // Build ZDATA-compatible suggested questions from live data
  const suggestedQuestions = dashData
    ? dashData.suggested_questions || window.ZDATA.SUGGESTED
    : window.ZDATA.SUGGESTED;

  const suggested = messages.length === 0 ? suggestedQuestions : null;
  const chatProps = { messages, sending, onSend: handleSend, suggested };

  // ── Pre-dashboard screens ──
  if (screen === "login") {
    return (<><LoginPage onLogin={() => setScreen("welcome")} theme={themeName} onTheme={themeToggle} /><Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} /></>);
  }
  if (screen === "welcome") {
    return (<><WelcomePage onContinue={() => setScreen("landing")} theme={themeName} onTheme={themeToggle} /><Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} /></>);
  }
  if (screen === "landing") {
    return (<><Landing theme={themeName} onTheme={themeToggle} onUpload={handleFilesSelected} /><Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} /></>);
  }
  if (screen === "uploading") {
    return (
      <div className="z-shell">
        <MiniHeader theme={themeName} onTheme={themeToggle} />
        <UploadProgress
          files={pendingFiles}
          onDone={handleUploadComplete}
        />
        <Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} />
      </div>
    );
  }
  if (screen === "schema") {
    return (
      <div className="z-shell">
        <MiniHeader theme={themeName} onTheme={themeToggle} />
        <SchemaConfirm
          schemaData={schemaData}
          uploadInfo={lastUpload}
          onConfirm={handleSchemaConfirm}
          onAdd={() => setScreen("landing")}
        />
        <Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} />
      </div>
    );
  }

  // ── Dashboard ──
  const focusMode = powerMode && t.powerPresentation === "focus";

  // Live session files or fall back to static ZDATA
  const liveFiles = sessionFiles.length > 0 ? sessionFiles : window.ZDATA.FILES;
  const rail = <FilesRail collapsed={t.dashLayout === "compact"} onAdd={() => setScreen("landing")} files={liveFiles} />;

  const mainContent = (focusMode && focusView === "power")
    ? <PowerFocus powerTab={powerTab} setPowerTab={setPowerTab} onBack={() => setFocusView("overview")} />
    : <DashboardMain t={t} powerMode={powerMode} powerTab={powerTab} setPowerTab={setPowerTab}
        openPower={focusMode ? () => setFocusView("power") : null}
        dashData={dashData}
        dashLoading={dashLoading} />;

  const mainScroll = <div className="z-work-main">{mainContent}</div>;
  const place = t.chatPlacement;

  let work;
  if (place === "bottom") {
    work = (<div className="z-work">{rail}<div className="z-work-col">{mainScroll}<div className="z-work-dock"><ChatPanel {...chatProps} variant="bottom" /></div></div></div>);
  } else if (place === "overlay") {
    work = (<div className="z-work">{rail}{mainScroll}
      {overlayOpen
        ? <div className="z-overlay-chat"><ChatPanel {...chatProps} variant="overlay" onClose={() => setOverlayOpen(false)} /></div>
        : <button className="z-fab" onClick={() => setOverlayOpen(true)}><Icon name="message" size={18} /><span>Ask ZmaRk</span></button>}
    </div>);
  } else if (place === "left") {
    work = (<div className="z-work">{rail}<div className="z-work-chat"><ChatPanel {...chatProps} variant="panel" /></div>{mainScroll}</div>);
  } else {
    work = (<div className="z-work">{rail}{mainScroll}<div className="z-work-chat"><ChatPanel {...chatProps} variant="panel" /></div></div>);
  }

  return (
    <div className="z-shell">
      <TopBar theme={themeName} onTheme={themeToggle}
        powerMode={powerMode} onPower={setPowerMode} onNewSession={newSession}
        showRailToggle railOpen={t.dashLayout !== "compact"}
        onRail={() => setTweak("dashLayout", t.dashLayout === "compact" ? "standard" : "compact")} />
      {work}
      <Tweaks {...{ t, setTweak, powerMode, setPowerMode, setScreen }} />
    </div>
  );
}

// ── Mini header (uploading / schema screens) ─────────────────────────────
function MiniHeader({ theme, onTheme }) {
  return (
    <header className="z-miniheader">
      <Logo size={16} />
      <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
    </header>
  );
}

// ── Tweaks panel ──────────────────────────────────────────────────────────
function Tweaks({ t, setTweak, powerMode, setPowerMode, setScreen }) {
  return (
    <TweaksPanel title="Tweaks">
      <TweakSection label="Theme" />
      <TweakToggle label="Dark mode" value={t.dark} onChange={(v) => setTweak("dark", v)} />
      <TweakColor label="Accent" value={t.accent}
        options={["#4f46e5", "#2563eb", "#0d9488", "#7c3aed", "#475569"]}
        onChange={(v) => setTweak("accent", v)} />
      <TweakRadio label="Density" value={t.density} options={["compact", "comfortable"]}
        onChange={(v) => setTweak("density", v)} />

      <TweakSection label="Layout" />
      <TweakRadio label="Dashboard" value={t.dashLayout}
        options={[{ value: "standard", label: "Standard" }, { value: "compact", label: "Compact" }, { value: "report", label: "Report" }]}
        onChange={(v) => setTweak("dashLayout", v)} />
      <TweakSelect label="Chat placement" value={t.chatPlacement}
        options={[{ value: "right", label: "Docked right" }, { value: "left", label: "Docked left" }, { value: "bottom", label: "Bottom dock" }, { value: "overlay", label: "Floating overlay" }]}
        onChange={(v) => setTweak("chatPlacement", v)} />
      <TweakRadio label="Chart style" value={t.chartStyle}
        options={[{ value: "minimal", label: "Minimal" }, { value: "grid", label: "Gridded" }, { value: "area", label: "Area" }]}
        onChange={(v) => setTweak("chartStyle", v)} />
      <TweakSelect label="Power Mode" value={t.powerPresentation}
        options={[{ value: "inline", label: "Inline cards" }, { value: "tabbed", label: "Tabbed panel" }, { value: "focus", label: "Full takeover" }]}
        onChange={(v) => setTweak("powerPresentation", v)} />

      <TweakSection label="State" />
      <TweakToggle label="Power Mode on" value={powerMode} onChange={setPowerMode} />
      <TweakRow label="Jump to screen">
        <div className="z-jump">
          {[["login", "Login"], ["welcome", "Welcome"], ["landing", "Landing"], ["uploading", "Upload"], ["schema", "Schema"], ["dashboard", "Dashboard"]].map(([k, l]) => (
            <button key={k} className="z-jump-btn" onClick={() => setScreen(k)}>{l}</button>
          ))}
        </div>
      </TweakRow>
    </TweaksPanel>
  );
}

// ── Canned fallback responder (used when backend is down) ────────────────
function respondFallback(text) {
  const lc = text.toLowerCase();
  const C = window.ZDATA.CHAT;
  if (/(stop|invest|at[- ]?risk|\brisk\b|discontinu|liquidat|drop|reduce)/.test(lc)) return C[1];
  return {
    role: "assistant",
    content: "I'm having trouble reaching the backend. Please make sure the FastAPI server is running on port 8000.",
    followups: ["Retry", "What data have I uploaded?"],
  };
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
