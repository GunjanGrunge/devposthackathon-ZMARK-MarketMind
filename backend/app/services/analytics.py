"""
analytics.py — Derives KPIs, chart series, product table, and narrative
summary from session-cached DataFrames.  Falls back gracefully when no
structured data is present.
"""
import logging
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from app.core.config import settings
from app.services.analysis_context import get_analysis_context
from app.services.eda import ensure_session_loaded, session_store, store_lock
from app.schemas.analytics import (
    KPIData, ChartPoint, RevenueTrendResponse, ProductRow, DashboardResponse,
    ObsolescenceRow, ObsolescenceResponse, RiskBreakdown, TrendPoint,
    BudgetItem, BudgetResponse, MonteCarloPoint, MonteCarloResponse,
)

logger = logging.getLogger("analytics")


def _extract_python_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.S | re.I)
    return match.group(1).strip() if match else text.strip()


def _format_value_list(values: List[str], limit: int = 3) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    cleaned = list(dict.fromkeys(cleaned))[:limit]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _top_text_values(df: pd.DataFrame, col: Optional[str], limit: int = 3) -> List[str]:
    if not col or col not in df.columns:
        return []
    values = df[col].dropna().astype(str).str.strip()
    values = values[~values.str.lower().isin(["", "nan", "none", "null"])]
    if values.empty:
        return []
    return values.value_counts().head(limit).index.tolist()


def _business_focus_sentence(
    df: pd.DataFrame,
    product_col: Optional[str],
    category_col: Optional[str],
    channel_col: Optional[str],
) -> str:
    categories = _top_text_values(df, category_col, 3)
    if not categories:
        for col in df.columns:
            clean = _clean_name(col)
            if any(keyword in clean for keyword in ["category", "subcategory", "subcat", "department"]):
                categories = _top_text_values(df, col, 3)
                if categories:
                    break
    products = _top_text_values(df, product_col, 4)
    channels = _top_text_values(df, channel_col, 2)

    category_text = _format_value_list(categories)
    product_text = _format_value_list(products)
    channel_text = _format_value_list(channels, 2)

    if category_text and product_text:
        sentence = f"This dataset appears to focus on sales of {category_text}, including {product_text}."
    elif product_text:
        sentence = f"This dataset appears to focus on sales of products such as {product_text}."
    elif category_text:
        sentence = f"This dataset appears to focus on sales across {category_text}."
    else:
        return ""

    if channel_text:
        sentence = sentence[:-1] + f" through {channel_text} channels."
    return sentence


def _ensure_business_context_in_summary(
    df: pd.DataFrame,
    summary: str,
    product_col: Optional[str],
    category_col: Optional[str],
    channel_col: Optional[str],
) -> str:
    focus = _business_focus_sentence(df, product_col, category_col, channel_col)
    normalized_summary = summary.strip()
    if not focus:
        return normalized_summary
    if not normalized_summary:
        return focus
    if normalized_summary.lower().startswith("this dataset appears to focus"):
        return normalized_summary
    return f"{focus} {normalized_summary}"


# ────────────────────────────────────────────────────────────────────────────
# Column-detection helpers
# ────────────────────────────────────────────────────────────────────────────
def _find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    for kw in keywords:
        for col in df.columns:
            if kw in col.lower():
                return col
    return None


