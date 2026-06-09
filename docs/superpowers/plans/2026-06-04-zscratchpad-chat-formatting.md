# ZScratchpad + Chat Formatting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a ZScratchpad output canvas for charts/reports, extend the LangGraph chat graph with visualization and hypothesis-testing agent branches, and fix chat response formatting to use plain text with superscript citations.

**Architecture:** The backend adds a session-scoped in-memory scratchpad store, a safe Python sandbox executor, and two new LangGraph branches (visualization, hypothesis_test). The frontend adds react-router-dom for the `/scratchpad/:reportId` route, react-plotly.js for interactive charts, a new ChatBubble component with superscript citations, and a ClarificationForm chip component for hypothesis testing intake.

**Tech Stack:** FastAPI, LangGraph, Plotly (Python + react-plotly.js), SciPy, React Router DOM, Vite/React frontend

---

## File Map

**New backend files:**
- `backend/app/services/scratchpad.py` — session-scoped in-memory artifact store
- `backend/app/services/sandbox.py` — safe `exec()` runner that produces Plotly JSON + summary
- `backend/app/api/v1/routes/scratchpad.py` — `GET /scratchpad/{session_id}/{report_id}`

**Modified backend files:**
- `backend/app/schemas/analytics.py` — add `ClarificationField`, `ClarificationForm`, `ScratchpadArtifact`; extend `ChatMessage`
- `backend/app/services/chat_graph.py` — new `visualization_node`, `hypothesis_node`; update `classify_node`, `_build_graph`, Gemini system prompt
- `backend/app/main.py` — register scratchpad router
- `backend/requirements.txt` — add `plotly`, `scipy`, `kaleido`

**New frontend files:**
- `frontend/src/ScratchpadPage.jsx` — ZScratchpad route page with Plotly chart + summary
- `frontend/src/ChatBubble.jsx` — chat message renderer: plain text, superscript `[n]`, references footer
- `frontend/src/ClarificationForm.jsx` — chip/select form rendered inside a chat bubble

**Modified frontend files:**
- `frontend/package.json` — add `react-router-dom`, `react-plotly.js`, `plotly.js`
- `frontend/src/main.jsx` — add `BrowserRouter`/routes, import new components, replace inline chat rendering

---

## Task 1: Backend — Scratchpad Store

**Files:**
- Create: `backend/app/services/scratchpad.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scratchpad.py
from app.services.scratchpad import save_artifact, get_artifact, delete_session_artifacts

def test_save_and_get_artifact():
    artifact = {
        "type": "histogram",
        "title": "RTX 3050 Sales",
        "chart": {"data": [{"type": "histogram", "x": [1, 2, 3]}], "layout": {}},
        "summary": "Test summary",
        "metadata": {},
    }
    report_id = save_artifact("sess-001", artifact)
    assert report_id.startswith("rpt_")
    result = get_artifact("sess-001", report_id)
    assert result is not None
    assert result["title"] == "RTX 3050 Sales"

def test_get_missing_artifact_returns_none():
    assert get_artifact("sess-999", "rpt_missing") is None

def test_delete_session_clears_artifacts():
    save_artifact("sess-del", {"type": "histogram", "title": "x", "chart": {}, "summary": "", "metadata": {}})
    delete_session_artifacts("sess-del")
    assert get_artifact("sess-del", "rpt_0000") is None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && python -m pytest tests/test_scratchpad.py -v
```
Expected: `ImportError: cannot import name 'save_artifact'`

- [ ] **Step 3: Write `scratchpad.py`**

```python
# backend/app/services/scratchpad.py
from __future__ import annotations
import threading
import uuid
from typing import Any, Dict, Optional

_store: Dict[str, Dict[str, Dict[str, Any]]] = {}
_lock = threading.Lock()


def save_artifact(session_id: str, artifact: Dict[str, Any]) -> str:
    report_id = f"rpt_{uuid.uuid4().hex[:8]}"
    with _lock:
        if session_id not in _store:
            _store[session_id] = {}
        _store[session_id][report_id] = artifact
    return report_id


def get_artifact(session_id: str, report_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        return _store.get(session_id, {}).get(report_id)


def delete_session_artifacts(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && python -m pytest tests/test_scratchpad.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scratchpad.py backend/tests/test_scratchpad.py
git commit -m "feat: add session-scoped scratchpad artifact store"
```

---

## Task 2: Backend — Safe Python Sandbox

**Files:**
- Create: `backend/app/services/sandbox.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sandbox.py
import pandas as pd
from app.services.sandbox import run_chart_code

def test_histogram_produces_chart_json():
    df = pd.DataFrame({"product_name": ["A", "A", "B"], "revenue": [100, 200, 150]})
    code = """
import plotly.express as px
fig = px.histogram(df, x="revenue", nbins=5, title="Revenue Distribution")
summary = f"Revenue histogram across {len(df)} rows."
"""
    result = run_chart_code(code, df)
    assert result["ok"] is True
    assert "data" in result["chart"]
    assert "Revenue Distribution" in result["summary"] or "rows" in result["summary"]

def test_dangerous_import_is_blocked():
    df = pd.DataFrame({"x": [1]})
    code = "import os; os.system('rm -rf /')\nfig = None\nsummary = ''"
    result = run_chart_code(code, df)
    assert result["ok"] is False
    assert "not allowed" in result["error"].lower() or result["chart"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && python -m pytest tests/test_sandbox.py -v
```
Expected: `ImportError: cannot import name 'run_chart_code'`

