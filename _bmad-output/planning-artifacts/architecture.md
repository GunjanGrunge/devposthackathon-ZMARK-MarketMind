---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - "_bmad-output/planning-artifacts/marketmind-prd-001/prd.md"
  - "_bmad-output/planning-artifacts/marketmind-prd-001/addendum.md"
  - "_bmad-output/planning-artifacts/marketmind-prd-001/.decision-log.md"
  - "_bmad-output/planning-artifacts/epics.md"
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-06-03'
project_name: 'ZmaRk hack'
user_name: 'Timmy'
date: '2026-06-03'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
- **FR-1.1 to FR-1.4 (Data Ingestion):** Supports multi-format uploads (CSV, PDF, Excel) under 50MB. Text parsing uses `pdfplumber` and chunking runs at a target of 512 tokens with a 50-token overlap. All session uploads stream to a unified index namespace (`marketmind-{session_id}`).
- **FR-2.1 to FR-2.4 (EDA & Visualization):** Generates monthly metrics for revenue trends, sales velocities, and category breakdowns. Highlights anomalies using standard deviations ($>2$ std devs) from rolling means. Plain-English narrative summary generated via Gemini 2.5 Pro.
- **FR-3.1 to FR-3.4 (Elastic MCP Integration):** Combines keyword and semantic vectors natively via Reciprocal Rank Fusion, queried strictly through the Elastic MCP tool.
- **FR-4.1 to FR-4.4 (Active Analytical Chat Assistant):**
  - **Dynamic Python Sandbox:** Integrates a code-generation and local execution node inside LangGraph to run pandas computations (covariance, correlation, trend lines) on-the-fly to answer statistical queries.
  - **Grounded Deep Dives:** Merges PDF retrieval, CSV data rows, and cached obsolescence/ROI metrics into the LLM context to explain why products are flagging risk and where budget should be reallocated.
  - **Adaptive Suggestion Chips:** Follow-up questions are dynamically suggested based on the metrics derived in the chat (e.g., proposing a Monte Carlo run on a newly identified at-risk product).
- **FR-5.1 to FR-5.4 (Power Mode):** Features a 10,000-path NumPy Monte Carlo simulation, composite obsolescence risk scoring (decline rate + inventory + depreciation), and external market trends.

**Non-Functional Requirements:**
- **Performance:** Chat queries must return in $<5$ seconds (p95), and the EDA generator must process datasets up to 100k rows in $<10$ seconds.
- **Data Privacy & Security:** Zero long-term user data persistence. Cloud Storage file payloads are deleted immediately after indexing, and the Elastic indices are deleted after 2 hours of inactivity. All API keys and secrets reside in GCP Secret Manager.
- **Elastic Integration Compliance:** Absolute requirement that the Elastic MCP server serves as the sole gateway for search retrievals.
- **Safety & Isolation:** Sandboxed execution of LLM-generated code against session data. Strict isolation of indices per session UUID.

**Scale & Complexity:**
- **Primary Domain:** Full-Stack AI/RAG Web Application
- **Complexity Level:** Medium (Hackathon scope: high density of complex features like Monte Carlo and hybrid search, but low compliance/database complexity due to session-only storage).
- **Estimated Architectural Components:** 4 core layers (Frontend UI, Gateway API, LangGraph Orchestration, Elastic Vector Store).

### Technical Constraints & Dependencies
- **FastAPI / Python (3.11+):** Backend runs as a containerized microservice on Google Cloud Run.
- **Next.js 14 (App Router):** Hosted on Vercel, querying the backend via session-labeled REST endpoints.
- **ELSER Embedding Model:** Built directly into Elastic Cloud, avoiding external API round-trips for embedding generation during upload.
- **LangGraph Routing:** Drives the core decision tree, branching queries into static RAG retrieval, analytical code execution, or metrics deep-dives based on user intent.