def _clean_name(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _numeric_series(series: pd.Series) -> pd.Series:
    """Coerce currency/percentage/comma-formatted numbers into numeric values."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _datetime_series(series: pd.Series) -> pd.Series:
    """Parse common date formats, including mixed US/EU strings and Excel serial dates."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    non_null = series.dropna()
    if not non_null.empty and pd.api.types.is_numeric_dtype(non_null):
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.dropna().between(20_000, 80_000).mean() > 0.7:
            return pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")

    text = series.astype(str).str.strip()
    candidates = [
        pd.to_datetime(text, errors="coerce", format="mixed"),
        pd.to_datetime(text, errors="coerce", dayfirst=False),
        pd.to_datetime(text, errors="coerce", dayfirst=True),
    ]
    return max(candidates, key=lambda parsed: parsed.notna().sum())


def _parseable_date_ratio(series: pd.Series) -> float:
    sampled = series.dropna().head(200)
    if sampled.empty:
        return 0.0
    return float(_datetime_series(sampled).notna().mean())


def _parseable_numeric_ratio(series: pd.Series) -> float:
    sampled = series.dropna().head(500)
    if sampled.empty:
        return 0.0
    return float(_numeric_series(sampled).notna().mean())


def _find_date_col(df: pd.DataFrame) -> Optional[str]:
    best: tuple[float, Optional[str]] = (0.0, None)
    for col in df.columns:
        clean = _clean_name(col)
        score = 0.0
        if any(token in clean for token in ["date", "time", "timestamp", "period", "month", "orderdate", "shipdate"]):
            score += 3.0
        score += _parseable_date_ratio(df[col]) * 4.0
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 2.5 else None


def _find_revenue_col(df: pd.DataFrame) -> Optional[str]:
    keywords = ["revenue", "sales", "sale", "amount", "total", "gmv", "net", "gross", "value", "profit"]
    best: tuple[float, Optional[str]] = (0.0, None)
    for col in df.columns:
        clean = _clean_name(col)
        numeric_ratio = _parseable_numeric_ratio(df[col])
        if numeric_ratio < 0.6:
            continue
        score = numeric_ratio * 3.0
        for keyword in keywords:
            if keyword in clean:
                score += 5.0
                break
        if any(bad in clean for bad in ["discount", "postal", "zip", "id", "quantity", "qty", "unit", "count"]):
            score -= 2.0
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 2.0 else None


def _find_product_col(df: pd.DataFrame) -> Optional[str]:
    keywords = ["product", "item", "sku", "name", "title", "description"]
    negative_keywords = [
        "customer", "client", "consumer", "segment", "class", "city", "state", "region",
        "country", "postal", "zip", "ship", "shipping", "market", "territory", "manager",
        "person", "contact", "order", "row",
    ]
    best: tuple[float, Optional[str]] = (0.0, None)
    row_count = max(len(df), 1)
    for col in df.columns:
        clean = _clean_name(col)
        if any(keyword in clean for keyword in negative_keywords):
            continue
        if _parseable_numeric_ratio(df[col]) > 0.8:
            continue
        unique = df[col].dropna().astype(str).nunique()
        if unique <= 1:
            continue
        score = 0.0
        if any(keyword in clean for keyword in keywords):
            score += 5.0
        if "id" in clean and "product" not in clean and "sku" not in clean:
            score -= 3.0
        cardinality = unique / row_count
        if 0.01 <= cardinality <= 0.8:
            score += 2.0
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 5.0 else None


def _find_category_col(df: pd.DataFrame) -> Optional[str]:
    keywords = ["category", "subcategory", "subcat", "cat", "department"]
    soft_keywords = ["group", "type"]
    negative_keywords = [
        "customer", "consumer", "segment", "class", "city", "state", "region", "country",
        "postal", "zip", "ship", "shipping", "market", "channel", "source", "platform",
    ]
    best: tuple[float, Optional[str]] = (0.0, None)
    for col in df.columns:
        clean = _clean_name(col)
        if any(keyword in clean for keyword in negative_keywords):
            continue
        if _parseable_date_ratio(df[col]) > 0.6:
            continue
        if _parseable_numeric_ratio(df[col]) > 0.8:
            continue
        unique = df[col].dropna().astype(str).nunique()
        if unique <= 1:
            continue
        score = 0.0
        if any(keyword in clean for keyword in keywords):
            score += 5.0
        elif any(keyword in clean for keyword in soft_keywords):
            score += 3.0
        if unique <= 50:
            score += 2.0
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 5.0 else None


def _find_channel_col(df: pd.DataFrame) -> Optional[str]:
    keywords = ["channel", "source", "platform", "store", "marketplace", "shipmode"]
    negative_keywords = [
        "category", "subcategory", "department", "class", "segment", "consumer", "customer",
        "city", "state", "region", "country", "postal", "zip", "product", "item", "sku",
    ]
    best: tuple[float, Optional[str]] = (0.0, None)
    for col in df.columns:
        clean = _clean_name(col)
        if any(keyword in clean for keyword in negative_keywords):
            continue
        if _parseable_date_ratio(df[col]) > 0.6:
            continue
        if _parseable_numeric_ratio(df[col]) > 0.8:
            continue
        unique = df[col].dropna().astype(str).nunique()
        if unique <= 1:
            continue
        score = 0.0
        if any(keyword in clean for keyword in keywords):
            score += 5.0
        if unique <= 30:
            score += 1.5
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 5.0 else None


def _find_units_col(df: pd.DataFrame) -> Optional[str]:
    keywords = ["unit", "units", "qty", "quantity", "count", "sold", "volume", "orders"]
    best: tuple[float, Optional[str]] = (0.0, None)
    for col in df.columns:
        clean = _clean_name(col)
        numeric_ratio = _parseable_numeric_ratio(df[col])
        if numeric_ratio < 0.6:
            continue
        score = numeric_ratio * 2.0
        if any(keyword in clean for keyword in keywords):
            score += 5.0
        if any(bad in clean for bad in ["revenue", "sales", "amount", "total", "price", "profit", "discount"]):
            score -= 3.0
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 3.0 else None


# ────────────────────────────────────────────────────────────────────────────
# Anomaly detection
# ────────────────────────────────────────────────────────────────────────────
def _detect_anomaly(values: List[float]) -> Optional[int]:
    if len(values) < 4:
        return None
    arr = np.array(values, dtype=float)
    mean, std = arr.mean(), arr.std()
    if std == 0:
        return None
    zscores = np.abs((arr - mean) / std)
    idx = int(np.argmax(zscores))
    return idx if zscores[idx] > 2.0 else None


# ────────────────────────────────────────────────────────────────────────────
# Temporal velocity-decline risk scoring (per-product, not cross-sectional)
# ────────────────────────────────────────────────────────────────────────────
def _compute_velocity_decline(
    product_df: pd.DataFrame,
    metric_col: str,
    date_col: Optional[str],
) -> float:
    """
    Returns a 0–1 float where 1.0 = 100% decline.
    Compares the average metric in the last 90 days vs the prior 90 days.
    Falls back to first-half vs second-half when date column is absent.
    """
    product_df = product_df.copy()
    product_df[metric_col] = _numeric_series(product_df[metric_col]).fillna(0)

    if date_col and len(product_df) >= 4:
        product_df["_date"] = _datetime_series(product_df[date_col])
        valid = product_df.dropna(subset=["_date"]).sort_values("_date")
        if not valid.empty:
            max_date = valid["_date"].max()
            recent_cut = max_date - pd.Timedelta(days=90)
            prior_cut = recent_cut - pd.Timedelta(days=90)

            recent = valid[valid["_date"] >= recent_cut][metric_col]
            prior = valid[(valid["_date"] >= prior_cut) & (valid["_date"] < recent_cut)][metric_col]

            recent_avg = recent.mean() if len(recent) > 0 else None
            prior_avg = prior.mean() if len(prior) > 0 else None

            if recent_avg is not None and prior_avg is not None and prior_avg > 0:
                decline = (prior_avg - recent_avg) / prior_avg
                return float(max(0.0, min(1.0, decline)))

    # Fallback: first vs second half
    vals = product_df[metric_col].values
    half = len(vals) // 2
    if half < 2:
        return 0.0
    first_avg = float(vals[:half].mean()) if half > 0 else 0
    second_avg = float(vals[half:].mean())
    if first_avg > 0 and second_avg < first_avg:
        return float(max(0.0, min(1.0, (first_avg - second_avg) / first_avg)))
    return 0.0


def _compute_category_trend(
    df: pd.DataFrame,
    category_value: Optional[str],
    category_col: Optional[str],
    metric_col: str,
    date_col: Optional[str],
) -> float:
    """
    Returns a 0–1 score where 1.0 = category is growing strongly.
    Uses first-half vs second-half of the category's aggregate metric.
    """
    if not category_col or not category_value or category_col not in df.columns:
        return 0.5  # neutral default

    cat_df = df[df[category_col] == category_value].copy()
    cat_df[metric_col] = _numeric_series(cat_df[metric_col]).fillna(0)

    if date_col and len(cat_df) >= 4:
        cat_df["_date"] = _datetime_series(cat_df[date_col])
        cat_df = cat_df.dropna(subset=["_date"]).sort_values("_date")
        if not cat_df.empty:
            half = len(cat_df) // 2
            first_avg = cat_df[metric_col].iloc[:half].mean()
            second_avg = cat_df[metric_col].iloc[half:].mean()
            if first_avg > 0:
                ratio = second_avg / first_avg
                return float(min(1.0, max(0.0, ratio)))

    vals = cat_df[metric_col].values
    half = len(vals) // 2
    if half < 2:
        return 0.5
    first_avg = float(vals[:half].mean()) if half > 0 else 1
    second_avg = float(vals[half:].mean())
    if first_avg > 0:
        return float(min(1.0, max(0.0, second_avg / first_avg)))
    return 0.5


def _build_rationale(
    product_name: str,
    velocity_decline_pct: float,
    category_trend_score: float,
    risk: int,
    action: str,
) -> str:
    reasons = []
    if velocity_decline_pct >= 40:
        reasons.append(f"sales velocity has dropped {velocity_decline_pct:.0f}% in the last 90 days")
    elif velocity_decline_pct >= 15:
        reasons.append(f"sales velocity is down {velocity_decline_pct:.0f}% vs the prior 90-day window")
    elif velocity_decline_pct > 0:
        reasons.append(f"a {velocity_decline_pct:.0f}% dip in recent sales velocity")
    else:
        reasons.append("stable or growing sales velocity")

    if category_trend_score < 0.6:
        reasons.append("its product category is also contracting")
    elif category_trend_score > 1.1:
        reasons.append("the broader category is expanding")

    reason_str = " and ".join(reasons) if reasons else "historical trend analysis"

    action_prefix = {
        "Liquidate": f"Immediate liquidation recommended (risk score {risk}/100)",
        "Discontinue": f"Planned discontinuation suggested (risk score {risk}/100)",
        "Discount": f"Targeted discounting recommended (risk score {risk}/100)",
        "Monitor": f"Monitor closely (risk score {risk}/100)",
    }.get(action, f"Review required (risk score {risk}/100)")

    return f"{action_prefix} — driven by {reason_str}."


def _compute_product_risk(
    product_name: str,
    df: pd.DataFrame,
    product_col: str,
    metric_col: str,
    date_col: Optional[str],
    category_col: Optional[str],
) -> Tuple[str, str, int, float, str, dict]:
    """
    Returns (level, action, risk_score 0-100, velocity_decline_pct, rationale, breakdown).

    breakdown = {"velocity_score": int, "category_score": int, "depreciation_score": int}

    Risk formula (from architecture spec):
      velocity_decline × 0.4 + (1 − category_trend) × 0.3 + depreciation × 0.3
    Depreciation defaults to 0.5 (neutral) when product age is unknown.
    """
    product_df = df[df[product_col] == product_name]

    velocity_decline = _compute_velocity_decline(product_df, metric_col, date_col)
    velocity_decline_pct = round(velocity_decline * 100, 1)

    # Category of this product (most common value)
    category_value = None
    if category_col and category_col in product_df.columns:
        mode = product_df[category_col].mode()
        if not mode.empty:
            category_value = str(mode.iloc[0])

    category_trend_score = _compute_category_trend(df, category_value, category_col, metric_col, date_col)

    depreciation = 0.5  # neutral; real age data would improve this

    raw_risk = velocity_decline * 0.4 + (1 - category_trend_score) * 0.3 + depreciation * 0.3
    risk = int(max(0, min(100, round(raw_risk * 100))))

    if risk >= 85:
        level, action = "high", "Liquidate"
    elif risk >= 70:
        level, action = "high", "Discontinue"
    elif risk >= 40:
        level, action = "medium", "Discount"
    else:
        level, action = "low", "Monitor"

    rationale = _build_rationale(product_name, velocity_decline_pct, category_trend_score, risk, action)

    breakdown = {
        "velocity_score": int(velocity_decline * 0.4 * 100),
        "category_score": int((1 - category_trend_score) * 0.3 * 100),
        "depreciation_score": int(depreciation * 0.3 * 100),
    }

    return level, action, risk, velocity_decline_pct, rationale, breakdown


# ────────────────────────────────────────────────────────────────────────────
# Sparkline trend + plain-English signals for the drilldown UI
# ────────────────────────────────────────────────────────────────────────────
def _get_product_trend(
    df: pd.DataFrame,
    product_name: str,
    product_col: str,
    metric_col: str,
    date_col: Optional[str],
) -> List[dict]:
    """Returns [{label, value}] monthly series for the product sparkline chart."""
    if not date_col:
        return []
    pdf = df[df[product_col] == product_name].copy()
    pdf[metric_col] = _numeric_series(pdf[metric_col]).fillna(0)
    pdf["_d"] = _datetime_series(pdf[date_col])
    pdf = pdf.dropna(subset=["_d"])
    if pdf.empty:
        return []
    monthly = pdf.set_index("_d").resample("ME")[metric_col].sum()
    return [{"label": idx.strftime("%b '%y"), "value": round(float(v), 2)} for idx, v in monthly.items()]


def _get_product_signals(
    product_name: str,
    velocity_decline_pct: float,
    velocity_decline: float,
    category_trend_score: float,
    category_value: Optional[str],
    risk: int,
    product_df: pd.DataFrame,
    metric_col: str,
    date_col: Optional[str],
) -> List[str]:
    """Generates specific, data-grounded bullet signals for the drilldown tooltip."""
    signals: List[str] = []

    # Velocity signal — include actual average values when possible
    if date_col:
        pdf = product_df.copy()
        pdf[metric_col] = _numeric_series(pdf[metric_col]).fillna(0)
        pdf["_d"] = _datetime_series(pdf[date_col])
        pdf = pdf.dropna(subset=["_d"]).sort_values("_d")
        if not pdf.empty:
            max_d = pdf["_d"].max()
            recent_cut = max_d - pd.Timedelta(days=90)
            prior_cut = recent_cut - pd.Timedelta(days=90)
            recent = pdf[pdf["_d"] >= recent_cut][metric_col]
            prior = pdf[(pdf["_d"] >= prior_cut) & (pdf["_d"] < recent_cut)][metric_col]

            if len(recent) > 0 and len(prior) > 0:
                r_avg = float(recent.mean())
                p_avg = float(prior.mean())
                if velocity_decline_pct > 5:
                    signals.append(
                        f"Sales velocity dropped {velocity_decline_pct:.0f}% — "
                        f"avg ${p_avg:,.0f}/period → ${r_avg:,.0f}/period in the last 90 days."
                    )
                else:
                    signals.append(
                        f"Sales velocity is stable — avg ${r_avg:,.0f}/period over the last 90 days."
                    )
            elif velocity_decline_pct > 5:
                signals.append(f"Sales velocity declined {velocity_decline_pct:.0f}% vs the prior 90-day window.")
            else:
                signals.append("Sales velocity shows no significant decline in the last 90 days.")
    elif velocity_decline_pct > 5:
        signals.append(f"Sales velocity declined {velocity_decline_pct:.0f}% (first-half vs second-half comparison).")
    else:
        signals.append("Sales velocity is stable across the uploaded data window.")

    # Category signal
    if category_value:
        if category_trend_score < 0.7:
            cat_decline = round((1 - category_trend_score) * 100)
            signals.append(
                f"Category '{category_value}' is also contracting "
                f"({cat_decline}% overall revenue decline in the same window)."
            )
        elif category_trend_score > 1.05:
            signals.append(
                f"Category '{category_value}' is expanding, but this product is not keeping pace."
            )
        else:
            signals.append(f"Category '{category_value}' is broadly stable.")

    # Depreciation factor note (always 50% until product-age tracking is added)
    signals.append(
        "Depreciation factor: 50% (neutral — product age not tracked; "
        "add age data to improve this component)."
    )

    return signals


# ────────────────────────────────────────────────────────────────────────────
# Business summary narrative
# ────────────────────────────────────────────────────────────────────────────
def _generate_business_summary(
    df: pd.DataFrame,
    revenue_col: str,
    product_col: Optional[str],
    total_revenue: float,
    revenue_delta: float,
    anomaly_idx: Optional[int],
    labels: List[str],
    date_col: Optional[str] = None,
    category_col: Optional[str] = None,
    channel_col: Optional[str] = None,
    units_col: Optional[str] = None,
) -> str:
    parts: List[str] = []
    focus_sentence = _business_focus_sentence(df, product_col, category_col, channel_col)
    if focus_sentence:
        parts.append(focus_sentence)

    delta_str = f"+{revenue_delta:.1f}%" if revenue_delta > 0 else f"{revenue_delta:.1f}%"
    trend_phrase = (
        f"Revenue is {delta_str} across the analysis window"
        if abs(revenue_delta) >= 1
        else "Revenue is roughly flat across the analysis window"
    )
    parts.append(f"{trend_phrase}, totaling ${total_revenue:,.0f} across {len(df):,} rows.")

    if product_col:
        product_revenue = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False)
        if not product_revenue.empty:
            top_product = product_revenue.index[0]
            top_revenue = float(product_revenue.iloc[0])
            share = (top_revenue / total_revenue * 100) if total_revenue else 0
            parts.append(
                f"Top product by revenue is {top_product} at ${top_revenue:,.0f}, "
                f"contributing {share:.1f}% of total revenue."
            )
        if len(product_revenue) > 1:
            bottom_product = product_revenue.index[-1]
            bottom_revenue = float(product_revenue.iloc[-1])
            parts.append(
                f"Weakest product by revenue is {bottom_product} at ${bottom_revenue:,.0f}, "
                "so it is the first candidate to review."
            )

    if product_col and units_col:
        df[units_col] = _numeric_series(df[units_col]).fillna(0)
        product_units = df.groupby(product_col)[units_col].sum().sort_values(ascending=False)
        if not product_units.empty:
            parts.append(
                f"Highest unit velocity comes from {product_units.index[0]} "
                f"with {float(product_units.iloc[0]):,.0f} units sold."
            )

    if date_col:
        dated = df.copy()
        dated["_summary_date"] = _datetime_series(dated[date_col])
        dated = dated.dropna(subset=["_summary_date"])
        if not dated.empty:
            monthly = dated.set_index("_summary_date").resample("ME")[revenue_col].sum()
            if not monthly.empty:
                parts.append(
                    f"Best month was {monthly.idxmax().strftime('%B %Y')} "
                    f"at ${float(monthly.max()):,.0f}."
                )

    if channel_col:
        channel_revenue = df.groupby(channel_col)[revenue_col].sum().sort_values(ascending=False)
        if not channel_revenue.empty:
            parts.append(f"Strongest channel is {channel_revenue.index[0]} at ${float(channel_revenue.iloc[0]):,.0f}.")

    if category_col:
        category_revenue = df.groupby(category_col)[revenue_col].sum().sort_values(ascending=False)
        if not category_revenue.empty:
            parts.append(f"Leading category is {category_revenue.index[0]} at ${float(category_revenue.iloc[0]):,.0f}.")

    if anomaly_idx is not None and anomaly_idx < len(labels):
        parts.append(
            f"An unusual movement was detected around {labels[anomaly_idx]}; "
            "investigate it before reallocating budget."
        )

    return " ".join(parts[:7])