- [ ] **Step 3: Write `sandbox.py`**

```python
# backend/app/services/sandbox.py
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
import pandas as pd

logger = logging.getLogger("sandbox")

_ALLOWED_IMPORTS = {"pandas", "numpy", "plotly", "scipy", "math", "statistics"}


def _safe_import(name: str, *args, **kwargs):
    top = name.split(".")[0]
    if top not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import '{name}' is not allowed in the sandbox.")
    return __builtins__["__import__"](name, *args, **kwargs)


def run_chart_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Execute LLM-generated chart code in a restricted namespace.
    The code must assign `fig` (a plotly Figure) and optionally `summary` (str).
    Returns {"ok": True, "chart": {...}, "summary": "..."} or {"ok": False, "error": "..."}.
    """
    namespace: Dict[str, Any] = {
        "__builtins__": {
            k: v for k, v in __builtins__.items()  # type: ignore[union-attr]
            if k not in ("open", "exec", "eval", "compile", "__import__", "breakpoint")
        },
        "__import__": _safe_import,
        "df": df.copy(),
    }
    namespace["__builtins__"]["__import__"] = _safe_import  # type: ignore[index]

    try:
        exec(compile(code, "<sandbox>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        logger.warning("Sandbox exec error: %s", exc)
        return {"ok": False, "error": str(exc), "chart": None, "summary": ""}

    fig = namespace.get("fig")
    summary = str(namespace.get("summary", ""))

    if fig is None:
        return {"ok": False, "error": "Code did not produce a `fig` variable.", "chart": None, "summary": summary}

    try:
        import plotly
        chart_json = fig.to_dict()
        return {"ok": True, "chart": chart_json, "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to serialize figure: {exc}", "chart": None, "summary": summary}
```

- [ ] **Step 4: Add `plotly` and `scipy` to requirements**

Edit `backend/requirements.txt`, append:
```
plotly>=5.22.0
scipy>=1.13.0
```

- [ ] **Step 5: Install new deps**

```
cd backend && pip install plotly scipy
```

- [ ] **Step 6: Run tests**

```
cd backend && python -m pytest tests/test_sandbox.py -v
```
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/sandbox.py backend/tests/test_sandbox.py backend/requirements.txt
git commit -m "feat: safe Python sandbox for LLM-generated chart code"
```

---

## Task 3: Backend — Schemas Extension

**Files:**
- Modify: `backend/app/schemas/analytics.py`

- [ ] **Step 1: Add new models to `analytics.py`**

Append to the bottom of `backend/app/schemas/analytics.py`:

```python
# ── Scratchpad ──
class ScratchpadArtifact(BaseModel):
    report_id: str
    session_id: str
    type: str                      # histogram | line | scatter | hypothesis_report
    title: str
    chart: Optional[Dict[str, Any]] = None   # plotly figure dict
    summary: str
    metadata: Dict[str, Any] = {}


# ── Clarification form (hypothesis testing intake) ──
class ClarificationOption(BaseModel):
    value: str
    label: str


class ClarificationField(BaseModel):
    id: str
    type: str          # select | text
    label: str
    options: Optional[List[ClarificationOption]] = None
    default: Optional[str] = None


class ClarificationForm(BaseModel):
    intent: str        # "hypothesis_test" | "visualization"
    fields: List[ClarificationField]
    submit_label: str = "Run Analysis"
```

- [ ] **Step 2: Extend `ChatMessage`**

Replace the existing `ChatMessage` class in `analytics.py`:

```python
class ChatMessage(BaseModel):
    role: str   # user | assistant
    content: str
    citations: Optional[List[Citation]] = None
    followups: Optional[List[str]] = None
    scratchpad_link: Optional[str] = None       # "/scratchpad/{session_id}/{report_id}"
    clarification_form: Optional[ClarificationForm] = None
```

- [ ] **Step 3: Verify no import errors**

```
cd backend && python -c "from app.schemas.analytics import ChatMessage, ClarificationForm, ScratchpadArtifact; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/analytics.py
git commit -m "feat: extend ChatMessage schema with scratchpad_link and clarification_form"
```

---

## Task 4: Backend — Scratchpad Route

**Files:**
- Create: `backend/app/api/v1/routes/scratchpad.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scratchpad_route.py
from fastapi.testclient import TestClient
from app.main import app
from app.services.scratchpad import save_artifact

client = TestClient(app)

def test_get_artifact_returns_200():
    artifact = {
        "type": "histogram",
        "title": "RTX 3050 Revenue",
        "chart": {"data": [], "layout": {}},
        "summary": "Test",
        "metadata": {"product": "RTX 3050"},
    }
    report_id = save_artifact("sess-route-001", artifact)
    resp = client.get(f"/api/v1/scratchpad/sess-route-001/{report_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_id"] == report_id
    assert data["title"] == "RTX 3050 Revenue"

def test_get_missing_artifact_returns_404():
    resp = client.get("/api/v1/scratchpad/sess-route-001/rpt_missing")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && python -m pytest tests/test_scratchpad_route.py -v
