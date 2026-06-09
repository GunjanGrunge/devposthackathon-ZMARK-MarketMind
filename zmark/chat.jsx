// chat.jsx — AI assistant panel. Renders in three placements: docked panel,
// bottom dock, or floating overlay. Messages/citations/followups + composer.

function Citations({ items }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="z-cites">
      <button className="z-cites-toggle" onClick={() => setOpen((o) => !o)}>
        <Icon name="book" size={13} />
        {items.length} source{items.length > 1 ? "s" : ""}
        <Icon name={open ? "chevronDown" : "chevronRight"} size={13} stroke={2} />
      </button>
      {open && (
        <div className="z-cites-list">
          {items.map((c, i) => (
            <div key={i} className="z-cite">
              <div className="z-cite-hd">
                <Icon name={c.source.endsWith(".pdf") ? "fileText" : "table"} size={13} />
                <span className="z-cite-src">{c.source}</span>
                <span className="z-cite-ref">{c.ref}</span>
              </div>
              <p className="z-cite-ex">{c.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Message({ m, onFollowup }) {
  if (m.role === "user") {
    return <div className="z-msg z-msg--user"><div className="z-bubble z-bubble--user">{m.content}</div></div>;
  }
  return (
    <div className="z-msg z-msg--ai">
      <div className="z-ai-avatar"><Icon name="sparkles" size={14} /></div>
      <div className="z-ai-body">
        <div className="z-bubble z-bubble--ai">{m.content}</div>
        {m.citations && <Citations items={m.citations} />}
        {m.followups && (
          <div className="z-followups">
            {m.followups.map((f, i) => (
              <button key={i} className="z-chip" onClick={() => onFollowup(f)}>
                {f}<Icon name="arrowUpRight" size={12} stroke={2} />
              </button>
            ))}
          </div>
        )}
      </div>
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

function ChatPanel({ messages, sending, onSend, suggested, variant = "panel", onClose }) {
  const [draft, setDraft] = React.useState("");
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  const submit = (text) => {
    const t = (text != null ? text : draft).trim();
    if (!t || sending) return;
    onSend(t);
    setDraft("");
  };

  return (
    <div className={`z-chat z-chat--${variant}`}>
      <header className="z-chat-hd">
        <div className="z-chat-hd-l">
          <span className="z-chat-ic"><Icon name="sparkles" size={15} /></span>
          <div>
            <div className="z-chat-ttl">Assistant</div>
            <div className="z-chat-sub">Grounded in your uploaded data</div>
          </div>
        </div>
        <div className="z-chat-hd-r">
          <Badge tone="accent" icon="database">Elastic hybrid</Badge>
          {variant === "overlay" && <Button variant="ghost" size="sm" icon="x" onClick={onClose} aria-label="Close" />}
        </div>
      </header>

      <div className="z-chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="z-chat-empty">
            <p className="z-chat-empty-t">Ask anything about your data</p>
            <p className="z-chat-empty-d">Every answer is retrieved from your files via Elastic hybrid search and cited.</p>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} m={m} onFollowup={submit} />)}
        {sending && <TypingDots />}
      </div>

      {suggested && suggested.length > 0 && (
        <div className="z-suggested">
          <div className="z-suggested-lbl">Suggested</div>
          <div className="z-suggested-list">
            {suggested.map((s, i) => (
              <button key={i} className="z-chip z-chip--suggest" onClick={() => submit(s)}>
                <Icon name="sparkles" size={12} />{s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="z-composer">
        <textarea
          className="z-composer-input" rows={1} value={draft}
          placeholder="Ask about your data…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        />
        <button className="z-composer-send" disabled={!draft.trim() || sending} onClick={() => submit()} aria-label="Send">
          <Icon name="send" size={16} />
        </button>
      </div>
      <div className="z-composer-hint">
        <Icon name="cpu" size={12} /> Gemini 2.5 Pro · retrieval via Elastic MCP
      </div>
    </div>
  );
}

Object.assign(window, { ChatPanel, Citations, Message });