# ────────────────────────────────────────────────────────────────────────────
# Session data loader
# ────────────────────────────────────────────────────────────────────────────
def _load_combined_df(session_id: str):
    """Returns (combined_df, revenue_col, date_col, product_col, category_col, channel_col, units_col) or Nones."""
    ensure_session_loaded(session_id)
    with store_lock:
        session_files = dict(session_store.get(session_id, {}))

    dfs = [fdata["df"] for fdata in session_files.values() if fdata.get("df") is not None and not fdata["df"].empty]
    if not dfs:
        return None, None, None, None, None, None, None

    combined = pd.concat(dfs, ignore_index=True)
    revenue_col = _find_revenue_col(combined)
    date_col = _find_date_col(combined)
    product_col = _find_product_col(combined)
    category_col = _find_category_col(combined)
    channel_col = _find_channel_col(combined)
    units_col = _find_units_col(combined)
    return combined, revenue_col, date_col, product_col, category_col, channel_col, units_col


# ────────────────────────────────────────────────────────────────────────────
# Public API: Dashboard
# ────────────────────────────────────────────────────────────────────────────
def _compute_dashboard_with_analysis_agent(session_id: str, combined: pd.DataFrame) -> Optional[DashboardResponse]:
    """Uses the LLM coding agent to derive dashboard metrics from the actual uploaded schema."""
    if not settings.gemini_api_key:
        return None

    try:
        import google.generativeai as genai
        from app.services.sandbox import run_analysis_code

        context = get_analysis_context(session_id, query="dashboard revenue trend product velocity channel category")
        compact_context = {
            "files": context.get("files", []),
            "elastic_docs": [
                {
                    "doc_type": doc.get("doc_type"),
                    "source_file": doc.get("source_file"),
                    "row_number": doc.get("row_number"),
                    "page_number": doc.get("page_number"),
                    "content": str(doc.get("content", ""))[:700],
                }
                for doc in context.get("elastic_docs", [])[:8]
            ],
        }

        sample = combined.head(8)
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""You are the dashboard analysis coding agent for a BI app.
Write Python pandas code that computes a dashboard JSON dict from the dataframe variable `df`.
Return only executable Python code, no markdown.

