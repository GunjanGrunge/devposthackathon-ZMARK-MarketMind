from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# ── Session file listing ──
class SessionFile(BaseModel):
    id: str
    name: str
    type: str          # csv | xlsx | pdf
    size: str
    rows: Optional[int] = None
    pages: Optional[int] = None
    status: str = "indexed"


class SessionFilesResponse(BaseModel):
    session_id: str
    files: List[SessionFile]


# ── KPI card ──
class KPIData(BaseModel):
    total_revenue: Optional[float] = None
    revenue_delta_pct: Optional[float] = None
    top_product: Optional[str] = None
    top_product_revenue: Optional[float] = None
    top_product_category: Optional[str] = None
    at_risk_skus: int = 0
    anomaly_count: int = 0
    anomaly_description: Optional[str] = None


# ── Chart series ──
class ChartPoint(BaseModel):
    label: str
    value: float


class RevenueTrendResponse(BaseModel):
    labels: List[str]
    values: List[float]
    anomaly_index: Optional[int] = None


# ── Product table ──
class ProductRow(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    revenue: float
    velocity: Optional[float] = None
    growth: Optional[float] = None
    velocity_decline_pct: Optional[float] = None  # % decline in last 90d vs prior 90d
    risk: Optional[int] = None
    level: Optional[str] = None      # low | medium | high
    action: Optional[str] = None     # Monitor | Maintain | Discount | Liquidate | Discontinue
    rationale: Optional[str] = None  # plain-English explanation of the risk score


# ── Policy / business-rule exclusions ──
class PolicyExclusion(BaseModel):
    type: str               # "month" | "category" | "channel"
    description: str        # human-readable, e.g. "May profit excluded per policy"
    excluded_amount: float  # revenue/profit amount excluded
    source_filename: str    # PDF that defined the rule


# ── Full dashboard response ──
class DashboardResponse(BaseModel):
    kpi: KPIData
    summary: str
    revenue_trend: RevenueTrendResponse
    products: List[ProductRow]
    channels: List[ChartPoint]
    categories: List[ChartPoint]
    suggested_questions: List[str]
    charts: Optional[Dict[str, Any]] = None
    agent_charts: Optional[List[Dict[str, Any]]] = None
    policy_exclusions: List[PolicyExclusion] = []


# ── Power Mode: Obsolescence ──
class RiskBreakdown(BaseModel):
    velocity_score: int      # 0–40 pts  (velocity_decline × 0.4 × 100)
    category_score: int      # 0–30 pts  ((1 − category_trend) × 0.3 × 100)
    depreciation_score: int  # 0–30 pts  (depreciation × 0.3 × 100)


class TrendPoint(BaseModel):
    label: str    # e.g. "Jan '24"
    value: float  # revenue or units


class ObsolescenceRow(BaseModel):
    name: str
    category: Optional[str] = None
    risk: int
    level: str              # low | medium | high
    action: str             # Monitor | Discount | Discontinue | Liquidate
    velocity_decline_pct: float
    rationale: str
    breakdown: Optional[RiskBreakdown] = None   # component score contributions
    trend: Optional[List[TrendPoint]] = None     # monthly series for sparkline
    signals: Optional[List[str]] = None          # plain-English bullet points


class ObsolescenceResponse(BaseModel):
    items: List[ObsolescenceRow]


# ── Power Mode: Budget Recommender ──
class BudgetItem(BaseModel):
    product: str
    confidence: str         # high | medium | low
    rationale: str


class BudgetResponse(BaseModel):
    increase: List[BudgetItem]
    maintain: List[BudgetItem]
    reduce: List[BudgetItem]


# ── Power Mode: Monte Carlo ──
class MonteCarloRequest(BaseModel):
    product: str
    budget_change_pct: float = 0
    horizon_days: int = 90
    simulations: int = 5000


class MonteCarloPoint(BaseModel):
    percentile: int
    revenue: float


class MonteCarloResponse(BaseModel):
    product: str
    horizon_days: int
    simulations: int
    budget_change_pct: float
    baseline_revenue: float
    expected_revenue: float
    p10_revenue: float
    p50_revenue: float
    p90_revenue: float
    probability_above_baseline: float
    probability_loss: float
    distribution: List[MonteCarloPoint]
    summary: str
    assumptions: List[str]


# ── Chat ──
class Citation(BaseModel):
    source: str
    ref: str
    excerpt: str


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


class ChatMessage(BaseModel):
    role: str   # user | assistant
    content: str
    citations: Optional[List[Citation]] = None
    followups: Optional[List[str]] = None
    scratchpad_link: Optional[str] = None       # "/scratchpad/{session_id}/{report_id}"
    clarification_form: Optional[ClarificationForm] = None


class ChatRequest(BaseModel):
    query: str
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    message: ChatMessage