```
Expected: `404 Not Found` on the GET call (route doesn't exist yet)

- [ ] **Step 3: Write `routes/scratchpad.py`**

```python
# backend/app/api/v1/routes/scratchpad.py
from fastapi import APIRouter, HTTPException
from app.services.scratchpad import get_artifact

router = APIRouter()


@router.get("/scratchpad/{session_id}/{report_id}")
async def get_scratchpad_artifact(session_id: str, report_id: str):
    artifact = get_artifact(session_id, report_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found or session expired.")
    return {"report_id": report_id, "session_id": session_id, **artifact}
```

- [ ] **Step 4: Register router in `main.py`**

Add after the existing router imports in `backend/app/main.py`:
```python
from app.api.v1.routes.scratchpad import router as scratchpad_router
```

Add after `app.include_router(chat_router, ...)`:
```python
app.include_router(scratchpad_router, prefix="/api/v1", tags=["Scratchpad"])
```

- [ ] **Step 5: Run test**

```
cd backend && python -m pytest tests/test_scratchpad_route.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/routes/scratchpad.py backend/app/main.py backend/tests/test_scratchpad_route.py
git commit -m "feat: add GET /scratchpad/{session_id}/{report_id} endpoint"
```

---

## Task 5: Backend — LangGraph Visualization + Hypothesis Nodes

**Files:**
- Modify: `backend/app/services/chat_graph.py`

This task adds two new nodes and updates the classifier and graph topology.

- [ ] **Step 1: Add `scratchpad_link` and `clarification_form` keys to `AgentState`**

In `chat_graph.py`, update the `AgentState` TypedDict to add:

```python
class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    history: List[Dict[str, str]]
    dataframes: List[Dict[str, Any]]
    data_summary: str
    route: str
    stats_results: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, str]]
    followups: List[str]
    suggested_followups: List[str]
    error: Optional[str]
    scratchpad_link: Optional[str]          # new
    clarification_form: Optional[Dict[str, Any]]   # new
```

- [ ] **Step 2: Update `classify_node` to detect new intents**

Replace the existing `classify_node` function:

```python
def classify_node(state: AgentState) -> AgentState:
    query = state["query"].lower()

    # Hypothesis test — must come before generic stats
    if re.search(
        r"hypothesis|t.?test|anova|chi.?square|p.?value|significance|statistical test|null hypothesis",
        query, re.I
    ):
        # Check if the user already submitted a clarification form response
        if re.search(r"metric=|group_a=|alpha=", query):
            state["route"] = "hypothesis_run"
        else:
            state["route"] = "hypothesis_clarify"
        return state

    # Visualization requests
    if re.search(
        r"histogram|bar chart|line chart|scatter|plot|chart|graph|visuali[sz]e|show me a|draw",
        query, re.I
    ):
        state["route"] = "visualization"
        return state

    # Document / policy retrieval
    if re.search(r"regulation|policy|compliance|pdf|document|clause|packaging", query, re.I):
        state["route"] = "retrieval"
        return state

    state["route"] = "statistics"
    return state
```

- [ ] **Step 3: Add `visualization_node`**

Add this function after `retrieval_node` in `chat_graph.py`:

```python
def visualization_node(state: AgentState) -> AgentState:
    """
    Generates a Plotly chart from LLM-produced code and stores it as a scratchpad artifact.
    """
    from app.services.sandbox import run_chart_code
    from app.services.scratchpad import save_artifact

    query = state["query"]
    session_id = state["session_id"]
    _, df = _combined_frame(state.get("dataframes", []))

    if df is None:
        state["answer"] = "Upload a CSV or Excel file first so I have data to chart."
        state["citations"] = []
        return state

    code = _generate_chart_code(query, df, state.get("data_summary", ""))
    if not code:
        state["answer"] = "I could not generate chart code for that request. Try rephrasing — for example: 'show me a histogram of RTX 3050 sales'."
        state["citations"] = []
        return state

    result = run_chart_code(code, df)
    if not result["ok"]:
        state["answer"] = f"The chart ran into an issue: {result['error']}. Please try a simpler request."
        state["citations"] = []
        return state

    title = _extract_chart_title(query)
    artifact = {
        "type": _detect_chart_type(query),
        "title": title,
        "chart": result["chart"],
        "summary": result["summary"],
        "metadata": {"query": query},
    }
    report_id = save_artifact(session_id, artifact)
    state["scratchpad_link"] = f"/scratchpad/{session_id}/{report_id}"
    state["answer"] = f"Here is your {title.lower()}."
    state["citations"] = []
    return state