Session context and Elastic retrieval snippets:
{json.dumps(compact_context, default=str)[:7000]}

DataFrame columns:
{json.dumps([str(col) for col in combined.columns.tolist()])}

Sample rows:
{sample.where(pd.notna(sample), None).to_string(index=False)}

The code must assign `result` to this exact shape:
{{
  "kpi": {{"total_revenue": null, "revenue_delta_pct": null, "top_product": null, "top_product_revenue": null, "top_product_category": null, "at_risk_skus": 0, "anomaly_count": 0, "anomaly_description": null}},
  "summary": "short business summary specific to this dataset",
  "revenue_trend": {{"labels": [], "values": [], "anomaly_index": null}},
  "products": [{{"name": "product", "category": null, "channel": null, "revenue": 0, "velocity": null, "growth": null, "velocity_decline_pct": null, "risk": 0, "level": "low", "action": "Monitor", "rationale": "why"}}],
  "channels": [{{"label": "Online", "value": 0}}],
  "categories": [{{"label": "Hardware", "value": 0}}],
  "suggested_questions": ["question"]
}}

Rules:
- Do not hardcode demo column names. Infer columns from names, dtypes, sample values, and context.
- Treat revenue/sales/amount/total/gmv/net/gross/value as revenue candidates, but avoid id, postal, discount, quantity, qty, unit, count.
- Treat date/order date/month/period/time columns as time candidates. Parse strings, mixed formats, and Excel serial dates when present.
- Treat product/item/sku/product name/item name/title/description as product candidates.
- Never treat customer, consumer segment, class, city, state, region, country, postal code, ship mode, market, or order/customer names as products.
- Treat category/sub-category/department as category candidates. Do not use segment/class/customer type as category unless the column is explicitly named category.
- Treat channel/source/platform/store/marketplace/ship mode as channel candidates. Do not use city/state/region/class/segment as channel.
- Treat units/quantity/qty/sold/volume/orders as velocity candidates. If no units column exists and a true product column exists, use row count per product as velocity.
- If no true product column exists, return products=[] instead of using geography/customer/segment fields.
- Summary must begin by identifying what business/domain the uploaded data is about, using real product/category examples from the data.
- Revenue trend values must be monthly revenue in thousands, e.g. 12500 becomes 12.5.
- If a field cannot be inferred, return an empty list/null for only that field, not the whole dashboard.
- Use only pandas, numpy, math, statistics. Do not import files, network clients, or pydantic.
"""

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.15, "max_output_tokens": 3200},
        )
        code = _extract_python_code(response.text or "")
        if not code:
            return None
        run = run_analysis_code(code, combined)
        if not run["ok"]:
            logger.warning("Dashboard analysis agent failed: %s", run["error"])
            return None
        dashboard = DashboardResponse(**run["result"])
        if not _dashboard_agent_dimensions_valid(combined, dashboard):
            logger.warning("Dashboard analysis agent returned invalid dimension roles; using guarded fallback.")
            return None
        product_col = _find_product_col(combined)
        category_col = _find_category_col(combined)
        channel_col = _find_channel_col(combined)
        dashboard.summary = _ensure_business_context_in_summary(
            combined, dashboard.summary, product_col, category_col, channel_col
        )
        return dashboard
    except Exception as exc:
        logger.warning("Dashboard analysis agent unavailable: %s", exc)
        return None


def _dashboard_agent_dimensions_valid(df: pd.DataFrame, dashboard: DashboardResponse) -> bool:
    product_col = _find_product_col(df)
    category_col = _find_category_col(df)
    channel_col = _find_channel_col(df)

    def _values(col: Optional[str]) -> set[str]:
        if not col or col not in df.columns:
            return set()
        return {str(value).strip().lower() for value in df[col].dropna().unique()}

    product_values = _values(product_col)
    category_values = _values(category_col)
    channel_values = _values(channel_col)

    if dashboard.products and not product_col:
        return False
    if dashboard.products and product_values:
        sampled_products = [str(product.name).strip().lower() for product in dashboard.products[:8]]
        if any(name and name not in product_values for name in sampled_products):
            return False

    top_product = (dashboard.kpi.top_product or "").strip().lower()
    if top_product and product_values and top_product not in product_values:
        return False
    if top_product and not product_col:
        return False

    if dashboard.categories and not category_col:
        return False
    if dashboard.categories and category_values:
        sampled_categories = [str(point.label).strip().lower() for point in dashboard.categories[:8]]
        if any(label and label not in category_values for label in sampled_categories):
            return False

    if dashboard.channels and not channel_col:
        return False
    if dashboard.channels and channel_values:
        sampled_channels = [str(point.label).strip().lower() for point in dashboard.channels[:8]]
        if any(label and label not in channel_values for label in sampled_channels):
            return False

    return True


def _fallback_revenue_trend_chart_code(df: pd.DataFrame) -> Optional[str]:
    revenue_col = _find_revenue_col(df)
    date_col = _find_date_col(df)
    if not revenue_col or not date_col:
        return None
    return f"""import pandas as pd