### Cross-Cutting Concerns Identified
- **Session Isolation:** Multiple parallel users must have strictly separated Elastic indices (`marketmind-{session_id}`) to prevent crosstalk.
- **API Rate Limits:** Potential Gemini quota limitations under peak concurrent user loads; mitigated by using the faster, lighter `gemini-1.5-flash` model for query classification tasks.
- **UI Error Boundaries:** Graces under failure: if the LLM or indexing fails, the client should show localized skeleton UI or retry notifications rather than a global crash.

## Starter Template Evaluation

### Primary Technology Domain
**Full-Stack Web Application + API Backend** (Next.js 14 Frontend & FastAPI Backend).

### Starter Options Considered

1. **Frontend: create-next-app@latest (Selected)**
   - **Rationale:** The official Next.js initializer. It is the standard, well-maintained starter that sets up our locked choices (TypeScript, Tailwind CSS, App Router, ESLint, and `@/*` imports) non-interactively in one command.
   - **Initialization Command:**
     ```bash
     npx create-next-app@latest frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --yes
     ```

2. **Backend: Layered FastAPI Starter (Selected)**
   - **Rationale:** Rather than using a bloated boilerplate with unused ORM databases (since our data is transient and session-only), we will initialize a clean, lightweight layered structure manually. This separates routes, business services, and LangGraph states to keep our code modular.
   - **Initialization commands & structure:**
     ```bash
     mkdir -p backend/app/api/v1/routes backend/app/core backend/app/services backend/tests
     touch backend/app/main.py backend/requirements.txt backend/.env
     ```

### Selected Starters & Decisions Provided

#### Frontend: `frontend/` (Next.js 14 App Router)
- **Language & Runtime:** TypeScript (`tsconfig.json` preconfigured). Node/npm runtime.
- **Styling Solution:** Tailwind CSS with utility class patterns, ready for shadcn/ui component integration.
- **Build Tooling:** Webpack/Turbopack built-in with Next.js fast-refresh development server.
- **Code Organization:** Modern App Router hierarchy housed inside a `/src` directory for clean code segregation:
  - `src/app/` (page routes, layouts, and global providers).
  - `src/components/` (reusable UI cards, tables, and forms).
  - `src/store/` (Zustand state management for chat session state).

#### Backend: `backend/` (Layered FastAPI)
- **Language & Runtime:** Python 3.11+ async runtime. Dependency management via `requirements.txt`.
- **API Routing:** FastAPI `APIRouter` instances grouped under `app/api/v1/routes/` (`upload.py`, `chat.py`, `simulate.py`).
- **Core Configurations:** Unified management of API keys and environmental secrets (GCP Secret Manager) inside `app/core/config.py`.
- **Code Organization:** Strict segregation of business logic:
  - `app/services/eda.py` (Pandas analysis and anomaly checks).
  - `app/services/graphs/` (LangGraph state definitions and node routines).
  - `app/services/montecarlo.py` (SciPy/NumPy vector operations).

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- **Dynamic Code Execution Sandbox:** FastAPI REST API executing LLM-generated Python code safely in a restricted scope.
- **Session Isolation:** Header-based index isolation (`X-Session-ID` → `marketmind-{session_id}`).
- **Data Disposal (ILM):** Explicit delete endpoints coupled with a 2-hour Elastic Index Lifecycle Policy.

**Important Decisions (Shape Architecture):**
- **LangGraph Routing:** Query classification (`eda` vs `retrieval` vs `analytical_sandbox`) using `gemini-1.5-flash`.
- **GCS Staging:** Uploaded files staged in a temporary Cloud Storage directory, deleted immediately after Elastic indexing completes.

**Deferred Decisions (Post-MVP):**
- **User Authentication:** Deferred post-hackathon; session UUID is sufficient for scoping.
- **Persistent DB (PostgreSQL):** Deferred; all analytical tables and data are cached in-session.

### Data Architecture