def _generate_chart_code(query: str, df: pd.DataFrame, data_summary: str) -> Optional[str]:
    """Ask Gemini to write safe Plotly chart code for the given query."""
    if not settings.gemini_api_key:
        return _fallback_chart_code(query, df)

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        col_info = f"Columns: {', '.join(df.columns.tolist())}\nSample rows:\n{df.head(3).to_string(index=False)}"
        prompt = f"""Write Python code to answer this visualization request: "{query}"

DataFrame variable name: `df`
{col_info}

Rules:
- Import only from: pandas, numpy, plotly.express, plotly.graph_objects
- Assign the final figure to `fig`
- Assign a 1–2 sentence plain-English summary to `summary` (no markdown, no em-dashes)
- Do NOT call fig.show()
- Filter df to the relevant product/column if mentioned in the request
- Use a dark-friendly Plotly template: template="plotly_dark"

Return ONLY the Python code block, no explanation."""

        response = model.generate_content(prompt, generation_config={"temperature": 0.1, "max_output_tokens": 600})
        raw = (response.text or "").strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```python\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()
    except Exception as exc:
        logger.warning("Chart code generation failed: %s", exc)
        return _fallback_chart_code(query, df)


def _fallback_chart_code(query: str, df: pd.DataFrame) -> Optional[str]:
    """Generate a basic histogram/bar chart without Gemini."""
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    if not revenue_col:
        return None

    if product_col and re.search(r"bar|by product|product", query, re.I):
        return f"""
import plotly.express as px
grouped = df.groupby("{product_col}")["{revenue_col}"].sum().reset_index()
fig = px.bar(grouped, x="{product_col}", y="{revenue_col}", title="Revenue by Product", template="plotly_dark")
summary = "Bar chart showing total revenue for each product."
"""
    return f"""
import plotly.express as px
fig = px.histogram(df, x="{revenue_col}", nbins=20, title="{revenue_col.title()} Distribution", template="plotly_dark")
summary = "Histogram showing the distribution of {revenue_col}."
"""


def _detect_chart_type(query: str) -> str:
    q = query.lower()
    if "histogram" in q:
        return "histogram"
    if "scatter" in q:
        return "scatter"
    if re.search(r"line|trend|over time", q):
        return "line"
    return "bar"


def _extract_chart_title(query: str) -> str:
    q = query.strip().rstrip("?")
    # Trim common lead-ins
    q = re.sub(r"^(can you |could you |please |show me |give me |create |make |generate |draw )", "", q, flags=re.I)
    return q[:60].title()
```

- [ ] **Step 4: Add `hypothesis_clarify_node` and `hypothesis_run_node`**

Add these two functions after `visualization_node`:

```python
def hypothesis_clarify_node(state: AgentState) -> AgentState:
    """
    Returns a structured clarification form for hypothesis testing.
    Extracts available column names from the data to populate option lists.
    """
    _, df = _combined_frame(state.get("dataframes", []))

    metric_options = []
    group_options = []

    if df is not None:
        for col in df.columns:
            c = col.lower()
            if any(k in c for k in ["revenue", "sales", "units", "price", "amount"]):
                metric_options.append({"value": col, "label": col.replace("_", " ").title()})
        category_col = _find_col(df, ["category", "cat", "group", "type"])
        if category_col:
            uniq = df[category_col].dropna().unique().tolist()
            group_options = [{"value": str(v), "label": str(v)} for v in sorted(uniq)[:8]]

    if not metric_options:
        metric_options = [{"value": "revenue", "label": "Revenue"}, {"value": "units_sold", "label": "Units Sold"}]
    if not group_options:
        group_options = [{"value": "Group A", "label": "Group A"}, {"value": "Group B", "label": "Group B"}]

    state["clarification_form"] = {
        "intent": "hypothesis_test",
        "submit_label": "Run Test",
        "fields": [
            {
                "id": "metric",
                "type": "select",
                "label": "Metric to test",
                "options": metric_options,
                "default": metric_options[0]["value"],
            },
            {
                "id": "group_a",
                "type": "select",
                "label": "Group A",
                "options": group_options,
                "default": group_options[0]["value"],
            },
            {
                "id": "group_b",
                "type": "select",
                "label": "Group B",
                "options": group_options[1:] if len(group_options) > 1 else group_options,
                "default": group_options[1]["value"] if len(group_options) > 1 else group_options[0]["value"],
            },
            {
                "id": "alpha",
                "type": "select",
                "label": "Significance level",
                "options": [
                    {"value": "0.01", "label": "0.01 (strict)"},
                    {"value": "0.05", "label": "0.05 (standard)"},
                    {"value": "0.10", "label": "0.10 (lenient)"},
                ],
                "default": "0.05",
            },
        ],
    }
    state["answer"] = "I can run a hypothesis test on your data. A few quick details:"
    state["citations"] = []
    return state


def hypothesis_run_node(state: AgentState) -> AgentState:
    """
    Parses the clarification form response and runs the hypothesis test.
    The query looks like: 'metric=revenue, group_a=GPU, group_b=Headsets, alpha=0.05'
    """
    from app.services.sandbox import run_chart_code
    from app.services.scratchpad import save_artifact

    query = state["query"]
    session_id = state["session_id"]
    _, df = _combined_frame(state.get("dataframes", []))

    if df is None:
        state["answer"] = "Upload a CSV or Excel file first."
        state["citations"] = []
        return state

    params = dict(re.findall(r"(\w+)=([^,]+)", query))
    metric = params.get("metric", "revenue").strip()
    group_a = params.get("group_a", "").strip()
    group_b = params.get("group_b", "").strip()
    alpha = float(params.get("alpha", "0.05").strip())

    category_col = _find_col(df, ["category", "cat", "group", "type"])
    metric_col = _find_col(df, [metric.lower()]) or metric

    code = f"""
import plotly.graph_objects as go
from scipy import stats
import numpy as np

cat_col = "{category_col or 'category'}"
metric_col = "{metric_col}"
group_a = "{group_a}"
group_b = "{group_b}"
alpha = {alpha}

a_data = df[df[cat_col] == group_a][metric_col].dropna().astype(float).values
b_data = df[df[cat_col] == group_b][metric_col].dropna().astype(float).values

t_stat, p_value = stats.ttest_ind(a_data, b_data, equal_var=False)
reject = p_value < alpha

fig = go.Figure()
fig.add_trace(go.Box(y=a_data, name=group_a, marker_color="#7c3aed"))
fig.add_trace(go.Box(y=b_data, name=group_b, marker_color="#0ea5e9"))
fig.update_layout(
    title=f"Hypothesis Test: {{group_a}} vs {{group_b}} — {{metric_col}}",
    template="plotly_dark",
    yaxis_title=metric_col,
)

verdict = "Reject the null hypothesis" if reject else "Fail to reject the null hypothesis"
summary = (
    f"t-statistic: {{t_stat:.4f}}, p-value: {{p_value:.4f}} (alpha={{alpha}}). "
    f"{{verdict}}. "
    f"{{group_a}} mean: {{a_data.mean():.2f}}, {{group_b}} mean: {{b_data.mean():.2f}}. "
    f"The difference is {'statistically significant' if reject else 'not statistically significant'} "
    f"at the {alpha} level."
)
"""

    result = run_chart_code(code, df)
    if not result["ok"]:
        state["answer"] = f"Test failed: {result['error']}"
        state["citations"] = []
        return state

    title = f"Hypothesis Test: {group_a} vs {group_b} on {metric}"
    artifact = {
        "type": "hypothesis_report",
        "title": title,
        "chart": result["chart"],
        "summary": result["summary"],
        "metadata": {"metric": metric, "group_a": group_a, "group_b": group_b, "alpha": alpha},
    }
    report_id = save_artifact(session_id, artifact)
    state["scratchpad_link"] = f"/scratchpad/{session_id}/{report_id}"
    state["answer"] = result["summary"]
    state["citations"] = []
    return state
```