import plotly.express as px

date_col = {json.dumps(date_col)}
revenue_col = {json.dumps(revenue_col)}
plot_df = df.copy()
if not pd.api.types.is_numeric_dtype(plot_df[revenue_col]):
    plot_df[revenue_col] = (
        plot_df[revenue_col].astype(str)
        .str.replace(r"[\\$,]", "", regex=True)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
plot_df[revenue_col] = pd.to_numeric(plot_df[revenue_col], errors="coerce").fillna(0)
if pd.api.types.is_numeric_dtype(plot_df[date_col]):
    numeric_dates = pd.to_numeric(plot_df[date_col], errors="coerce")
    if numeric_dates.dropna().between(20000, 80000).mean() > 0.7:
        plot_df["_trend_date"] = pd.to_datetime(numeric_dates, unit="D", origin="1899-12-30", errors="coerce")
    else:
        plot_df["_trend_date"] = pd.to_datetime(plot_df[date_col], errors="coerce")
else:
    plot_df["_trend_date"] = pd.to_datetime(plot_df[date_col].astype(str), errors="coerce", format="mixed")
monthly = (
    plot_df.dropna(subset=["_trend_date"])
    .set_index("_trend_date")
    .resample("ME")[revenue_col]
    .sum()
    .reset_index()
)
monthly["label"] = monthly["_trend_date"].dt.strftime("%b '%y")
fig = px.line(monthly, x="label", y=revenue_col, markers=True, title="Revenue Trend")
fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=42, b=32), xaxis_title="", yaxis_title="Revenue")
summary = f"Created a monthly revenue trend chart with {{len(monthly)}} data points using {{revenue_col}} by {{date_col}}."
"""


def _generate_revenue_trend_chart(session_id: str, combined: pd.DataFrame) -> Optional[Dict[str, Any]]:
    try:
        from app.services.sandbox import run_chart_code

        code = ""
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai

                context = get_analysis_context(session_id, query="monthly revenue trend chart")
                compact_context = {
                    "files": context.get("files", []),
                    "elastic_docs": [
                        {
                            "source_file": doc.get("source_file"),
                            "row_number": doc.get("row_number"),
                            "content": str(doc.get("content", ""))[:500],
                        }
                        for doc in context.get("elastic_docs", [])[:6]
                    ],
                }
                sample = combined.head(8)
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = f"""You are a chart coding agent for a BI dashboard.
Write only executable Python code. The dataframe variable is `df`.
Create a Plotly Figure assigned to `fig` for monthly revenue trend from the uploaded data.
Also assign a one-sentence `summary`.

Context:
{json.dumps(compact_context, default=str)[:5000]}

Columns:
{json.dumps([str(col) for col in combined.columns.tolist()])}

Sample rows:
{sample.where(pd.notna(sample), None).to_string(index=False)}

Rules:
- Infer the revenue metric from names like revenue, sales, amount, total, gmv, net, gross, value.
- Avoid id, postal, discount, quantity, qty, unit, count for revenue.
- Infer the date column from date, order date, month, period, timestamp, time.
- Do not use product/category/channel fields for this chart. Only date and revenue are required.
- Parse mixed string dates and Excel serial dates if needed.
- Aggregate by month. Use Plotly line chart with markers.
- If no date or revenue column exists, create an empty Plotly figure with a clear title.
- Use only pandas, numpy, plotly, math, statistics.
"""
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1, "max_output_tokens": 2200},
                )
                code = _extract_python_code(response.text or "")
            except Exception as exc:
                logger.warning("Revenue chart agent generation failed: %s", exc)

        if not code:
            code = _fallback_revenue_trend_chart_code(combined) or ""
        if not code:
            return None

        result = run_chart_code(code, combined)
        if not result["ok"]:
            fallback = _fallback_revenue_trend_chart_code(combined)
            if fallback and fallback != code:
                result = run_chart_code(fallback, combined)
        if not result["ok"]:
            logger.warning("Revenue trend chart failed: %s", result["error"])
            return None
        return {"chart": result["chart"], "summary": result["summary"]}
    except Exception as exc:
        logger.warning("Revenue trend chart unavailable: %s", exc)
        return None


def _dimension_candidates(df: pd.DataFrame) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    blocked = {"id", "rowid", "postalcode", "zipcode"}
    for col in df.columns:
        clean = _clean_name(col)
        if any(bad in clean for bad in blocked):
            continue
        if _parseable_date_ratio(df[col]) > 0.6 or _parseable_numeric_ratio(df[col]) > 0.8:
            continue
        values = df[col].dropna().astype(str)
        unique = values.nunique()
        if unique <= 1 or unique > min(80, max(len(df) // 2, 10)):
            continue
        candidates.append(
            {
                "column": str(col),
                "unique_count": int(unique),
                "sample_values": values.drop_duplicates().head(8).tolist(),
            }
        )
    return candidates


def _metric_candidates(df: pd.DataFrame) -> List[str]:
    metrics: List[str] = []
    for col in df.columns:
        clean = _clean_name(col)
        if any(bad in clean for bad in ["id", "postal", "zip"]):
            continue
        if _parseable_numeric_ratio(df[col]) >= 0.6:
            metrics.append(str(col))
    return metrics


def _fallback_dashboard_chart_specs(df: pd.DataFrame) -> List[Dict[str, Any]]:
    revenue_col = _find_revenue_col(df)
    if not revenue_col:
        return []

    specs: List[Dict[str, Any]] = []
    for col in [_find_product_col(df), _find_category_col(df), _find_channel_col(df)]:
        if col and col not in [spec.get("dimension_col") for spec in specs]:
            specs.append(
                {
                    "title": f"{col} performance",
                    "subtitle": f"{revenue_col} by {col}",
                    "chart_type": "bar",
                    "metric_col": revenue_col,
                    "dimension_col": col,
                    "aggregation": "sum",
                }
            )

    if not specs:
        for candidate in _dimension_candidates(df)[:4]:
            col = candidate["column"]
            specs.append(
                {
                    "title": f"{col} performance",
                    "subtitle": f"{revenue_col} by {col}",
                    "chart_type": "bar",
                    "metric_col": revenue_col,
                    "dimension_col": col,
                    "aggregation": "sum",
                }
            )
    return specs[:4]


def _dashboard_chart_specs_from_agent(session_id: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
    fallback = _fallback_dashboard_chart_specs(df)
    if not settings.gemini_api_key:
        return fallback

    try:
        import google.generativeai as genai

        context = get_analysis_context(session_id, query="choose dashboard charts for uploaded data")
        profile = {
            "files": context.get("files", []),
            "metrics": _metric_candidates(df),
            "dimensions": _dimension_candidates(df),
            "date_column": _find_date_col(df),
            "revenue_column": _find_revenue_col(df),
        }
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""You are a BI dashboard orchestrator.
Choose the most relevant landing-page charts for this uploaded dataset.
Return only valid JSON: an array of 2 to 4 chart specs.

Dataset profile:
{json.dumps(profile, default=str)[:8000]}

Each spec must have:
title, subtitle, chart_type, metric_col, dimension_col, aggregation

Rules:
- chart_type should be bar, pie, or line.
- Use only columns present in the profile.
- Pick dimensions that are meaningful for this dataset, not fixed product/channel/category slots.
- If there is no product column, do not create a product chart. Use geography, segment, ship mode, class, region, customer type, or another relevant dimension when useful.
- Prefer revenue/sales/amount/profit metrics for business charts.
- Avoid IDs and postal codes.
- Titles should match the chosen dimension, e.g. "Sales by City", "Revenue by Segment", "Profit by Ship Mode".
"""
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 1600},
        )
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.I | re.M).strip()
        specs = json.loads(raw)
        if not isinstance(specs, list):
            return fallback
        allowed_cols = {str(col) for col in df.columns}
        cleaned: List[Dict[str, Any]] = []
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            metric_col = spec.get("metric_col")
            dimension_col = spec.get("dimension_col")
            if metric_col not in allowed_cols or dimension_col not in allowed_cols:
                continue
            cleaned.append(
                {
                    "title": str(spec.get("title") or f"{metric_col} by {dimension_col}")[:80],
                    "subtitle": str(spec.get("subtitle") or f"{metric_col} by {dimension_col}")[:120],
                    "chart_type": str(spec.get("chart_type") or "bar").lower(),
                    "metric_col": metric_col,
                    "dimension_col": dimension_col,
                    "aggregation": str(spec.get("aggregation") or "sum").lower(),
                }
            )
        return cleaned[:4] or fallback
    except Exception as exc:
        logger.warning("Dashboard chart orchestrator unavailable: %s", exc)
        return fallback