- **Transient Storage:** In-memory pandas cache keyed by `session_id` in FastAPI for immediate EDA calls.
- **Search Vector Base:** Elastic Cloud cluster (8.13.0) using ELSER sparse vector embeddings mapped inside a single session-scoped index.

### Authentication & Security

- **Restricted Sandbox:** Backend execution uses `exec()` within a scope restricted of write access, `__builtins__`, and library imports outside of `pandas` and `numpy`.
- **Secrets Management:** Environment variables are strictly mounted from GCP Secret Manager on deployment; no local `.env` files are pushed.

### API & Communication Patterns

- **API Style:** REST API (FastAPI) utilizing JSON payloads and custom headers.
- **CORS Configuration:** FastAPI CORS middleware configured to allow origins from specific Vercel and local development hosts.
- **Agent Builder Integration:** A custom API endpoint `/chat` is registered as a OpenAPI tool inside Google Cloud Agent Builder using Bearer authentication.

### Frontend Architecture

- **Client State:** Zustand store (`useSessionStore`) maps state across file lists, upload speeds, and current active chats.
- **Chart Componentry:** Recharts components wrapped inside shadcn/ui Card structures.

### Infrastructure & Deployment

- **Hosting Platform:** Frontend hosted on Vercel; Backend hosted on Google Cloud Run as a stateless container.
- **Clean-up Daemon:** 2-hour Elastic ILM policy target configured upon index creation.

## Implementation Patterns & Consistency Rules

### Naming Patterns

- **API Routes:** Endpoints are plural-based (session resources) but respect the hackathon contract boundaries:
  - `POST /upload`
  - `GET /eda/{session_id}`
  - `POST /chat`
  - `POST /simulate/montecarlo`
  - `GET /power/obsolescence/{session_id}`
  - `GET /power/budget-recommendations/{session_id}`
  - `DELETE /session/{session_id}`
- **JSON Field Convention:** All JSON request and response payloads MUST use **snake_case** keys exclusively (matching standard Python paradigms).
  - *Good:* `{"session_id": "uuid-v4", "units_sold": 45}`
  - *Bad:* `{"sessionId": "uuid-v4", "unitsSold": 45}`
- **Frontend Code Files:** Next.js route folders are lowercase (`/src/app/`). Reusable React components use **PascalCase** (`UploadZone.tsx`, `ChatPanel.tsx`). Local helpers and hooks use **camelCase** (`useDebounce.ts`).
- **Backend Code Files:** Python modules use **snake_case** (`main.py`, `upload.py`, `chat_graph.py`).

### Structure Patterns

- **Test Placement:** Backend tests live inside `backend/tests/` (grouped by endpoint). Frontend Playwright/Jest tests are co-located alongside the component using `.test.tsx` naming.
- **Shared Schemas:** Pydantic schemas (backend) and TypeScript interfaces (frontend) are aligned. Any type used for data transfer is explicitly declared in `backend/app/schemas/` and mirrored in `frontend/src/types/`.

### API Response & Error Formats

- **Standard Success Response Wrapper:** Simple JSON objects directly representing the payload as documented in the API contract.
- **Standard Error Payload:** Every error response MUST yield a HTTP $4xx/5xx$ status code accompanied by a standard payload:
  ```json
  {
    "error": "insufficient_data",
    "message": "RTX 4070 has fewer than 3 historical data points to run a simulation."
  }
  ```
- **HTTP Status Codes:**
  - `413 Request Entity Too Large` (Upload exceeds 50MB).
  - `422 Unprocessable Entity` (Schema parsing or mathematical simulation validation failure).
  - `500 Internal Server Error` (Failed upstream LLM or search engine connection).

### State Management Patterns (Zustand)