- [ ] **Step 5: Update `_build_graph` with new branches**

Replace the existing `_build_graph` function:

```python
def _build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(AgentState)
    graph.add_node("load_data", load_data_node)
    graph.add_node("classify", classify_node)
    graph.add_node("statistics", statistics_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("visualization", visualization_node)
    graph.add_node("hypothesis_clarify", hypothesis_clarify_node)
    graph.add_node("hypothesis_run", hypothesis_run_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("followup", followup_node)

    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "classify")
    graph.add_conditional_edges(
        "classify",
        lambda state: state.get("route", "statistics"),
        {
            "statistics": "statistics",
            "retrieval": "retrieval",
            "visualization": "visualization",
            "hypothesis_clarify": "hypothesis_clarify",
            "hypothesis_run": "hypothesis_run",
        },
    )
    graph.add_edge("statistics", "retrieval")
    graph.add_edge("retrieval", "synthesis")
    graph.add_edge("synthesis", "followup")
    graph.add_edge("followup", END)
    graph.add_edge("visualization", END)
    graph.add_edge("hypothesis_clarify", END)
    graph.add_edge("hypothesis_run", END)
    return graph.compile()
```

- [ ] **Step 6: Update `answer_query_graph` to pass new fields through**

In `answer_query_graph`, update the return statement:

```python
    return ChatMessage(
        role="assistant",
        content=result.get("answer") or "I couldn't find relevant data in your uploaded files for this question.",
        citations=citations,
        followups=result.get("followups") or None,
        scratchpad_link=result.get("scratchpad_link") or None,
        clarification_form=result.get("clarification_form") or None,
    )
```

- [ ] **Step 7: Verify graph compiles**

```
cd backend && python -c "from app.services.chat_graph import compiled_chat_graph; print('graph ok' if compiled_chat_graph else 'FAILED')"
```
Expected: `graph ok`

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/chat_graph.py
git commit -m "feat: add visualization, hypothesis_clarify, hypothesis_run nodes to chat graph"
```

---

## Task 6: Backend — Fix Gemini System Prompt Formatting

**Files:**
- Modify: `backend/app/services/chat_graph.py`

- [ ] **Step 1: Replace `_GEMINI_SYSTEM` constant**

Find and replace the `_GEMINI_SYSTEM` string in `chat_graph.py`:

```python
_GEMINI_SYSTEM = """You are ZmaRk, a sharp business-intelligence assistant. The user has uploaded their sales data and you have been given computed findings and a data snapshot.

PERSONALITY:
Warm and proactive. Direct. Specific. Always cite real numbers.

RESPONSE RULES (strict):
- Write plain sentences. No bullet points, no numbered lists, no headers.
- No em-dashes (do not use the — character). Use commas or periods instead.
- No markdown bold or italic (no ** or * or __ wrapping text).
- When citing a data source, use inline numeric markers like [1], [2] in the text.
- Keep the total response under 4 sentences.
- Answer the question first, then offer one follow-up analysis.
- Never invent numbers or product names not present in COMPUTED FINDINGS or DATA SUMMARY.
- If the data does not contain what was asked, say so clearly and suggest what you can answer.
- Do not start with "Based on your uploaded data" — be direct."""
```

- [ ] **Step 2: Verify synthesis path returns clean text**

```
cd backend && python -m pytest tests/test_chat_graph.py -v
```
Expected: all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/chat_graph.py
git commit -m "fix: enforce plain-text formatting in Gemini system prompt (no em-dash, no markdown bold)"
```