def _chart_card_code(spec: Dict[str, Any]) -> str:
    chart_type = spec.get("chart_type") if spec.get("chart_type") in {"bar", "pie", "line"} else "bar"
    metric_col = str(spec["metric_col"])
    dimension_col = str(spec["dimension_col"])
    aggregation = spec.get("aggregation") if spec.get("aggregation") in {"sum", "mean", "count"} else "sum"
    title = str(spec.get("title") or f"{metric_col} by {dimension_col}")
    if aggregation == "count":
        agg_expr = "grouped = plot_df.groupby(dimension_col).size().reset_index(name='value')"
    else:
        agg_expr = f"grouped = plot_df.groupby(dimension_col)[metric_col].{aggregation}().reset_index(name='value')"
    plot_call = {
        "pie": "fig = px.pie(grouped, names=dimension_col, values='value', title=title)",
        "line": "fig = px.line(grouped, x=dimension_col, y='value', markers=True, title=title)",
        "bar": "fig = px.bar(grouped, x=dimension_col, y='value', title=title)",
    }[chart_type]
    return f"""import pandas as pd
import plotly.express as px

metric_col = {json.dumps(metric_col)}
dimension_col = {json.dumps(dimension_col)}
title = {json.dumps(title)}
plot_df = df.copy()
if {json.dumps(aggregation)} != "count":
    if not pd.api.types.is_numeric_dtype(plot_df[metric_col]):
        plot_df[metric_col] = (
            plot_df[metric_col].astype(str)
            .str.replace(r"[\\$,]", "", regex=True)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
    plot_df[metric_col] = pd.to_numeric(plot_df[metric_col], errors="coerce").fillna(0)
{agg_expr}
grouped = grouped.dropna(subset=[dimension_col]).sort_values("value", ascending=False).head(12)
{plot_call}
fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=42, b=48), xaxis_title="", yaxis_title="")
summary = f"Created {{title}} with {{len(grouped)}} groups."
"""


def _generate_agent_dashboard_charts(session_id: str, combined: pd.DataFrame) -> List[Dict[str, Any]]:
    try:
        from app.services.sandbox import run_chart_code

        cards: List[Dict[str, Any]] = []
        for spec in _dashboard_chart_specs_from_agent(session_id, combined):
            try:
                result = run_chart_code(_chart_card_code(spec), combined)
            except Exception as exc:
                logger.warning("Dashboard chart spec failed: %s", exc)
                continue
            if not result.get("ok"):
                logger.warning("Dashboard chart card failed: %s", result.get("error"))
                continue
            cards.append(
                {
                    "title": spec.get("title"),
                    "subtitle": spec.get("subtitle"),
                    "type": spec.get("chart_type"),
                    "metric": spec.get("metric_col"),
                    "dimension": spec.get("dimension_col"),
                    "chart": result.get("chart"),
                    "summary": result.get("summary", ""),
                }
            )
        return cards
    except Exception as exc:
        logger.warning("Agent dashboard charts unavailable: %s", exc)
        return []


def _attach_dashboard_charts(session_id: str, combined: pd.DataFrame, dashboard: DashboardResponse) -> DashboardResponse:
    charts = dict(dashboard.charts or {})
    revenue_chart = _generate_revenue_trend_chart(session_id, combined)
    if revenue_chart:
        charts["revenue_trend"] = revenue_chart
    dashboard.charts = charts or None
    dashboard.agent_charts = _generate_agent_dashboard_charts(session_id, combined)
    return dashboard