- **Store Definition:** Frontend state stores are split by concern:
  - `useSessionStore` in [useSessionStore.ts](file:///c:/Users/Bot/Desktop/ZmaRk%20hack/frontend/src/store/useSessionStore.ts) handles active files, layout sizing, and upload progress.
  - `useChatStore` in [useChatStore.ts](file:///c:/Users/Bot/Desktop/ZmaRk%20hack/frontend/src/store/useChatStore.ts) handles messages, citations, streaming states, and suggested follow-ups.
- **State Mutation:** Component code must never write directly to store properties. State mutations must run through explicit action setters.

### Process & Security Patterns

- **Restricted execution in `code_executor_node`:** LLM-generated code execution runs inside a sandbox constructed as:
  ```python
  def execute_code_sandboxed(code_str: str, df: pd.DataFrame) -> dict:
      # Block basic system commands and file system access
      forbidden = ["import os", "sys", "subprocess", "open", "eval", "getattr"]
      if any(term in code_str for term in forbidden):
          return {"success": False, "error": "security_violation"}
      
      local_scope = {"df": df, "pd": pd, "np": np}
      try:
          exec(code_str, {"__builtins__": {}}, local_scope)
          return {"success": True, "result": local_scope.get("result", None)}
      except Exception as e:
          return {"success": False, "error": str(e)}
  ```

### Anti-Patterns to Avoid

- **Direct DB Queries in Routes:** Backend endpoints must not manipulate data frames or run raw searches. They must dispatch requests directly to `app/services/` logic.
- **Hardcoding API Keys:** No active API keys (Elastic, Gemini) are permitted in local `.env` files. Secrets must always resolve from the environment (GCP Secret Manager mounts).

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
ZmaRk hack/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routes/
│   │   │       │   ├── upload.py          # POST /upload, GET /schema
│   │   │       │   ├── chat.py            # POST /chat (routes to LangGraph)
│   │   │       │   └── simulate.py        # POST /simulate, GET /obsolescence, GET /budget
│   │   │       └── api.py                 # Combines routers
│   │   ├── core/
│   │   │   ├── config.py                  # Environment parsing + GCP Secret Manager
│   │   │   └── sandbox.py                 # python exec() restricted sandbox
│   │   ├── schemas/
│   │   │   ├── upload.py                  # Pydantic schemas for upload responses
│   │   │   ├── chat.py                    # Pydantic schemas for chat payload/responses
│   │   │   └── simulate.py                # Pydantic schemas for simulations
│   │   ├── services/
│   │   │   ├── eda.py                     # Pandas aggregation & anomaly maths
│   │   │   ├── montecarlo.py              # NumPy simulator logic
│   │   │   ├── obsolescence.py            # Composite risk calculation logic
│   │   │   └── graphs/
│   │   │       ├── chat_graph.py          # StateGraph construction & compilation
│   │   │       └── nodes.py               # Node handlers (classify, retrieve, synthesize)
│   │   └── main.py                        # FastAPI entry point & initialization
│   ├── tests/
│   │   ├── test_upload.py
│   │   ├── test_chat.py
│   │   └── test_simulate.py
│   ├── requirements.txt                   # Locked production Python libraries
│   └── Dockerfile                         # Build definition for Cloud Run
│
├── zmark/                                 # Pre-existing custom React/JSX frontend
│   ├── ZmaRk.html                         # SPA document loading CDN react & local scripts
│   ├── app.jsx                            # Flow state machine & shell routing
│   ├── auth.jsx                           # Login & Welcome splash screens
│   ├── screens.jsx                        # Layout grids, FileRail, Landing, SchemaConfirm
│   ├── chat.jsx                           # Conversation logs, citations, and footnotes
│   ├── power.jsx                          # Obsolescence tables & Monte Carlo sliders
│   ├── charts.jsx                         # Render helper wrappers for dashboard metrics
│   ├── components.jsx                     # UI library primitives (Button, Badge, Select)
│   ├── icons.jsx                          # SVG symbol libraries
│   ├── data.js                            # Static window.ZDATA config mappings
│   ├── styles.css                         # Custom layout themes and styling classes
│   └── tweaks-panel.jsx                   # Theme/Accent control interface
```

### Architectural Boundaries

**API Boundaries:**
- The frontend `zmark` application runs directly in the browser using Babel Standalone. It communicates with the FastAPI backend at `http://localhost:8000` via async AJAX calls using the standard `fetch()` API.
- FastAPI endpoints located in `backend/app/api/v1/routes/` serve as the absolute boundary. No raw computation occurs inside the routes; they serve as controllers validating inputs and dispatching work to `app/services/` classes.

**Component Boundaries:**
- **State isolation:** Dynamic properties are managed in React state hooks at the `App` root level in `app.jsx` and passed down. All API outputs (such as calculated EDA values and chat histories) are bound directly to `window.ZDATA` or local states.
- **LangGraph boundary:** The `/chat` route delegates the entire execution tree to `compiled_chat_graph.ainvoke()` in [chat_graph.py](file:///c:/Users/Bot/Desktop/ZmaRk%20hack/backend/app/services/graphs/chat_graph.py). API controllers interact only with this interface, treating the graph as a black box.

**Data Boundaries:**
- **Indexed Boundaries:** Indexes in Elastic Cloud are scoped explicitly: `marketmind-{session_id}`.
- **DataFrame Cache:** A global thread-safe dictionary in FastAPI caches parsed DataFrames by `session_id` to prevent redundant reading of files during short sessions.

### Requirements to Structure Mapping

- **Epic 1: Data Ingestion**
  - Backend: `routes/upload.py`, `services/eda.py` (for schema detection).
  - Frontend: `zmark/screens.jsx` (`UploadProgress` & `SchemaConfirm` views).
- **Epic 2: EDA & Visualization**
  - Backend: `services/eda.py` (aggregations + anomaly formulas).
  - Frontend: `zmark/charts.jsx` and `zmark/screens.jsx` (`DashboardMain` view).
- **Epic 3: Elastic Search Integration**
  - Backend: `core/sandbox.py`, `services/graphs/nodes.py` (MCP search executions).
- **Epic 4: AI Chat Assistant**
  - Backend: `services/graphs/chat_graph.py`, `services/graphs/nodes.py`.
  - Frontend: `zmark/chat.jsx` (`ChatPanel` view).
- **Epic 5: Power Mode**
  - Backend: `routes/simulate.py`, `services/montecarlo.py`, `services/obsolescence.py`.
  - Frontend: `zmark/power.jsx` (`PowerSection` view).

### ZScratchpad — Agent Output Canvas

**Decision:** Add a `/scratchpad/:sessionId/:reportId` route as a dedicated display surface for rich agent outputs (interactive charts, hypothesis test reports).

**Rationale:** Chat bubbles are unsuitable for full-width interactive Plotly charts. Decoupling output rendering from the chat thread keeps the chat clean while giving the agent a canvas to show results.

**Key pieces:**
- `services/scratchpad.py` — thread-safe in-memory `dict[session_id][report_id]` artifact store. Ephemeral, same 2-hour session lifecycle as the Elastic index.
- `services/sandbox.py` — safe `exec()` runner. Allows only `pandas`, `numpy`, `plotly`, `scipy`, `math`, `statistics` imports. Strips dangerous builtins. Validates that `fig` is a `plotly.basedatatypes.BaseFigure` before serialization.
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
| `visualization` | "histogram", "bar chart", "plot", "chart" | `load_data → classify → visualization → followup → END` |
| `hypothesis_clarify` | "hypothesis", "t-test" (no params yet) | `load_data → classify → hypothesis_clarify → END` |
| `hypothesis_run` | same keywords + `metric=` in query | `load_data → classify → hypothesis_run → followup → END` |

**Security:** User-controlled strings (group names, metric names) are sanitized via `_safe_str` (alphanumeric + safe chars only) before embedding in sandbox code. Query strings are quote-stripped before embedding in Gemini prompts.