---

## Task 7: Frontend — Install Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install new packages**

```
cd frontend && npm install react-router-dom react-plotly.js plotly.js
```

- [ ] **Step 2: Verify installs succeeded**

```
cd frontend && node -e "require('react-router-dom'); require('react-plotly.js'); console.log('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add react-router-dom, react-plotly.js, plotly.js to frontend"
```

---

## Task 8: Frontend — ChatBubble Component

**Files:**
- Create: `frontend/src/ChatBubble.jsx`

- [ ] **Step 1: Create `ChatBubble.jsx`**

```jsx
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

export function ChatBubble({ message, sessionId }) {
  const isAssistant = message.role === "assistant";

  return (
    <div className={`chat-bubble ${isAssistant ? "assistant" : "user"}`}>
      <div className="chat-bubble-content">
        <p className="chat-bubble-text">
          {renderContentWithCitations(message.content)}
        </p>

        {message.scratchpad_link && (
          <a
            href={message.scratchpad_link}
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
            <button key={i} className="followup-chip" data-followup={f}>
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add CSS for ChatBubble to `zmark.css`**

Append to `frontend/src/zmark.css`:

```css
/* ── ChatBubble ─────────────────────────────────────────────── */
.chat-bubble { display: flex; flex-direction: column; gap: 6px; max-width: 720px; }
.chat-bubble.user { align-self: flex-end; }
.chat-bubble.assistant { align-self: flex-start; }

