import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Database,
  FileSpreadsheet,
  FileText,
  Layers,
  Loader2,
  Moon,
  PanelLeft,
  Plus,
  RefreshCcw,
  Send,
  Sparkles,
  Sun,
  Table,
  Target,
  Upload,
  User,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import * as api from "./api";
import "./zmark.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ChatBubble } from "./ChatBubble";
import { ClarificationForm } from "./ClarificationForm";
import { ScratchpadPage } from "./ScratchpadPage";
import Plot from "react-plotly.js";

function SqlDatabaseIcon({ size = 16, className, style }) {
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

function GoogleAnalyticsIcon({ size = 16, className, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
      <rect x="3" y="13" width="4" height="8" rx="1.5" fill="#F9AB00" />
      <rect x="10" y="8" width="4" height="13" rx="1.5" fill="#E37400" />
      <rect x="17" y="3" width="4" height="18" rx="1.5" fill="#F4B400" />
    </svg>
  );
}

function BigQueryIcon({ size = 16, className, style }) {
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

function SalesforceIcon({ size = 16, className, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
      <path d="M19.4 10.4a3.7 3.7 0 0 0-3.7-3.7c-.3 0-.7 0-1 .1a5.1 5.1 0 0 0-9.2 1.8 3.4 3.4 0 0 0-3.3 3.4 3.4 3.4 0 0 0 3.4 3.4h13.7a2.9 2.9 0 0 0 2.9-2.9 2.9 2.9 0 0 0-2.8-2.1z" fill="#00A1E0" />
    </svg>
  );
}

function HubSpotIcon({ size = 16, className, style }) {
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

function SnowflakeIcon({ size = 16, className, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
      <path d="M12 2v20M2 12h20M19 5L5 19M19 19L5 5" stroke="#29B6F6" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M12 6l-2.5-2.5M12 6L14.5 3.5M12 18l-2.5 2.5M12 18l2.5-2.5M6 12L3.5 9.5M6 12l-2.5 2.5M18 12l2.5-2.5M18 12l2.5 2.5" stroke="#29B6F6" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

const ICONS = {
  activity: Activity,
  alert: AlertTriangle,
  arrowDownRight: ArrowDownRight,
  arrowUpRight: ArrowUpRight,
  barChart: BarChart3,
  book: BookOpen,
  check: Check,
  checkCircle: CheckCircle,
  chevronDown: ChevronDown,
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  cpu: Cpu,
  database: Database,
  fileText: FileText,
  layers: Layers,
  loader: Loader2,
  moon: Moon,
  panelLeft: PanelLeft,
  refresh: RefreshCcw,
  send: Send,
  sheet: FileSpreadsheet,
  sparkles: Sparkles,
  sun: Sun,
  table: Table,
  target: Target,
  upload: Upload,
  user: User,
  zap: Zap,
  add: Plus,
  trendUp: ArrowUpRight,
  trendDown: ArrowDownRight,
  scan: Activity,
  scale: Layers,
  sqlDatabase: SqlDatabaseIcon,
  googleAnalytics: GoogleAnalyticsIcon,
  bigQuery: BigQueryIcon,
  salesforce: SalesforceIcon,
  hubspot: HubSpotIcon,
  snowflake: SnowflakeIcon,
};

const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".xlsm", ".xlsb", ".xltx", ".xltm", ".ods", ".xl", ".pdf"];
const ACCEPTED_FILE_TYPES = ACCEPTED_EXTENSIONS.join(",");
const MAX_FILE_SIZE = 50 * 1024 * 1024;
const MAX_FILES = 10;

function Icon({ name, size = 16, stroke = 1.75, className, style }) {
  const Component = ICONS[name] || Activity;
  return <Component size={size} strokeWidth={stroke} className={className} style={style} aria-hidden="true" />;
}

function Spinner({ size = 16 }) {
  return <Icon name="loader" size={size} style={{ animation: "zspin 0.9s linear infinite" }} />;
}

function Button({ variant = "secondary", size = "md", icon, iconRight, active, children, className = "", ...rest }) {
  const cls = [
    "z-btn",
    `z-btn--${variant}`,
    size === "sm" && "z-btn--sm",
    !children && "z-btn--icon",
    active && "is-active",
    className,
  ].filter(Boolean).join(" ");
  const iconSize = size === "sm" ? 14 : 16;
  return (
    <button className={cls} {...rest}>
      {icon && <Icon name={icon} size={iconSize} />}
      {children}
      {iconRight && <Icon name={iconRight} size={iconSize} />}
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

function Card({ title, subtitle, actions, icon, children, className = "", pad = true }) {
  return (
    <section className={`z-card ${className}`}>
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

function Switch({ checked, onChange }) {
  return <button type="button" role="switch" aria-checked={checked} className="z-switch" data-on={checked ? "1" : "0"} onClick={() => onChange(!checked)}><i /></button>;
}

function Segmented({ value, options, onChange }) {
  return (
    <div className="z-seg" role="tablist">
      {options.map((option) => (
        <button key={option.value} role="tab" data-on={option.value === value ? "1" : "0"} onClick={() => onChange(option.value)}>
          {option.icon && <Icon name={option.icon} size={14} />}
          {option.label}
        </button>
      ))}
    </div>
  );
}

function Logo({ size = 17, showWord = true }) {
  const tile = Math.round(size * 1.5);
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

function FileTypeIcon({ type, size = 16 }) {
  const icon = type === "pdf" ? "fileText" : type === "xlsx" || type === "xls" ? "sheet" : "table";
  return <Icon name={icon} size={size} />;
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
  const pct = Math.round((value || 0) * 100);
  return (
    <span className="z-conf" title={`${pct}% confidence`}>
      <span className="z-conf-track"><span className="z-conf-fill" style={{ width: `${pct}%` }} /></span>
      <span className="z-conf-num">{pct}%</span>
    </span>
  );
}

function RiskPill({ level = "low", score = 0 }) {
  return <span className={`z-risk z-risk--${level}`}><span className="z-risk-dot" />{score}</span>;
}

function Select({ value, onChange, options, width }) {
  return (
    <div className="z-select" style={width ? { width } : null}>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => {
          const opt = typeof option === "object" ? option : { value: option, label: option };
          return <option key={opt.value} value={opt.value}>{opt.label}</option>;
        })}
      </select>
      <Icon name="chevronDown" size={14} stroke={2} />
    </div>
  );
}

function money(value) {
  return value == null ? "-" : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function compactMoney(value) {
  if (value == null) return "-";
  return `$${(Number(value) / 1000).toFixed(1)}k`;
}

function App() {
  const [theme, setTheme] = React.useState(() => localStorage.getItem("zmark.theme") || "dark");
  const [screen, setScreen] = React.useState("landing");
  const [powerMode, setPowerMode] = React.useState(false);
  const [powerTab, setPowerTab] = React.useState("obsolescence");
  const addFilesInputRef = React.useRef(null);
  const policyInputRef = React.useRef(null);
  const [pendingFiles, setPendingFiles] = React.useState([]);
  const [sessionFiles, setSessionFiles] = React.useState([]);
  const [lastUpload, setLastUpload] = React.useState(null);
  const [schemaData, setSchemaData] = React.useState(null);
  const [dashData, setDashData] = React.useState(null);
  const [dashLoading, setDashLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [messages, setMessages] = React.useState(() => {
    const sessionId = api.getSessionId();
    try {
      return JSON.parse(localStorage.getItem(`zmark.messages.${sessionId}`) || "[]");
    } catch {
      return [];
    }
  });
  const [sending, setSending] = React.useState(false);

  React.useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.setAttribute("data-density", "compact");
    root.style.setProperty("--accent", "#4f46e5");
    localStorage.setItem("zmark.theme", theme);
  }, [theme]);

  React.useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      setDashLoading(true);
      try {
        const files = await api.getSessionFiles();
        if (cancelled) return;
        const restoredFiles = files.files || [];
        setSessionFiles(restoredFiles);
        if (restoredFiles.length) {
          const dashboard = await api.getDashboard();
          if (cancelled) return;
          setDashData(dashboard);
          setScreen("dashboard");
        }
      } catch {
        if (!cancelled) setScreen("landing");
      } finally {
        if (!cancelled) setDashLoading(false);
      }
    }
    restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    localStorage.setItem(`zmark.messages.${api.getSessionId()}`, JSON.stringify(messages.slice(-30)));
  }, [messages]);

  async function refreshDashboard() {
    setDashLoading(true);
    setError("");
    try {
      const [dashboard, files] = await Promise.all([api.getDashboard(), api.getSessionFiles()]);
      setDashData(dashboard);
      setSessionFiles(files.files || []);
      if ((files.files || []).length) setScreen("dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setDashLoading(false);
    }
  }

  function validateFiles(files) {
    const list = Array.from(files || []);
    if (!list.length) return [];
    const existingNames = new Set(sessionFiles.map((file) => file.name.trim().toLowerCase()));
    const newNames = list
      .map((file) => file.name.trim().toLowerCase())
      .filter((name) => !existingNames.has(name));
    if (sessionFiles.length + new Set(newNames).size > MAX_FILES) throw new Error("Maximum 10 files per session reached");
    const invalid = list.find((file) => !ACCEPTED_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext)));
    if (invalid) throw new Error("Unsupported file type. Use CSV, Excel, or PDF");
    const large = list.find((file) => file.size > MAX_FILE_SIZE);
    if (large) throw new Error("File exceeds 50MB limit");
    return list;
  }

  async function handleFilesSelected(files) {
    try {
      const list = validateFiles(files);
      if (!list.length) return;
      setError("");
      setPendingFiles(list);
      setScreen("uploading");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUploadComplete(uploadResults) {
    if (uploadResults.length) {
      const structured = uploadResults.find((item) => item.file_type !== "pdf") || uploadResults[0];
      setLastUpload(structured);
      const schema = structured ? await api.getSchema(structured.file_id).catch(() => null) : null;
      setSchemaData(schema);
      if (schema?.columns?.length) {
        setScreen("schema");
        return;
      }
    }
    setScreen("dashboard");
    await refreshDashboard();
  }

  async function handleSchemaConfirm() {
    setScreen("dashboard");
    await refreshDashboard();
  }

  async function newSession() {
    const previousSessionId = api.getSessionId();
    await api.clearSession().catch(() => {});
    localStorage.removeItem(`zmark.messages.${previousSessionId}`);
    api.resetSessionId();
    setSessionFiles([]);
    setLastUpload(null);
    setSchemaData(null);
    setDashData(null);
    setPendingFiles([]);
    setMessages([]);
    setPowerMode(false);
    setScreen("landing");
  }

  async function handleSend(text) {
    const query = text.trim();
    if (!query || sending) return;
    const assistantId = crypto.randomUUID();
    const fallbackText = "I couldn't find relevant data in your uploaded files for this question.";
    setMessages((current) => [
      ...current,
      { role: "user", content: query },
      { id: assistantId, role: "assistant", content: "", streaming: true, citations: [], followups: [] },
    ]);
    setSending(true);
    try {
      const history = messages.slice(-6).map(({ role, content }) => ({ role, content }));
      let streamed = false;
      await api.streamChat(query, history, (event) => {
        if (event.event === "status") {
          setMessages((current) => current.map((message) => (
            message.id === assistantId && !message.content
              ? { ...message, content: event.message || "Thinking..." }
              : message
          )));
          return;
        }
        if (event.event === "metadata") {
          const meta = event.message || {};
          setMessages((current) => current.map((message) => (
            message.id === assistantId
              ? {
                ...message,
                content: "",
                citations: meta.citations || [],
                followups: meta.followups || [],
                scratchpad_link: meta.scratchpad_link || null,
                clarification_form: meta.clarification_form || null,
              }
              : message
          )));
          return;
        }
        if (event.event === "chunk") {
          streamed = true;
          setMessages((current) => current.map((message) => (
            message.id === assistantId
              ? { ...message, content: `${message.content || ""}${event.content || ""}` }
              : message
          )));
          return;
        }
        if (event.event === "done") {
          const finalMessage = event.message || {};
          setMessages((current) => current.map((message) => (
            message.id === assistantId
              ? {
                ...message,
                streaming: false,
                content: finalMessage.content || (streamed ? message.content : fallbackText),
                citations: finalMessage.citations || message.citations || [],
                followups: finalMessage.followups || message.followups || [],
                scratchpad_link: finalMessage.scratchpad_link || message.scratchpad_link || null,
                clarification_form: finalMessage.clarification_form || message.clarification_form || null,
              }
              : message
          )));
          return;
        }
        if (event.event === "error") {
          throw new Error(event.message || "Streaming chat failed");
        }
      });
    } catch (err) {
      try {
        const history = messages.slice(-6).map(({ role, content }) => ({ role, content }));
        const response = await api.sendChat(query, history);
        const message = response.message || {};
        setMessages((current) => current.map((item) => (
          item.id === assistantId
            ? {
              ...item,
              streaming: false,
              content: message.content || fallbackText,
              citations: message.citations || [],
              followups: message.followups || [],
              scratchpad_link: message.scratchpad_link || null,
              clarification_form: message.clarification_form || null,
            }
            : item
        )));
      } catch (fallbackErr) {
        setMessages((current) => current.map((message) => (
          message.id === assistantId
            ? {
              ...message,
              streaming: false,
              content: `Chat error: ${fallbackErr.message || err.message}`,
              citations: [],
              followups: ["Retry after checking the backend"],
            }
            : message
        )));
      }
    } finally {
      setSending(false);
    }
  }

  const themeToggle = () => setTheme((current) => current === "dark" ? "light" : "dark");

  if (screen === "landing") {
    return (
      <div className="z-shell">
        <Landing theme={theme} onTheme={themeToggle} onUpload={handleFilesSelected} />
        {error && <ErrorToast message={error} />}
      </div>
    );
  }

  if (screen === "uploading") {
    return (
      <div className="z-shell">
        <MiniHeader theme={theme} onTheme={themeToggle} />
        <UploadProgress files={pendingFiles} onDone={handleUploadComplete} onError={setError} />
        {error && <ErrorToast message={error} />}
      </div>
    );
  }

  if (screen === "schema") {
    return (
      <div className="z-shell">
        <MiniHeader theme={theme} onTheme={themeToggle} />
        <SchemaConfirm schemaData={schemaData} uploadInfo={lastUpload} onConfirm={handleSchemaConfirm} onAdd={() => setScreen("landing")} />
        {error && <ErrorToast message={error} />}
      </div>
    );
  }

  const chatProps = {
    messages,
    sending,
    onSend: handleSend,
    suggested: messages.length === 0 ? dashData?.suggested_questions || [] : null,
  };

  return (
    <div className="z-shell">
      <TopBar
        theme={theme}
        onTheme={themeToggle}
        powerMode={powerMode}
        onPower={setPowerMode}
        onNewSession={newSession}
      />
      <div className="z-work">
        <input ref={addFilesInputRef} type="file" accept={ACCEPTED_FILE_TYPES} multiple hidden onChange={(event) => handleFilesSelected(event.target.files)} />
        <input ref={policyInputRef} type="file" accept=".pdf" multiple hidden onChange={(event) => handleFilesSelected(event.target.files)} />
        <FilesRail
          files={sessionFiles}
          onAdd={() => addFilesInputRef.current?.click()}
          onAddPolicy={() => policyInputRef.current?.click()}
        />
        <div className="z-work-main">
          <DashboardMain
            dashData={dashData}
            dashLoading={dashLoading}
            powerMode={powerMode}
            powerTab={powerTab}
            setPowerTab={setPowerTab}
          />
        </div>
        <div className="z-work-chat">
          <ChatPanel {...chatProps} />
        </div>
      </div>
      {error && <ErrorToast message={error} />}
    </div>
  );
}

function ErrorToast({ message }) {
  return (
    <div className="z-toast z-toast--danger">
      <Icon name="alert" size={15} />
      <span>{message}</span>
    </div>
  );
}

function MiniHeader({ theme, onTheme }) {
  return (
    <header className="z-miniheader">
      <Logo size={16} />
      <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
    </header>
  );
}

function Landing({ theme, onTheme, onUpload }) {
  const [drag, setDrag] = React.useState(false);
  const inputRef = React.useRef(null);
  const policyInputRef = React.useRef(null);
  const handleFiles = (files) => onUpload(files);

  return (
    <div className="z-landing">
      <header className="z-landing-top">
        <Logo size={17} />
        <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
      </header>
      <div className="z-landing-body">
        <SourcesSidebar
          onUpload={() => inputRef.current?.click()}
          onPolicyUpload={() => policyInputRef.current?.click()}
        />
        <main className="z-landing-main">
          <div className="z-landing-eyebrow"><Icon name="sparkles" size={13} /> Business intelligence agent</div>
          <h1 className="z-landing-h1">Turn raw data into <span className="z-accent-text">decisions</span>.</h1>
          <p className="z-landing-sub">Upload your sales spreadsheets and compliance documents. ZmaRk analyzes, charts, and answers with LangGraph agents grounded in your session data.</p>
          <input ref={inputRef} type="file" accept={ACCEPTED_FILE_TYPES} multiple hidden onChange={(event) => handleFiles(event.target.files)} />
          <input ref={policyInputRef} type="file" accept=".pdf" multiple hidden onChange={(event) => handleFiles(event.target.files)} />
          <div
            className={`z-dropzone ${drag ? "is-drag" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(event) => { event.preventDefault(); setDrag(false); handleFiles(event.dataTransfer.files); }}
          >
            <span className="z-dropzone-ic"><Icon name="upload" size={26} /></span>
            <div className="z-dropzone-t">Drag &amp; drop your files here</div>
            <div className="z-dropzone-d">or <span className="z-link">browse to upload</span></div>
            <div className="z-dropzone-types">
              <span className="z-type"><Icon name="table" size={13} /> CSV</span>
              <span className="z-type"><Icon name="sheet" size={13} /> Excel</span>
              <span className="z-type"><Icon name="fileText" size={13} /> PDF</span>
            </div>
          </div>
          <div className="z-landing-meta">Up to 50 MB per file - 10 files per session - data stays session-scoped</div>
          <div className="z-landing-feats">
            <div className="z-feat"><span className="z-feat-ic"><Icon name="barChart" size={15} /></span><div><b>Auto EDA</b><span>Charts and anomaly detection on upload</span></div></div>
            <div className="z-feat"><span className="z-feat-ic"><Icon name="sparkles" size={15} /></span><div><b>Grounded chat</b><span>Cited answers from uploaded files</span></div></div>
            <div className="z-feat"><span className="z-feat-ic"><Icon name="zap" size={15} /></span><div><b>Power Mode</b><span>Risk radar from live analytics</span></div></div>
          </div>
        </main>
      </div>
      <footer className="z-landing-foot">React UI - FastAPI backend - LangGraph statistical agents</footer>
    </div>
  );
}

const CONNECTORS = [
  { name: "SQL Database", desc: "Postgres · MySQL · SQL Server", icon: "sqlDatabase" },
  { name: "Google Analytics", desc: "GA4 traffic & conversions", icon: "googleAnalytics" },
  { name: "BigQuery", desc: "Warehouse tables & views", icon: "bigQuery" },
  { name: "Salesforce", desc: "CRM objects & reports", icon: "salesforce" },
  { name: "HubSpot", desc: "Marketing & sales hub", icon: "hubspot" },
  { name: "Snowflake", desc: "Cloud data warehouse", icon: "snowflake" },
];

function SourcesSidebar({ onUpload, onPolicyUpload }) {
  return (
    <aside className="z-sources">
      <div className="z-sources-hd">
        <span className="z-sources-ic"><Icon name="database" size={15} /></span>
        <div>
          <div className="z-sources-ttl">Data sources</div>
          <div className="z-sources-sub">Bring data into your session</div>
        </div>
      </div>
      <div className="z-sources-group">
        <div className="z-sources-grouplbl">Available now</div>
        <button className="z-source z-source--active" onClick={onUpload}>
          <span className="z-source-ic"><Icon name="upload" size={16} /></span>
          <span className="z-source-info">
            <span className="z-source-name">Business data upload</span>
            <span className="z-source-desc">CSV - Excel</span>
          </span>
          <Icon name="chevronRight" size={15} stroke={2} />
        </button>
        <button className="z-source z-source--active" onClick={onPolicyUpload}>
          <span className="z-source-ic"><Icon name="fileText" size={16} /></span>
          <span className="z-source-info">
            <span className="z-source-name">Index policy PDF</span>
            <span className="z-source-desc">PDF to Elastic retrieval</span>
          </span>
          <Icon name="chevronRight" size={15} stroke={2} />
        </button>
      </div>
      <div className="z-sources-group">
        <div className="z-sources-grouplbl">Connectors <Badge tone="neutral">Coming soon</Badge></div>
        {CONNECTORS.map((c) => (
          <div key={c.name} className="z-source z-source--soon" aria-disabled="true">
            <span className="z-source-ic"><Icon name={c.icon} size={16} /></span>
            <span className="z-source-info">
              <span className="z-source-name">{c.name}</span>
              <span className="z-source-desc">{c.desc}</span>
            </span>
            <span className="z-source-soon">Soon</span>
          </div>
        ))}
      </div>
    </aside>
  );
}

function UploadProgress({ files, onDone, onError }) {
  const [pct, setPct] = React.useState(5);
  const [stepIdx, setStepIdx] = React.useState(0);
  const [localError, setLocalError] = React.useState("");
  const didRun = React.useRef(false);
  const steps = ["Uploading", "Parsing", "Indexing to Elastic"];

  React.useEffect(() => {
    if (didRun.current) return;
    didRun.current = true;
    (async () => {
      try {
        const results = [];
        for (let index = 0; index < files.length; index += 1) {
          setStepIdx(index === 0 ? 0 : 1);
          setPct(Math.round(8 + (index / files.length) * 70));
          results.push(await api.uploadFile(files[index]));
        }
        setStepIdx(2);
        setPct(88);
        await new Promise((resolve) => setTimeout(resolve, 350));
        setPct(100);
        setTimeout(() => onDone(results), 250);
      } catch (err) {
        setLocalError(err.message);
        onError(err.message);
      }
    })();
  }, [files, onDone, onError]);

  return (
    <div className="z-center-screen">
      <div className="z-flow-card">
        <div className="z-flow-hd">
          <span className="z-flow-ic"><Spinner size={18} /></span>
          <div><div className="z-flow-ttl">Processing your files</div><div className="z-flow-sub">Uploading, parsing, then indexing available content</div></div>
        </div>
        {localError && <div className="z-flow-error">{localError}</div>}
        <div className="z-flow-steps">
          {steps.map((step, index) => (
            <div key={step} className={`z-flow-step ${index < stepIdx ? "is-done" : index === stepIdx ? "is-active" : ""}`}>
              <span className="z-flow-step-dot">{index < stepIdx ? <Icon name="check" size={12} stroke={2.4} /> : index + 1}</span>{step}
            </div>
          ))}
        </div>
        <div className="z-flow-files">
          {files.map((file) => {
            const ext = file.name.split(".").pop()?.toLowerCase();
            const type = ext === "pdf" ? "pdf" : ext === "csv" ? "csv" : "xlsx";
            const size = file.size > 1048576 ? `${(file.size / 1048576).toFixed(1)} MB` : `${Math.round(file.size / 1024)} KB`;
            return (
              <div key={file.name} className="z-flow-file">
                <span className={`z-file-ic z-file-ic--${type}`}><FileTypeIcon type={type} size={14} /></span>
                <span className="z-flow-file-name">{file.name}</span>
                <span className="z-flow-file-size z-mono">{size}</span>
              </div>
            );
          })}
        </div>
        <div className="z-progress"><span className="z-progress-fill" style={{ width: `${pct}%` }} /></div>
        <div className="z-progress-pct z-mono">{pct}%</div>
      </div>
    </div>
  );
}

function SchemaConfirm({ schemaData, uploadInfo, onConfirm, onAdd }) {
  const columns = schemaData?.columns || [];
  const typeTone = { date: "accent", currency: "success", numeric: "neutral", string: "neutral" };
  return (
    <div className="z-center-screen z-center-screen--wide">
      <div className="z-flow-card z-flow-card--wide">
        <div className="z-flow-hd">
          <span className="z-flow-ic z-flow-ic--ok"><Icon name="checkCircle" size={18} /></span>
          <div>
            <div className="z-flow-ttl">Confirm detected schema</div>
            <div className="z-flow-sub">Detected column roles for <b>{uploadInfo?.filename}</b>{uploadInfo?.row_count ? ` - ${uploadInfo.row_count.toLocaleString()} rows` : ""}.</div>
          </div>
        </div>
        <table className="z-table z-table--schema">
          <thead><tr><th>Column</th><th>Detected type</th><th>Semantic role</th><th>Confidence</th></tr></thead>
          <tbody>
            {columns.map((column) => (
              <tr key={column.name}>
                <td className="z-mono z-td-strong">{column.name}</td>
                <td><Badge tone={typeTone[column.type] || "neutral"}>{column.type}</Badge></td>
                <td>{column.role}</td>
                <td><ConfidenceBar value={column.confidence} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="z-flow-foot">
          <span className="z-muted-xs">Schema correction can be added next; current analysis uses detected roles.</span>
          <div className="z-flow-foot-actions">
            <Button variant="secondary" icon="add" onClick={onAdd}>Add files</Button>
            <Button variant="primary" iconRight="chevronRight" onClick={onConfirm}>Run analysis</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TopBar({ theme, onTheme, powerMode, onPower, onNewSession }) {
  return (
    <header className="z-topbar">
      <div className="z-topbar-l">
        <Button variant="ghost" size="sm" icon="panelLeft" aria-label="Files" />
        <Logo size={16} />
        <span className="z-topbar-sep" />
        <span className="z-session-pill"><Icon name="database" size={13} /> Session <span className="z-mono">{api.getSessionId().slice(0, 8)}</span></span>
      </div>
      <div className="z-topbar-r">
        <span className="z-elastic-chip"><Icon name="database" size={13} /> LangGraph <b>active</b><span className="z-elastic-dot" /></span>
        <div className={`z-power-toggle ${powerMode ? "is-on" : ""}`}>
          <Icon name="zap" size={14} />
          <span>Power Mode</span>
          <Switch checked={powerMode} onChange={onPower} />
        </div>
        <Button variant="ghost" size="sm" icon={theme === "dark" ? "sun" : "moon"} onClick={onTheme} aria-label="Toggle theme" />
        <Button variant="secondary" size="sm" icon="refresh" onClick={onNewSession}>New session</Button>
        <span className="z-avatar"><Icon name="user" size={16} /></span>
      </div>
    </header>
  );
}

function FilesRail({ files, onAdd, onAddPolicy }) {
  const totalRows = files.reduce((sum, file) => sum + (file.rows || 0), 0);
  const totalPages = files.reduce((sum, file) => sum + (file.pages || 0), 0);
  return (
    <aside className="z-rail">
      <div className="z-rail-hd">
        <span className="z-rail-hd-ttl">Session files</span>
        <Badge tone="neutral">{files.length}</Badge>
      </div>
      <div className="z-rail-meta">{totalRows.toLocaleString()} rows - {totalPages} pages indexed</div>
      <div className="z-rail-files">
        {files.length === 0 && <div className="z-muted-xs">No files uploaded yet.</div>}
        {files.map((file) => (
          <div key={file.id} className="z-file">
            <span className={`z-file-ic z-file-ic--${file.type}`}><FileTypeIcon type={file.type} size={15} /></span>
            <div className="z-file-info">
              <div className="z-file-name">{file.name}</div>
              <div className="z-file-sub">{file.rows ? `${file.rows.toLocaleString()} rows` : `${file.pages || 0} pages`} - {file.size}</div>
            </div>
            <span className="z-file-status" title={file.status || "indexed"}><Icon name="checkCircle" size={14} /></span>
          </div>
        ))}
      </div>
      <button className="z-add-files" onClick={onAdd}>
        <Icon name="add" size={15} /> Add files to session
      </button>
      <button className="z-add-files" onClick={onAddPolicy}>
        <Icon name="fileText" size={15} /> Index policy PDF
      </button>
      <div className="z-index-card">
        <div className="z-index-hd"><Icon name="database" size={13} /> Retrieval index</div>
        <div className="z-index-name z-mono">marketmind-{api.getSessionId().slice(0, 8)}</div>
        <div className="z-index-row"><span>Chat route</span><b>LangGraph agents</b></div>
        <div className="z-index-row"><span>Search</span><b>Elastic when configured</b></div>
      </div>
    </aside>
  );
}

function formatValueList(values, limit = 3) {
  const cleaned = [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))].slice(0, limit);
  if (!cleaned.length) return "";
  if (cleaned.length === 1) return cleaned[0];
  if (cleaned.length === 2) return `${cleaned[0]} and ${cleaned[1]}`;
  return `${cleaned.slice(0, -1).join(", ")}, and ${cleaned[cleaned.length - 1]}`;
}

function dashboardBusinessFocus(dashData) {
  if (!dashData) return "";
  const products = (dashData.products || []).map((product) => product.name);
  const productCategories = (dashData.products || []).map((product) => product.category);
  const categories = (dashData.categories || []).map((category) => category.label);
  const channels = (dashData.channels || []).map((channel) => channel.label);

  const categoryText = formatValueList([...productCategories, ...categories], 3);
  const productText = formatValueList(products, 4);
  const channelText = formatValueList(channels, 2);

  let sentence = "";
  if (categoryText && productText) {
    sentence = `This dataset appears to focus on sales of ${categoryText}, including ${productText}.`;
  } else if (productText) {
    sentence = `This dataset appears to focus on sales of products such as ${productText}.`;
  } else if (categoryText) {
    sentence = `This dataset appears to focus on sales across ${categoryText}.`;
  }

  if (sentence && channelText) {
    sentence = `${sentence.slice(0, -1)} through ${channelText} channels.`;
  }
  return sentence;
}

function dashboardSummaryText(dashData) {
  const summary = (dashData?.summary || "").trim();
  if (!summary) return "Upload files and run analysis to generate a summary.";
  if (summary.toLowerCase().startsWith("this dataset appears to focus")) return summary;
  const focus = dashboardBusinessFocus(dashData);
  return focus ? `${focus} ${summary}` : summary;
}

function DashboardMain({ dashData, dashLoading, powerMode, powerTab, setPowerTab }) {
  const trend = dashData?.revenue_trend;
  const products = dashData?.products || [];
  const trendData = (trend?.labels || []).map((label, index) => ({ label, revenue: trend.values[index], anomaly: trend.anomaly_index === index }));
  const revenueTrendChart = dashData?.charts?.revenue_trend?.chart;
  const agentCharts = dashData?.agent_charts || [];
  const topProducts = [...products].sort((a, b) => b.revenue - a.revenue).slice(0, 8);
  const velocity = products.filter((product) => product.velocity != null).sort((a, b) => b.velocity - a.velocity).slice(0, 8);
  const channels = dashData?.channels || [];
  const categories = dashData?.categories || [];
  const kpi = dashData?.kpi;
  const anomalyIdx = trend?.anomaly_index;

  return (
    <div className="z-dashmain">
      {dashLoading && <div className="z-dash-loading"><Spinner size={16} /> <span>Loading analytics...</span></div>}
      <div className="z-kpis">
        <div className="z-kpi"><Stat label="Total revenue" value={compactMoney(kpi?.total_revenue)} delta={kpi?.revenue_delta_pct != null ? `${kpi.revenue_delta_pct > 0 ? "+" : ""}${kpi.revenue_delta_pct.toFixed(1)}%` : null} deltaTone={(kpi?.revenue_delta_pct || 0) >= 0 ? "up" : "down"} sub="current session" /></div>
        <div className="z-kpi"><Stat label="Top performer" value={kpi?.top_product || "-"} sub={kpi?.top_product_revenue ? compactMoney(kpi.top_product_revenue) : "waiting for data"} /></div>
        <div className="z-kpi"><Stat label="At-risk SKUs" value={String(kpi?.at_risk_skus ?? 0)} delta={(kpi?.at_risk_skus || 0) > 0 ? "action needed" : "clear"} deltaTone={(kpi?.at_risk_skus || 0) > 0 ? "down" : "up"} sub="obsolescence flags" /></div>
        <div className="z-kpi"><Stat label="Anomalies" value={String(kpi?.anomaly_count ?? 0)} sub={kpi?.anomaly_description || "none detected"} /></div>
      </div>

      <Card className="z-summary" icon="sparkles" title="Business summary" subtitle="Plain-English narrative generated from your uploaded data" actions={<Badge tone="accent" icon="cpu">Backend EDA</Badge>}>
        <p className="z-summary-text">{dashboardSummaryText(dashData)}</p>
      </Card>

      <Card title="Revenue trend" subtitle={`Monthly revenue - ${trendData.length || revenueTrendChart?.data?.[0]?.x?.length || 0} data points`} icon="trendUp" actions={anomalyIdx != null ? <Badge tone="danger" dot>1 anomaly</Badge> : null}>
        <ChartShell>{revenueTrendChart ? <DashboardPlotlyChart chart={revenueTrendChart} /> : trendData.length ? <TrendChart data={trendData} /> : <EmptyChart />}</ChartShell>
      </Card>

      {agentCharts.length ? (
        <div className="z-chart-grid">
          {agentCharts.map((card, index) => (
            <Card key={`${card.title || "chart"}-${index}`} title={card.title || "Analysis chart"} subtitle={card.subtitle || card.summary || "Generated from uploaded data"} icon={card.type === "pie" ? "database" : card.type === "line" ? "trendUp" : "barChart"}>
              <ChartShell>{card.chart ? <DashboardPlotlyChart chart={card.chart} /> : <EmptyChart />}</ChartShell>
            </Card>
          ))}
        </div>
      ) : (
        <div className="z-chart-grid">
          <Card title="Top products" subtitle="By revenue" icon="barChart"><ChartShell>{topProducts.length ? <BarSeries data={topProducts.map((p) => ({ name: p.name, value: p.revenue }))} /> : <EmptyChart />}</ChartShell></Card>
          <Card title="Sales velocity" subtitle="Units / period" icon="activity"><ChartShell>{velocity.length ? <BarSeries data={velocity.map((p) => ({ name: p.name, value: p.velocity }))} /> : <EmptyChart />}</ChartShell></Card>
          <Card title="Channel performance" subtitle="Revenue by channel" icon="layers"><ChartShell>{channels.length ? <BarSeries data={channels.map((c) => ({ name: c.label, value: c.value }))} /> : <EmptyChart />}</ChartShell></Card>
          <Card title="Category mix" subtitle="Revenue by category" icon="database"><ChartShell>{categories.length ? <BarSeries data={categories.map((c) => ({ name: c.label, value: c.value }))} /> : <EmptyChart />}</ChartShell></Card>
        </div>
      )}

      {powerMode && (
        <div className="z-power-wrap">
          <div className="z-power-head">
            <span className="z-power-head-ic"><Icon name="zap" size={15} /></span>
            <div className="z-power-head-txt">
              <div className="z-power-head-ttl">Power Mode</div>
              <div className="z-power-head-sub">Advanced risk analysis from live uploaded data</div>
            </div>
            <Badge tone="accent">Advanced</Badge>
          </div>
          <PowerSection products={products} tab={powerTab} onTab={setPowerTab} />
        </div>
      )}
    </div>
  );
}

function ChartShell({ children }) {
  return <div style={{ width: "100%", height: 230 }}>{children}</div>;
}

function cssVar(name, fallback) {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function chartThemeColors() {
  return {
    text: cssVar("--text", "#14181f"),
    text2: cssVar("--text-2", "#3f4856"),
    text3: cssVar("--text-3", "#687386"),
    border: cssVar("--border", "#e3e6eb"),
    surface: cssVar("--surface", "#ffffff"),
    accent: cssVar("--accent", "#4f46e5"),
  };
}

function EmptyChart() {
  return <div className="z-empty">No chart data returned for this session.</div>;
}

function TrendChart({ data }) {
  const colors = chartThemeColors();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: colors.text3 }} />
        <YAxis tick={{ fontSize: 11, fill: colors.text3 }} />
        <Tooltip />
        <Line type="monotone" dataKey="revenue" stroke={colors.accent} strokeWidth={2} dot={(props) => <Cell {...props} fill={props.payload?.anomaly ? cssVar("--danger", "#c62b3f") : colors.accent} />} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function themedPlotlyLayout(layout, colors) {
  const axisStyle = (axis = {}) => ({
    ...axis,
    color: colors.text2,
    gridcolor: axis.gridcolor || colors.border,
    zerolinecolor: axis.zerolinecolor || colors.border,
    tickfont: { ...(axis.tickfont || {}), color: colors.text3 },
    title: typeof axis.title === "string"
      ? { text: axis.title, font: { color: colors.text2 } }
      : { ...(axis.title || {}), font: { ...(axis.title?.font || {}), color: colors.text2 } },
  });
  const title = typeof layout.title === "string"
    ? { text: layout.title, font: { color: colors.text } }
    : { ...(layout.title || {}), font: { ...(layout.title?.font || {}), color: colors.text } };

  return {
    ...layout,
    template: null,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { ...(layout.font || {}), color: colors.text2, size: layout.font?.size || 11, family: layout.font?.family || "IBM Plex Sans, sans-serif" },
    title,
    xaxis: axisStyle(layout.xaxis),
    yaxis: axisStyle(layout.yaxis),
    legend: { ...(layout.legend || {}), font: { ...(layout.legend?.font || {}), color: colors.text2 } },
    hoverlabel: {
      ...(layout.hoverlabel || {}),
      bgcolor: colors.surface,
      bordercolor: colors.border,
      font: { ...(layout.hoverlabel?.font || {}), color: colors.text },
    },
    annotations: (layout.annotations || []).map((annotation) => ({
      ...annotation,
      font: { ...(annotation.font || {}), color: colors.text2 },
    })),
  };
}

function themedPlotlyData(data, colors) {
  return (data || []).map((trace) => ({
    ...trace,
    textfont: { ...(trace.textfont || {}), color: trace.textfont?.color || colors.text2 },
    insidetextfont: { ...(trace.insidetextfont || {}), color: trace.insidetextfont?.color || "#ffffff" },
    outsidetextfont: { ...(trace.outsidetextfont || {}), color: trace.outsidetextfont?.color || colors.text2 },
    hoverlabel: {
      ...(trace.hoverlabel || {}),
      font: { ...(trace.hoverlabel?.font || {}), color: colors.text },
    },
  }));
}

function DashboardPlotlyChart({ chart }) {
  const colors = chartThemeColors();
  const layout = themedPlotlyLayout(chart.layout || {}, colors);
  return (
    <Plot
      data={themedPlotlyData(chart.data, colors)}
      layout={{
        ...layout,
        autosize: true,
        margin: { l: 36, r: 12, t: 32, b: 36, ...(layout.margin || {}) },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height: "100%" }}
      useResizeHandler
    />
  );
}

function BarSeries({ data }) {
  const colors = chartThemeColors();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
        <XAxis dataKey="name" hide />
        <YAxis tick={{ fontSize: 11, fill: colors.text3 }} />
        <Tooltip formatter={(value) => money(value)} />
        <Bar dataKey="value" fill={colors.accent} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const POWER_TABS = [
  { value: "obsolescence", label: "Obsolescence radar", icon: "scan" },
  { value: "budget", label: "Budget recommender", icon: "scale" },
  { value: "montecarlo", label: "Monte Carlo", icon: "target" },
];

function PowerSection({ products, tab, onTab }) {
  return (
    <Card className="z-power-tabbed" pad={false}>
      <div className="z-power-tabs"><Segmented value={tab} options={POWER_TABS} onChange={onTab} /></div>
      <div className="z-power-tabbody">
        {tab === "obsolescence" && <Obsolescence products={products} />}
        {tab === "budget" && <BudgetRec products={products} />}
        {tab === "montecarlo" && <MonteCarlo products={products} />}
      </div>
    </Card>
  );
}

function Obsolescence({ products }) {
  const rows = [...products].sort((a, b) => (b.risk || 0) - (a.risk || 0)).slice(0, 12);
  const actionTone = { Liquidate: "danger", Discontinue: "danger", Discount: "warn", Maintain: "neutral", Monitor: "success" };
  return (
    <div className="z-radar">
      <table className="z-table">
        <thead><tr><th>Product</th><th>Category</th><th className="z-num">Growth</th><th>Risk score</th><th>Recommended action</th></tr></thead>
        <tbody>
          {rows.map((product, index) => (
            <tr key={`${product.name}-${product.channel || index}`}>
              <td><div className="z-td-strong">{product.name}</div><div className="z-td-sub">{product.channel || "all channels"}</div></td>
              <td className="z-td-muted">{product.category || "-"}</td>
              <td className="z-num"><span className={(product.growth || 0) < 0 ? "z-neg" : "z-pos"}>{product.growth > 0 ? "+" : ""}{product.growth ?? 0}%</span></td>
              <td><div className="z-riskcell"><RiskPill level={product.level || "low"} score={product.risk || 0} /><span className="z-riskbar"><span className={`z-riskbar-fill z-riskbar-fill--${product.level || "low"}`} style={{ width: `${product.risk || 0}%` }} /></span></div></td>
              <td><Badge tone={actionTone[product.action] || "neutral"} dot>{product.action || "Monitor"}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BudgetRec({ products }) {
  const sorted = [...products].sort((a, b) => (b.growth || 0) - (a.growth || 0));
  const cols = [
    { title: "Increase", icon: "trendUp", tone: "success", items: sorted.slice(0, 3), text: (p) => `Growth ${p.growth ?? 0}% with ${money(p.revenue)} revenue.` },
    { title: "Maintain", icon: "activity", tone: "neutral", items: sorted.slice(3, 6), text: (p) => `Stable candidate with risk score ${p.risk ?? 0}.` },
    { title: "Reduce", icon: "trendDown", tone: "danger", items: [...products].sort((a, b) => (b.risk || 0) - (a.risk || 0)).slice(0, 3), text: (p) => `Risk score ${p.risk ?? 0}; recommended action: ${p.action || "Monitor"}.` },
  ];
  return (
    <div className="z-budget">
      {cols.map((col) => (
        <div key={col.title} className="z-budget-col">
          <div className="z-budget-hd">
            <span className={`z-budget-ic z-budget-ic--${col.tone}`}><Icon name={col.icon} size={14} stroke={2} /></span>
            <span className="z-budget-ttl">{col.title}</span>
            <span className="z-budget-count">{col.items.length}</span>
          </div>
          <div className="z-budget-cards">
            {col.items.map((item) => (
              <div key={`${col.title}-${item.name}-${item.channel || ""}`} className="z-budget-card">
                <div className="z-budget-card-hd">
                  <span className="z-budget-prod">{item.name}</span>
                  <Badge tone={(item.risk || 0) > 60 ? "danger" : "accent"}>{(item.risk || 0) > 60 ? "risk" : "signal"}</Badge>
                </div>
                <p className="z-budget-rat">{col.text(item)}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function MonteCarlo({ products }) {
  const [product, setProduct] = React.useState(products[0]?.name || "");
  const [budget, setBudget] = React.useState(30);
  const [horizon, setHorizon] = React.useState("90");
  const [simulations, setSimulations] = React.useState("5000");
  const [result, setResult] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    if (!product && products[0]?.name) setProduct(products[0].name);
  }, [product, products]);
  const runSimulation = async () => {
    if (!product || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await api.runMonteCarlo({
        product,
        budgetChangePct: budget,
        horizonDays: Number(horizon),
        simulations: Number(simulations),
      });
      setResult(response);
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };
  const distributionData = (result?.distribution || []).map((point) => ({
    name: `P${point.percentile}`,
    value: point.revenue,
  }));
  return (
    <div className="z-mc">
      <div className="z-mc-controls">
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Product / channel</span>
          <Select value={product} onChange={setProduct} options={products.map((p) => p.name)} />
        </label>
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Budget change <b className="z-ctrl-val">{budget > 0 ? "+" : ""}{budget}%</b></span>
          <input type="range" className="z-range" min={-50} max={100} step={5} value={budget} onChange={(event) => setBudget(Number(event.target.value))} />
        </label>
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Time horizon</span>
          <Select value={horizon} onChange={setHorizon} options={[{ value: "30", label: "30 days" }, { value: "60", label: "60 days" }, { value: "90", label: "90 days" }, { value: "180", label: "180 days" }]} />
        </label>
        <label className="z-ctrl">
          <span className="z-ctrl-lbl">Runs</span>
          <Select value={simulations} onChange={setSimulations} options={[{ value: "1000", label: "1k" }, { value: "5000", label: "5k" }, { value: "10000", label: "10k" }]} />
        </label>
        <Button variant="primary" icon="target" disabled={!product || loading} onClick={runSimulation}>{loading ? "Running..." : "Run simulation"}</Button>
      </div>
      {error && <div className="z-mc-error">{error}</div>}
      {!result && !error && (
        <div className="z-mc-placeholder">
          <Icon name="target" size={22} />
          <p>Run the Monte Carlo agent against the products detected from your uploaded data.</p>
          <span className="z-muted-xs">Simulation uses session rows, inferred revenue/date/product columns, and observed volatility.</span>
        </div>
      )}
      {result && (
        <div className="z-mc-result">
          <div className="z-mc-stats">
            <Stat label="Expected revenue" value={money(result.expected_revenue)} sub={`${result.simulations.toLocaleString()} runs`} />
            <Stat label="Median" value={money(result.p50_revenue)} sub={`${result.horizon_days} day horizon`} />
            <Stat label="P10 / P90 range" value={`${compactMoney(result.p10_revenue)} - ${compactMoney(result.p90_revenue)}`} sub="80% simulation band" />
            <Stat label="Beat baseline" value={`${result.probability_above_baseline.toFixed(1)}%`} sub={`baseline ${compactMoney(result.baseline_revenue)}`} />
          </div>
          <div className="z-mc-chart">
            <div className="z-mini-axislabel">Revenue percentile distribution for {result.product}</div>
            <ChartShell><BarSeries data={distributionData} /></ChartShell>
          </div>
          <div className="z-interp">
            <span className="z-interp-ic"><Icon name="sparkles" size={14} /></span>
            <div>
              <div className="z-interp-lbl">Monte Carlo agent interpretation</div>
              <p>{result.summary}</p>
              <ul className="z-mc-assumptions">
                {result.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ChatPanel({ messages, sending, onSend, suggested }) {
  const [draft, setDraft] = React.useState("");
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);
  const submit = (text = draft) => {
    const value = text.trim();
    if (!value || sending) return;
    onSend(value);
    setDraft("");
  };

  return (
    <div className="z-chat z-chat--panel">
      <header className="z-chat-hd">
        <div className="z-chat-hd-l">
          <span className="z-chat-ic"><Icon name="sparkles" size={15} /></span>
          <div>
            <div className="z-chat-ttl">Assistant</div>
            <div className="z-chat-sub">LangGraph statistical agents</div>
          </div>
        </div>
        <div className="z-chat-hd-r"><Badge tone="accent" icon="database">Live backend</Badge></div>
      </header>
      <div className="z-chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="z-chat-empty">
            <p className="z-chat-empty-t">Ask anything about your data</p>
            <p className="z-chat-empty-d">Answers are generated from uploaded session files only.</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={index}>
            <ChatBubble
              message={message}
              sessionId={api.getSessionId()}
              onFollowup={(text) => submit(text)}
            />
            {message.clarification_form && (
              <ClarificationForm
                form={message.clarification_form}
                onSubmit={(encoded) => onSend(encoded)}
              />
            )}
          </div>
        ))}
        {sending && <TypingDots />}
      </div>
      {suggested && suggested.length > 0 && (
        <div className="z-suggested">
          <div className="z-suggested-lbl">Suggested</div>
          <div className="z-suggested-list">
            {suggested.map((question) => <button key={question} className="z-chip z-chip--suggest" onClick={() => submit(question)}><Icon name="sparkles" size={12} />{question}</button>)}
          </div>
        </div>
      )}
      <div className="z-composer">
        <textarea className="z-composer-input" rows={1} value={draft} placeholder="Ask about your data..." onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} />
        <button className="z-composer-send" disabled={!draft.trim() || sending} onClick={() => submit()} aria-label="Send"><Icon name="send" size={16} /></button>
      </div>
      <div className="z-composer-hint"><Icon name="cpu" size={12} /> FastAPI - LangGraph - Elastic when configured</div>
    </div>
  );
}

function Message({ m, onFollowup }) {
  if (m.role === "user") return <div className="z-msg z-msg--user"><div className="z-bubble z-bubble--user">{m.content}</div></div>;
  return (
    <div className="z-msg z-msg--ai">
      <div className="z-ai-avatar"><Icon name="sparkles" size={14} /></div>
      <div className="z-ai-body">
        <div className="z-bubble z-bubble--ai">{m.content}</div>
        {m.citations?.length > 0 && <Citations items={m.citations} />}
        {m.followups?.length > 0 && (
          <div className="z-followups">
            {m.followups.map((followup) => <button key={followup} className="z-chip" onClick={() => onFollowup(followup)}>{followup}<Icon name="arrowUpRight" size={12} stroke={2} /></button>)}
          </div>
        )}
      </div>
    </div>
  );
}

function Citations({ items }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="z-cites">
      <button className="z-cites-toggle" onClick={() => setOpen((value) => !value)}>
        <Icon name="book" size={13} />
        {items.length} source{items.length > 1 ? "s" : ""}
        <Icon name={open ? "chevronDown" : "chevronRight"} size={13} stroke={2} />
      </button>
      {open && (
        <div className="z-cites-list">
          {items.map((citation, index) => (
            <div key={index} className="z-cite">
              <div className="z-cite-hd">
                <Icon name={citation.source?.endsWith(".pdf") ? "fileText" : "table"} size={13} />
                <span className="z-cite-src">{citation.source}</span>
                <span className="z-cite-ref">{citation.ref}</span>
              </div>
              <p className="z-cite-ex">{citation.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TypingDots() {
  return (
    <div className="z-msg z-msg--ai">
      <div className="z-ai-avatar"><Icon name="sparkles" size={14} /></div>
      <div className="z-typing"><i /><i /><i /></div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <BrowserRouter basename="/ui">
    <Routes>
      <Route path="/scratchpad/:sessionId/:reportId" element={<ScratchpadPage />} />
      <Route path="*" element={<App />} />
    </Routes>
  </BrowserRouter>
);
