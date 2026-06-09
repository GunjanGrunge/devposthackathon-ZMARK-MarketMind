// frontend/src/ScratchpadPage.jsx
import React, { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, BarChart3, Loader2 } from "lucide-react";

export function ScratchpadPage() {
  const { sessionId, reportId } = useParams();
  const navigate = useNavigate();
  const [artifact, setArtifact] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const isDark = document.documentElement.getAttribute("data-theme") !== "light";

  useEffect(() => {
    if (!sessionId || !reportId) {
      setError("Invalid link.");
      setLoading(false);
      return;
    }
    fetch(`/api/v1/scratchpad/${sessionId}/${reportId}`)
      .then((r) => {
        if (!r.ok) throw new Error("Artifact not found or session expired.");
        return r.json();
      })
      .then((data) => {
        setArtifact(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [sessionId, reportId]);

  return (
    <div className="scratchpad-page">
      <div className="scratchpad-header">
        <button className="scratchpad-back" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} />
          Back to chat
        </button>
        <div className="scratchpad-title-row">
          <BarChart3 size={20} className="scratchpad-icon" />
          <h1 className="scratchpad-title">
            {artifact ? artifact.title : "ZScratchpad"}
          </h1>
          {artifact && (
            <span className="scratchpad-badge">{artifact.type}</span>
          )}
        </div>
      </div>

      <div className="scratchpad-body">
        {loading && (
          <div className="scratchpad-loading">
            <Loader2 size={24} className="spin" />
            <span>Loading artifact...</span>
          </div>
        )}

        {error && (
          <div className="scratchpad-error">
            <p>{error}</p>
            <button onClick={() => navigate(-1)}>Go back</button>
          </div>
        )}

        {artifact && !loading && (
          <>
            {artifact.chart && (
              <div className="scratchpad-chart-container">
                <Plot
                  data={artifact.chart.data || []}
                  layout={{
                    ...(artifact.chart.layout || {}),
                    paper_bgcolor: "transparent",
                    plot_bgcolor: "transparent",
                    font: { color: isDark ? "#eef1f6" : "#14181f", family: "IBM Plex Sans, sans-serif" },
                    margin: { t: 48, b: 48, l: 56, r: 24 },
                    autosize: true,
                  }}
                  config={{
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false,
                  }}
                  style={{ width: "100%", minHeight: 420 }}
                  useResizeHandler
                />
              </div>
            )}

            {artifact.summary && (
              <div className="scratchpad-summary">
                <h2 className="scratchpad-summary-label">Summary</h2>
                <p className="scratchpad-summary-text">{artifact.summary}</p>
              </div>
            )}

            {artifact.metadata && Object.keys(artifact.metadata).length > 0 && (
              <div className="scratchpad-meta">
                {Object.entries(artifact.metadata)
                  .filter(([k]) => k !== "query")
                  .map(([k, v]) => (
                    <span key={k} className="scratchpad-meta-chip">
                      {k.replace(/_/g, " ")}: <strong>{String(v)}</strong>
                    </span>
                  ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