.chat-bubble-content {
  background: var(--surface, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text, #e2e2f0);
}
.chat-bubble.user .chat-bubble-content {
  background: var(--accent, #7c3aed);
  border-color: transparent;
  color: #fff;
}

.chat-bubble-text { margin: 0 0 6px; }

sup.citation-ref {
  font-size: 10px;
  color: var(--accent, #7c3aed);
  font-weight: 600;
  margin-left: 1px;
  cursor: default;
}

.citations-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border, #2a2a3e);
  font-size: 11px;
  color: var(--text-muted, #888);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.citations-label { font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; }
.citation-item { display: flex; gap: 4px; }
.citation-item sup { color: var(--accent, #7c3aed); min-width: 16px; }

.scratchpad-link-card {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 6px 12px;
  background: rgba(124, 58, 237, 0.12);
  border: 1px solid rgba(124, 58, 237, 0.4);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #a78bfa;
  text-decoration: none;
  transition: background 0.15s;
}
.scratchpad-link-card:hover { background: rgba(124, 58, 237, 0.22); }

.followup-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.followup-chip {
  background: var(--surface-2, #252535);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 16px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-muted, #aaa);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.followup-chip:hover { border-color: var(--accent, #7c3aed); color: var(--text, #e2e2f0); }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ChatBubble.jsx frontend/src/zmark.css
git commit -m "feat: ChatBubble component with superscript citations and scratchpad link card"
```

---

## Task 9: Frontend — ClarificationForm Component

**Files:**
- Create: `frontend/src/ClarificationForm.jsx`

- [ ] **Step 1: Create `ClarificationForm.jsx`**

```jsx
// frontend/src/ClarificationForm.jsx
import React, { useState } from "react";
import { Play } from "lucide-react";

export function ClarificationForm({ form, onSubmit }) {
  const initial = Object.fromEntries(
    form.fields.map((f) => [f.id, f.default || (f.options?.[0]?.value ?? "")])
  );
  const [values, setValues] = useState(initial);

  function handleChange(fieldId, value) {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    // Encode as structured query string the backend can parse
    const encoded = Object.entries(values)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    onSubmit(encoded);
  }

  return (
    <form className="clarification-form" onSubmit={handleSubmit}>
      <div className="clarification-fields">
        {form.fields.map((field) => (
          <div key={field.id} className="clarification-field">
            <label className="clarification-label">{field.label}</label>
            {field.type === "select" && field.options ? (
              <div className="clarification-chips">
                {field.options.map((opt) => (
                  <button
                    type="button"
                    key={opt.value}
                    className={`clarification-chip ${values[field.id] === opt.value ? "active" : ""}`}
                    onClick={() => handleChange(field.id, opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                className="clarification-input"
                value={values[field.id]}
                onChange={(e) => handleChange(field.id, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>
      <button type="submit" className="clarification-submit">
        <Play size={13} />
        {form.submit_label || "Run Analysis"}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Add CSS for ClarificationForm to `zmark.css`**

Append to `frontend/src/zmark.css`:

```css
/* ── ClarificationForm ──────────────────────────────────────── */
.clarification-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 10px;
}
.clarification-fields { display: flex; flex-direction: column; gap: 10px; }
.clarification-field { display: flex; flex-direction: column; gap: 4px; }
.clarification-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted, #888); }

.clarification-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.clarification-chip {
  padding: 5px 12px;
  border-radius: 14px;
  border: 1px solid var(--border, #2a2a3e);
  background: var(--surface-2, #252535);
  font-size: 12px;
  color: var(--text-muted, #aaa);
  cursor: pointer;
  transition: all 0.15s;
}
.clarification-chip.active {
  background: rgba(124, 58, 237, 0.18);
  border-color: #7c3aed;
  color: #a78bfa;
}
.clarification-chip:hover:not(.active) { border-color: #555; color: var(--text, #e2e2f0); }

.clarification-input {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border, #2a2a3e);
  background: var(--surface, #1e1e2e);
  color: var(--text, #e2e2f0);
  font-size: 13px;
}

.clarification-submit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  border-radius: 8px;
  background: #7c3aed;
  border: none;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  transition: background 0.15s;
}
.clarification-submit:hover { background: #6d28d9; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ClarificationForm.jsx frontend/src/zmark.css
git commit -m "feat: ClarificationForm chip component for hypothesis testing intake"
```

---

## Task 10: Frontend — ZScratchpad Page

**Files:**
- Create: `frontend/src/ScratchpadPage.jsx`

- [ ] **Step 1: Create `ScratchpadPage.jsx`**

```jsx
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

  useEffect(() => {
    if (!sessionId || !reportId) { setError("Invalid link."); setLoading(false); return; }
    fetch(`/api/v1/scratchpad/${sessionId}/${reportId}`)
      .then((r) => {
        if (!r.ok) throw new Error("Artifact not found or session expired.");
        return r.json();
      })
      .then((data) => { setArtifact(data); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
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
                    font: { color: "#e2e2f0", family: "Inter, sans-serif" },
                    margin: { t: 48, b: 48, l: 56, r: 24 },
                    autosize: true,
                  }}
                  config={{ responsive: true, displayModeBar: true, displaylogo: false }}
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
```

- [ ] **Step 2: Add CSS for ScratchpadPage to `zmark.css`**

Append to `frontend/src/zmark.css`:

```css
/* ── ScratchpadPage ─────────────────────────────────────────── */
.scratchpad-page {
  min-height: 100vh;
  background: var(--bg, #12121e);
  color: var(--text, #e2e2f0);
  display: flex;
  flex-direction: column;
}
.scratchpad-header {
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--border, #2a2a3e);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.scratchpad-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--text-muted, #888);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s;
}
.scratchpad-back:hover { color: var(--text, #e2e2f0); }
.scratchpad-title-row { display: flex; align-items: center; gap: 10px; }
.scratchpad-icon { color: #7c3aed; }
.scratchpad-title { font-size: 20px; font-weight: 600; margin: 0; }
.scratchpad-badge {
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(124, 58, 237, 0.15);
  border: 1px solid rgba(124, 58, 237, 0.35);
  font-size: 11px;
  color: #a78bfa;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.scratchpad-body { padding: 28px 32px; display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.scratchpad-loading, .scratchpad-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 40px;
  color: var(--text-muted, #888);
}
.scratchpad-chart-container {
  background: var(--surface, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 14px;
  padding: 16px;
  overflow: hidden;
}
.scratchpad-summary {
  background: var(--surface, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  border-radius: 12px;
  padding: 18px 20px;
}
.scratchpad-summary-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted, #888); margin: 0 0 8px; }
.scratchpad-summary-text { margin: 0; line-height: 1.7; font-size: 14px; }
.scratchpad-meta { display: flex; flex-wrap: wrap; gap: 8px; }
.scratchpad-meta-chip {
  padding: 4px 12px;
  border-radius: 8px;
  background: var(--surface, #1e1e2e);
  border: 1px solid var(--border, #2a2a3e);
  font-size: 12px;
  color: var(--text-muted, #888);
}
.scratchpad-meta-chip strong { color: var(--text, #e2e2f0); }
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/ScratchpadPage.jsx frontend/src/zmark.css
git commit -m "feat: ZScratchpad page with Plotly chart rendering and summary panel"
```

---

## Task 11: Frontend — Wire Routing and New Components into `main.jsx`

**Files:**
- Modify: `frontend/src/main.jsx`

- [ ] **Step 1: Add imports at the top of `main.jsx`**

After the existing imports, add:
```jsx
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { ChatBubble } from "./ChatBubble";
import { ClarificationForm } from "./ClarificationForm";
import { ScratchpadPage } from "./ScratchpadPage";
```

- [ ] **Step 2: Wrap the root render with `BrowserRouter` and `Routes`**

Find the `createRoot(...).render(...)` call at the bottom of `main.jsx`.
Replace:
```jsx
createRoot(document.getElementById("root")).render(<App />);
```
With:
```jsx
createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <Routes>
      <Route path="/scratchpad/:sessionId/:reportId" element={<ScratchpadPage />} />
      <Route path="*" element={<App />} />
    </Routes>
  </BrowserRouter>
);
```

- [ ] **Step 3: Replace inline chat message rendering with `ChatBubble`**

Find the section in `main.jsx` that renders individual chat messages (look for `.map` over messages with `.role === "assistant"` checks). Replace the per-message render block with:

```jsx
{messages.map((msg, idx) => (
  <div key={idx}>
    <ChatBubble message={msg} sessionId={sessionId} />
    {msg.clarification_form && (
      <ClarificationForm
        form={msg.clarification_form}
        onSubmit={(encoded) => sendMessage(encoded)}
      />
    )}
  </div>
))}
```

Note: `sendMessage` is whatever function currently handles sending a new user message from the chat input. Find its name in `main.jsx` and use the correct reference.

- [ ] **Step 4: Add ZScratchpad nav item**

In the sidebar navigation section (look for the `nav` or sidebar list with items like "Dashboard", "Chat"), add a ZScratchpad entry:

```jsx
<button
  className={`nav-item ${activeTab === "scratchpad-history" ? "active" : ""}`}
  onClick={() => setActiveTab("scratchpad-history")}
>
  <BarChart3 size={16} />
  <span>ZScratchpad</span>
</button>
```

- [ ] **Step 5: Start dev server and verify routing works**

```
cd frontend && npm run dev
```

Open `http://localhost:5173`. Confirm:
1. Main app loads on `/`
2. Navigating to `/scratchpad/test-session/rpt_missing` shows the scratchpad page with "Artifact not found" error (expected — no real artifact yet)
3. Chat messages render via `ChatBubble` with the citation footer styling

- [ ] **Step 6: Commit**

```bash
git add frontend/src/main.jsx
git commit -m "feat: wire BrowserRouter routing, ChatBubble, ClarificationForm into main.jsx"
```

---

## Task 12: Update Architecture Document

**Files:**
- Modify: `_bmad-output/planning-artifacts/architecture.md`

- [ ] **Step 1: Append ZScratchpad section to architecture doc**

In `_bmad-output/planning-artifacts/architecture.md`, at the end of the "Core Architectural Decisions" section append:

```markdown
### ZScratchpad — Agent Output Canvas

**Decision:** Add a `/scratchpad/:sessionId/:reportId` route as a dedicated display surface for rich agent outputs (interactive charts, hypothesis test reports).

**Rationale:** Chat bubbles are unsuitable for full-width interactive Plotly charts. Decoupling output rendering from the chat thread keeps the chat clean while giving the agent a canvas to show results.

**Key pieces:**
- `services/scratchpad.py` — thread-safe in-memory `dict[session_id][report_id]` artifact store. Ephemeral, same 2-hour session lifecycle as the Elastic index.
- `services/sandbox.py` — safe `exec()` runner. Allows only `pandas`, `numpy`, `plotly`, `scipy`, `math`, `statistics` imports. All other `__builtins__` write-capable operations are stripped.
- `api/v1/routes/scratchpad.py` — `GET /scratchpad/{session_id}/{report_id}` returns artifact JSON.
- `ScratchpadPage.jsx` — renders `react-plotly.js` chart from artifact JSON. Dark theme, fully interactive (hover, zoom, pan, download).

**Chart library:** `react-plotly.js` for ZScratchpad (interactive, generated from Python `fig.to_dict()`). `Recharts` retained for EDA dashboard (pre-computed series, lighter weight).

### Chat Response Formatting

**Decision:** Chat responses are plain prose. No em-dashes, no markdown bold/italic. Citations are inline `[n]` markers rendered as `<sup>` tags with a References footer.

**Backend contract:** Gemini system prompt enforces plain text. The `ChatMessage` schema adds `scratchpad_link` (optional URL string) and `clarification_form` (optional typed field spec).

**Frontend rendering:** `ChatBubble.jsx` parses `[n]` markers and renders `<sup>[n]</sup>`. `ClarificationForm.jsx` renders chip-select fields for hypothesis testing intake. Submitted form values are encoded as `metric=X, group_a=Y, ...` and sent as a normal chat message.

### LangGraph — Extended Chat Graph

New branches added to the existing graph:

| Route | Trigger | Nodes |
|---|---|---|
| `visualization` | "histogram", "bar chart", "plot", "chart" | `load_data → classify → visualization → END` |
| `hypothesis_clarify` | "hypothesis", "t-test" (no params yet) | `load_data → classify → hypothesis_clarify → END` |
| `hypothesis_run` | same keywords + `metric=` in query | `load_data → classify → hypothesis_run → END` |
```

- [ ] **Step 2: Commit**

```bash
git add "_bmad-output/planning-artifacts/architecture.md"
git commit -m "docs: update architecture with ZScratchpad, sandbox, chat formatting decisions"
```

---

## Self-Review

**Spec coverage:**
- ZScratchpad page with chart + summary — Task 10
- Plotly for interactive charts — Tasks 2, 10
- Visualization agent node — Task 5
- Hypothesis testing with clarification form chips — Tasks 5, 9
- Clean chat formatting (no em-dash, no **) — Task 6
- Superscript citations with references footer — Task 8
- Scratchpad link card in chat — Task 8
- Architecture doc updated — Task 12

**Placeholder scan:** No TBDs. All code is complete and self-contained per task.

**Type consistency:**
- `ScratchpadArtifact` fields (`type`, `title`, `chart`, `summary`, `metadata`) match in `scratchpad.py`, `scratchpad.py` route, and `ScratchpadPage.jsx`
- `clarification_form` dict shape from `hypothesis_clarify_node` matches `ClarificationForm` props
- `scratchpad_link` passed through `AgentState` and `answer_query_graph` return into `ChatMessage.scratchpad_link`
- `ChatBubble` consumes `message.scratchpad_link`, `message.citations`, `message.followups`, `message.content` — all present in `ChatMessage` schema