def compute_dashboard(session_id: str) -> DashboardResponse:
    ensure_session_loaded(session_id)
    with store_lock:
        session_files = dict(session_store.get(session_id, {}))

    dfs = []
    for fid, fdata in session_files.items():
        df = fdata.get("df")
        if df is not None and not df.empty:
            dfs.append(df)

    if not dfs:
        return DashboardResponse(
            kpi=KPIData(),
            summary="Upload a CSV or Excel file to see your business analytics here.",
            revenue_trend=RevenueTrendResponse(labels=[], values=[]),
            products=[],
            channels=[],
            categories=[],
            suggested_questions=[
                "What was my best-performing month?",
                "Which product has the highest sales velocity?",
                "Are there any at-risk products?",
            ]
        )

    combined = pd.concat(dfs, ignore_index=True)

    agent_dashboard = _compute_dashboard_with_analysis_agent(session_id, combined.copy())
    if agent_dashboard is not None:
        return _attach_dashboard_charts(session_id, combined.copy(), agent_dashboard)

    revenue_col = _find_revenue_col(combined)
    date_col = _find_date_col(combined)
    product_col = _find_product_col(combined)
    category_col = _find_category_col(combined)
    channel_col = _find_channel_col(combined)
    units_col = _find_units_col(combined)

    if not revenue_col:
        return DashboardResponse(
            kpi=KPIData(),
            summary="No revenue column detected. Make sure your file has a 'revenue' or 'sales' column.",
            revenue_trend=RevenueTrendResponse(labels=[], values=[]),
            products=[],
            channels=[],
            categories=[],
            suggested_questions=["What columns are in my data?"]
        )

    combined[revenue_col] = _numeric_series(combined[revenue_col]).fillna(0)
    total_revenue = float(combined[revenue_col].sum())

    # ── Revenue trend ──────────────────────────────────────────────────────
    labels: List[str] = []
    values: List[float] = []
    anomaly_idx: Optional[int] = None

    if date_col:
        try:
            combined["_date"] = _datetime_series(combined[date_col])
            trend_df = combined.dropna(subset=["_date"])
            monthly = (
                trend_df.set_index("_date")
                .resample("ME")[revenue_col]
                .sum()
                .reset_index()
            )
            monthly.columns = ["date", "revenue"]
            labels = monthly["date"].dt.strftime("%b '%y").tolist()
            values = [round(float(v) / 1000, 1) for v in monthly["revenue"].tolist()]
            anomaly_idx = _detect_anomaly(values)
        except Exception as exc:
            logger.warning("Revenue trend failed: %s", exc)

    # ── Revenue delta ──────────────────────────────────────────────────────
    revenue_delta = 0.0
    if len(values) >= 4:
        mid = len(values) // 2
        first_half = sum(values[:mid]) or 1
        second_half = sum(values[mid:])
        revenue_delta = round((second_half - first_half) / first_half * 100, 1)

    # ── Products with temporal risk scoring ────────────────────────────────
    products: List[ProductRow] = []
    if product_col:
        velocity_metric_col = units_col or "_row_count_metric"
        agg: dict = {revenue_col: "sum"}
        if units_col:
            agg[units_col] = "sum"
        else:
            combined[velocity_metric_col] = 1
            agg[velocity_metric_col] = "sum"

        group_cols = [product_col]
        if category_col:
            group_cols.append(category_col)
        if channel_col:
            group_cols.append(channel_col)

        prod_df = combined.groupby(group_cols).agg(agg).reset_index()
        prod_df = prod_df.sort_values(revenue_col, ascending=False)

        for _, row in prod_df.iterrows():
            product_name = str(row[product_col])
            rev = float(row[revenue_col])
            velocity = float(row[velocity_metric_col]) if velocity_metric_col in row else None

            level, action, risk, velocity_decline_pct, rationale, _bd = _compute_product_risk(
                product_name=product_name,
                df=combined,
                product_col=product_col,
                metric_col=revenue_col,
                date_col=date_col,
                category_col=category_col,
            )

            products.append(ProductRow(
                name=product_name,
                category=str(row[category_col]) if category_col and category_col in row else None,
                channel=str(row[channel_col]) if channel_col and channel_col in row else None,
                revenue=round(rev, 2),
                velocity=round(velocity, 1) if velocity is not None else None,
                growth=None,  # no longer using cross-sectional growth proxy
                velocity_decline_pct=velocity_decline_pct,
                risk=risk,
                level=level,
                action=action,
                rationale=rationale,
            ))

    # ── KPI ────────────────────────────────────────────────────────────────
    top_product = products[0] if products else None
    at_risk = sum(1 for p in products if p.level == "high")

    kpi = KPIData(
        total_revenue=round(total_revenue, 2),
        revenue_delta_pct=revenue_delta,
        top_product=top_product.name if top_product else None,
        top_product_revenue=top_product.revenue if top_product else None,
        top_product_category=top_product.category if top_product else None,
        at_risk_skus=at_risk,
        anomaly_count=1 if anomaly_idx is not None else 0,
        anomaly_description=f"{labels[anomaly_idx]} · unusual movement detected" if anomaly_idx is not None and labels else None,
    )

    # ── Channels & categories ──────────────────────────────────────────────
    channels: List[ChartPoint] = []
    if channel_col:
        ch = combined.groupby(channel_col)[revenue_col].sum().sort_values(ascending=False)
        channels = [ChartPoint(label=str(k), value=round(float(v), 2)) for k, v in ch.items()]

    categories: List[ChartPoint] = []
    if category_col:
        cat = combined.groupby(category_col)[revenue_col].sum().sort_values(ascending=False)
        categories = [ChartPoint(label=str(k), value=round(float(v), 2)) for k, v in cat.items()]

    summary = _generate_business_summary(
        combined, revenue_col, product_col, total_revenue, revenue_delta,
        anomaly_idx, labels, date_col=date_col, category_col=category_col,
        channel_col=channel_col, units_col=units_col,
    )

    dashboard = DashboardResponse(
        kpi=kpi,
        summary=summary,
        revenue_trend=RevenueTrendResponse(labels=labels, values=values, anomaly_index=anomaly_idx),
        products=products,
        channels=channels,
        categories=categories,
        suggested_questions=[
            "What was my best-performing month?",
            "Which product has the highest sales velocity?",
            "Are there any at-risk products?",
            "What does my channel mix look like?",
        ],
    )
    return _attach_dashboard_charts(session_id, combined.copy(), dashboard)


# ────────────────────────────────────────────────────────────────────────────
# Public API: Power Mode — Obsolescence Radar
# ────────────────────────────────────────────────────────────────────────────
def compute_obsolescence(session_id: str) -> ObsolescenceResponse:
    combined, revenue_col, date_col, product_col, category_col, channel_col, units_col = _load_combined_df(session_id)

    if combined is None or not revenue_col or not product_col:
        return ObsolescenceResponse(items=[])

    combined[revenue_col] = _numeric_series(combined[revenue_col]).fillna(0)
    metric_col = units_col if units_col else revenue_col

    products = combined[product_col].unique()
    items: List[ObsolescenceRow] = []

    for product_name in products:
        product_name = str(product_name)
        level, action, risk, velocity_decline_pct, rationale, bd = _compute_product_risk(
            product_name=product_name,
            df=combined,
            product_col=product_col,
            metric_col=metric_col,
            date_col=date_col,
            category_col=category_col,
        )

        # Get category for display + signals
        category_value = None
        if category_col and category_col in combined.columns:
            mode = combined[combined[product_col] == product_name][category_col].mode()
            if not mode.empty:
                category_value = str(mode.iloc[0])

        category_trend_score = _compute_category_trend(
            combined, category_value, category_col, metric_col, date_col
        )
        velocity_decline = bd["velocity_score"] / 40.0  # reverse-compute float from score

        signals = _get_product_signals(
            product_name=product_name,
            velocity_decline_pct=velocity_decline_pct,
            velocity_decline=velocity_decline,
            category_trend_score=category_trend_score,
            category_value=category_value,
            risk=risk,
            product_df=combined[combined[product_col] == product_name],
            metric_col=metric_col,
            date_col=date_col,
        )

        trend = _get_product_trend(
            df=combined,
            product_name=product_name,
            product_col=product_col,
            metric_col=metric_col,
            date_col=date_col,
        )

        items.append(ObsolescenceRow(
            name=product_name,
            category=category_value,
            risk=risk,
            level=level,
            action=action,
            velocity_decline_pct=velocity_decline_pct,
            rationale=rationale,
            breakdown=RiskBreakdown(**bd),
            trend=[TrendPoint(**pt) for pt in trend],
            signals=signals,
        ))

    # Sort by risk score descending (highest risk first)
    items.sort(key=lambda x: x.risk, reverse=True)
    return ObsolescenceResponse(items=items)


