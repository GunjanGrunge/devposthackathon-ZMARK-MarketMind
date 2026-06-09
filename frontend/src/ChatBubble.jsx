// frontend/src/ChatBubble.jsx
import React from "react";
import { ExternalLink } from "lucide-react";

function renderContentWithCitations(content) {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      return (
        <sup key={i} className="citation-ref">
          [{match[1]}]
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export function ChatBubble({ message, sessionId, onFollowup }) {
  const isAssistant = message.role === "assistant";
  const scratchpadHref = message.scratchpad_link?.startsWith("/scratchpad/")
    ? `/ui${message.scratchpad_link}`
    : message.scratchpad_link;

  return (
    <div className={`chat-bubble ${isAssistant ? "assistant" : "user"}`}>
      <div className="chat-bubble-content">
        <p className="chat-bubble-text">
          {renderContentWithCitations(message.content)}
        </p>

        {scratchpadHref && (
          <a
            href={scratchpadHref}
            target="_blank"
            rel="noopener noreferrer"
            className="scratchpad-link-card"
          >
            <ExternalLink size={14} />
            <span>Open in ZScratchpad</span>
          </a>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="citations-footer">
            <span className="citations-label">References</span>
            {message.citations.map((c, idx) => (
              <div key={idx} className="citation-item">
                <sup>[{idx + 1}]</sup>
                <span>
                  {c.source}
                  {c.ref ? `, ${c.ref}` : ""} — {c.excerpt}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {message.followups && message.followups.length > 0 && (
        <div className="followup-chips">
          {message.followups.map((f, i) => (
            <button
              key={i}
              className="followup-chip"
              onClick={() => onFollowup && onFollowup(f)}
            >
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