# ────────────────────────────────────────────────────────────────────────────
# Public API: Power Mode — Budget Reallocation Recommender
# ────────────────────────────────────────────────────────────────────────────
def compute_budget_recommendations(session_id: str) -> BudgetResponse:
    combined, revenue_col, date_col, product_col, category_col, channel_col, units_col = _load_combined_df(session_id)

    if combined is None or not revenue_col or not product_col:
        return BudgetResponse(increase=[], maintain=[], reduce=[])

    combined[revenue_col] = _numeric_series(combined[revenue_col]).fillna(0)

    # Compute ROI signal per product: revenue CAGR proxy (second half vs first half growth)
    products = combined[product_col].unique()
    scored: list = []

    for product_name in products:
        product_name = str(product_name)
        pdf = combined[combined[product_col] == product_name].copy()
        pdf[revenue_col] = _numeric_series(pdf[revenue_col]).fillna(0)

        velocity_decline = _compute_velocity_decline(pdf, revenue_col, date_col)
        velocity_decline_pct = round(velocity_decline * 100, 1)

        # Revenue total and per-unit metric
        total_rev = float(pdf[revenue_col].sum())
        avg_rev_per_row = total_rev / max(len(pdf), 1)

        # ROI score: higher growth rate = higher score
        if velocity_decline < 0:
            growth_rate = abs(velocity_decline)  # negative decline = growth
        else:
            growth_rate = -velocity_decline

        scored.append({
            "product": product_name,
            "total_rev": total_rev,
            "velocity_decline_pct": velocity_decline_pct,
            "growth_rate": growth_rate,
        })

    # Sort by growth rate descending
    scored.sort(key=lambda x: x["growth_rate"], reverse=True)

    def _confidence(rank: int, total: int) -> str:
        pct = rank / max(total, 1)
        if pct <= 0.25:
            return "high"
        if pct <= 0.6:
            return "medium"
        return "low"

    def _budget_rationale(product: str, velocity_decline_pct: float, bucket: str) -> str:
        if bucket == "increase":
            if velocity_decline_pct <= 0:
                return (
                    f"{product} shows positive sales momentum with no velocity decline — "
                    "increasing budget here is likely to compound returns."
                )
            return (
                f"{product} has the strongest ROI signal in your dataset with a "
                f"modest {velocity_decline_pct:.0f}% recent dip — worth sustaining spend to defend position."
            )
        if bucket == "maintain":
            return (
                f"{product} is performing near the session average. "
                f"Current allocation appears appropriate; monitor for trend changes."
            )
        # reduce
        return (
            f"{product} shows a {velocity_decline_pct:.0f}% decline in sales velocity — "
            "reallocating budget to higher-performing SKUs will improve overall ROI."
        )

    n = len(scored)
    top_n = max(1, min(3, n // 3 + (1 if n % 3 > 0 else 0)))
    bottom_n = max(1, min(3, n // 3))
    mid_start = top_n
    mid_end = n - bottom_n

    increase_items: List[BudgetItem] = []
    for i, s in enumerate(scored[:top_n]):
        increase_items.append(BudgetItem(
            product=s["product"],
            confidence=_confidence(i, n),
            rationale=_budget_rationale(s["product"], s["velocity_decline_pct"], "increase"),
        ))

    maintain_items: List[BudgetItem] = []
    for i, s in enumerate(scored[mid_start:mid_end]):
        maintain_items.append(BudgetItem(
            product=s["product"],
            confidence=_confidence(mid_start + i, n),
            rationale=_budget_rationale(s["product"], s["velocity_decline_pct"], "maintain"),
        ))

    reduce_items: List[BudgetItem] = []
    for i, s in enumerate(scored[mid_end:]):
        reduce_items.append(BudgetItem(
            product=s["product"],
            confidence=_confidence(mid_end + i, n),
            rationale=_budget_rationale(s["product"], s["velocity_decline_pct"], "reduce"),
        ))

    return BudgetResponse(
        increase=increase_items,
        maintain=maintain_items,
        reduce=reduce_items,
    )


# ────────────────────────────────────────────────────────────────────────────
# Public API: Power Mode — Monte Carlo Simulation Agent
# ────────────────────────────────────────────────────────────────────────────
def compute_monte_carlo_simulation(
    session_id: str,
    product: str,
    budget_change_pct: float = 0,
    horizon_days: int = 90,
    simulations: int = 5000,
) -> MonteCarloResponse:
    combined, revenue_col, date_col, product_col, category_col, channel_col, units_col = _load_combined_df(session_id)

    if combined is None or not revenue_col or not product_col:
        raise ValueError("Upload sales data with product and revenue columns before running a simulation.")

    horizon_days = int(max(7, min(horizon_days, 365)))
    simulations = int(max(500, min(simulations, 20000)))
    product = str(product).strip()
    if not product:
        raise ValueError("Select a product before running a simulation.")

    working = combined.copy()
    working[revenue_col] = _numeric_series(working[revenue_col]).fillna(0)
    product_values = working[product_col].dropna().astype(str)
    match = next((value for value in product_values.unique() if value.lower() == product.lower()), None)
    if match is None:
        match = next((value for value in product_values.unique() if product.lower() in value.lower()), None)
    if match is None:
        available = ", ".join(product_values.unique()[:5])
        raise ValueError(f"Product '{product}' was not found in the uploaded data. Available examples: {available}")

    product_df = working[working[product_col].astype(str) == str(match)].copy()
    if product_df.empty:
        raise ValueError(f"No rows found for product '{match}'.")

    if date_col:
        product_df["_mc_date"] = _datetime_series(product_df[date_col])
        daily = (
            product_df.dropna(subset=["_mc_date"])
            .set_index("_mc_date")
            .resample("D")[revenue_col]
            .sum()
        )
        daily = daily[daily.index <= daily.index.max()]
        observations = daily[daily > 0]
    else:
        observations = product_df[revenue_col]

    observations = pd.to_numeric(observations, errors="coerce").dropna()
    observations = observations[observations >= 0]
    if observations.empty:
        raise ValueError(f"No numeric revenue observations found for product '{match}'.")

    mean_daily = float(observations.mean())
    std_daily = float(observations.std(ddof=1)) if len(observations) > 1 else max(mean_daily * 0.2, 1.0)
    std_daily = max(std_daily, mean_daily * 0.05, 1.0)
    baseline_revenue = mean_daily * horizon_days

    elasticity = 0.65
    budget_multiplier = max(0.05, 1 + (float(budget_change_pct) / 100.0 * elasticity))
    simulated_daily = np.random.default_rng(
        abs(hash((session_id, str(match), horizon_days, round(float(budget_change_pct), 2)))) % (2**32)
    ).normal(
        loc=mean_daily * budget_multiplier,
        scale=std_daily,
        size=(simulations, horizon_days),
    )
    simulated_daily = np.clip(simulated_daily, 0, None)
    totals = simulated_daily.sum(axis=1)

    expected = float(np.mean(totals))
    p10 = float(np.percentile(totals, 10))
    p50 = float(np.percentile(totals, 50))
    p90 = float(np.percentile(totals, 90))
    probability_above = float(np.mean(totals > baseline_revenue) * 100)
    probability_loss = float(np.mean(totals < baseline_revenue) * 100)
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    distribution = [
        MonteCarloPoint(percentile=pct, revenue=round(float(np.percentile(totals, pct)), 2))
        for pct in percentiles
    ]

    assumptions = [
        f"Monte Carlo agent used {len(observations):,} historical revenue observations for {match}.",
        f"Budget elasticity is modeled at {elasticity:.2f}, so a {budget_change_pct:+.0f}% budget change shifts expected demand by {(budget_multiplier - 1) * 100:+.1f}%.",
        f"The simulation samples daily revenue over {horizon_days} days using the product's observed mean and volatility.",
    ]
    summary = (
        f"Monte Carlo simulation for {match} projects {expected:,.0f} revenue over {horizon_days} days "
        f"with a median of {p50:,.0f} and an 80% range from {p10:,.0f} to {p90:,.0f}. "
        f"Probability of beating the historical baseline is {probability_above:.1f}%."
    )

    return MonteCarloResponse(
        product=str(match),
        horizon_days=horizon_days,
        simulations=simulations,
        budget_change_pct=float(budget_change_pct),
        baseline_revenue=round(baseline_revenue, 2),
        expected_revenue=round(expected, 2),
        p10_revenue=round(p10, 2),
        p50_revenue=round(p50, 2),
        p90_revenue=round(p90, 2),
        probability_above_baseline=round(probability_above, 2),
        probability_loss=round(probability_loss, 2),
        distribution=distribution,
        summary=summary,
        assumptions=assumptions,
    )
