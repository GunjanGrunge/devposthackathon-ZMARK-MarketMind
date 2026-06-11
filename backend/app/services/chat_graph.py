"""
LangGraph-backed chat orchestration for MarketMind.

The graph uses small specialist analysis nodes for statistical questions, then
optionally augments with Elastic retrieval and Gemini synthesis when configured.
It intentionally avoids sample data: every answer is derived from the current
session_store or retrieved session documents.
"""
from __future__ import annotations

import logging
import json
import re
from typing import Any, Dict, List, Optional, TypedDict

import numpy as np
import pandas as pd

from app.core.config import settings
from app.schemas.analytics import ChatMessage, Citation
from app.services.eda import ensure_session_loaded, session_store, store_lock
from app.services.analytics import (
    _compute_product_risk,
    _find_category_col,
    _find_channel_col,
    _find_date_col,
    _find_product_col,
    _find_revenue_col,
    _find_units_col,
)
from app.services.business_rules_service import get_session_business_rules

logger = logging.getLogger("chat_graph")


class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    history: List[Dict[str, str]]
    dataframes: List[Dict[str, Any]]
    data_summary: str               # text snapshot of uploaded data for Gemini context
    analysis_context: Dict[str, Any]
    route: str
    stats_results: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, str]]  # plain dicts; reconstructed as Citation objects at boundary
    followups: List[str]
    suggested_followups: List[str]
    error: Optional[str]
    scratchpad_link: Optional[str]
    clarification_form: Optional[Dict[str, Any]]
    policy_context: str             # human-readable summary of active business-rule exclusions


def _find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    keyword_text = " ".join(keywords).lower()
    if any(token in keyword_text for token in ["revenue", "sales", "amount", "total", "price", "gmv", "profit"]):
        found = _find_revenue_col(df)
        if found:
            return found
    if any(token in keyword_text for token in ["date", "time", "timestamp", "month", "period"]):
        found = _find_date_col(df)
        if found:
            return found
    if any(token in keyword_text for token in ["product", "item", "sku", "name", "title"]):
        found = _find_product_col(df)
        if found:
            return found
    if any(token in keyword_text for token in ["unit", "qty", "quantity", "sold", "volume"]):
        found = _find_units_col(df)
        if found:
            return found
    if any(token in keyword_text for token in ["channel", "source", "platform", "store", "market", "region"]):
        found = _find_channel_col(df)
        if found:
            return found
    if any(token in keyword_text for token in ["category", "cat", "group", "type", "segment", "department"]):
        found = _find_category_col(df)
        if found:
            return found
    for keyword in keywords:
        for col in df.columns:
            if keyword in col.lower():
                return col
    return None


def _load_session_dataframes(session_id: str) -> List[Dict[str, Any]]:
    ensure_session_loaded(session_id)
    with store_lock:
        session_files = dict(session_store.get(session_id, {}))

    frames: List[Dict[str, Any]] = []
    for file_id, file_data in session_files.items():
        df = file_data.get("df")
        if df is not None and not df.empty:
            frames.append(
                {
                    "file_id": file_id,
                    "filename": file_data.get("filename", "uploaded-data"),
                    "df": df.copy(),
                }
            )
    return frames


def _combined_frame(frames: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[pd.DataFrame]]:
    if not frames:
        return None, None
    filename = ", ".join(frame["filename"] for frame in frames)
    df = pd.concat([frame["df"] for frame in frames], ignore_index=True)
    return filename, df


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _build_data_summary(frames: List[Dict[str, Any]]) -> str:
    """
    Builds a concise text snapshot of all uploaded DataFrames.
    This is passed to Gemini so it can answer ANY question about the data,
    not just the ones matched by hardcoded regex agents.
    """
    if not frames:
        return ""
    parts: List[str] = []
    for frame in frames:
        df: pd.DataFrame = frame["df"].copy()
        filename: str = frame["filename"]
        lines = [f"File: {filename}  ({len(df):,} rows, {len(df.columns)} columns)"]
        lines.append(f"Columns: {', '.join(df.columns.tolist())}")

        date_col = _find_col(df, ["date", "time", "timestamp", "month", "period"])
        revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
        product_col = _find_col(df, ["product", "item", "sku", "name"])
        units_col = _find_col(df, ["units", "unit", "qty", "quantity", "sold", "volume"])
        category_col = _find_col(df, ["category", "cat", "group", "type"])
        channel_col = _find_col(df, ["channel", "source", "platform", "store"])

        if date_col:
            try:
                df["_d"] = pd.to_datetime(df[date_col], errors="coerce")
                mn, mx = df["_d"].min(), df["_d"].max()
                if not pd.isna(mn):
                    lines.append(f"Date range: {mn.strftime('%b %Y')} → {mx.strftime('%b %Y')}")
            except Exception:
                pass

        if revenue_col:
            df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
            total = df[revenue_col].sum()
            lines.append(f"Total {revenue_col}: ${total:,.0f}")

            if date_col:
                try:
                    monthly = df.dropna(subset=["_d"]).set_index("_d").resample("ME")[revenue_col].sum()
                    if not monthly.empty:
                        best_m = monthly.idxmax().strftime("%B %Y")
                        lines.append(f"Best month: {best_m} (${monthly.max():,.0f})")
                        # Also include monthly breakdown for Jan 2025 etc.
                        monthly_str = "; ".join(
                            f"{idx.strftime('%b %Y')}=${val:,.0f}"
                            for idx, val in monthly.items()
                        )
                        lines.append(f"Monthly {revenue_col}: {monthly_str}")
                except Exception:
                    pass

        if product_col and revenue_col:
            top = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False)
            plines = [f"{n}: ${v:,.0f}" for n, v in top.items()]
            lines.append(f"Revenue by product: {'; '.join(plines)}")

        if product_col and units_col:
            df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
            top_u = df.groupby(product_col)[units_col].sum().sort_values(ascending=False)
            ulines = [f"{n}: {int(v):,}" for n, v in top_u.items()]
            lines.append(f"Units sold by product: {'; '.join(ulines)}")

        if category_col and revenue_col:
            cats = df.groupby(category_col)[revenue_col].sum().sort_values(ascending=False)
            lines.append(f"Revenue by category: {'; '.join(f'{n}: ${v:,.0f}' for n, v in cats.items())}")

        if channel_col and revenue_col:
            chs = df.groupby(channel_col)[revenue_col].sum().sort_values(ascending=False)
            lines.append(f"Revenue by channel: {'; '.join(f'{n}: ${v:,.0f}' for n, v in chs.items())}")

        parts.append("\n".join(lines))
    return "\n\n".join(parts)


MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _detect_operation(query: str) -> Optional[str]:
    lc = query.lower()
    if re.search(r"\b(mean|average|avg)\b", lc):
        return "mean"
    if re.search(r"\b(median|midpoint)\b", lc):
        return "median"
    if re.search(r"\b(min|minimum|lowest|smallest)\b", lc):
        return "min"
    if re.search(r"\b(max|maximum|highest|largest)\b", lc):
        return "max"
    if re.search(r"\b(count|how many|number of)\b", lc):
        return "count"
    if re.search(r"\b(total|sum|overall|sales for|revenue for)\b", lc):
        return "sum"
    return None


def _detect_month_filter(query: str) -> Optional[Dict[str, Any]]:
    match = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b",
        query,
        re.I,
    )
    if not match:
        return None

    month_name = match.group(1).lower()
    year = int(match.group(2))
    month = MONTHS[month_name]
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthEnd(1)
    return {
        "start": start,
        "end": end,
        "label": start.strftime("%B %Y"),
    }


def _format_metric(value: float, metric_col: str, operation: str) -> str:
    if any(keyword in metric_col.lower() for keyword in ["revenue", "sales", "amount", "price", "total"]):
        return _money(value)
    if operation == "count":
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


STATISTICAL_OPERATIONS = {
    "std": {
        "label": "sample standard deviation",
        "patterns": [
            r"\bstd\b", r"\bstd\.?\s*dev\b", r"\bstandard\s+deviation\b",
            r"\bspread\b", r"\bdispersion\b", r"\bvolatility\b",
        ],
    },
    "var": {
        "label": "sample variance",
        "patterns": [r"\bvariance\b", r"\bvar\b"],
    },
    "mean": {
        "label": "mean",
        "patterns": [r"\bmean\b", r"\baverage\b", r"\bavg\b"],
    },
    "median": {
        "label": "median",
        "patterns": [r"\bmedian\b", r"\bmidpoint\b"],
    },
    "min": {
        "label": "minimum",
        "patterns": [r"\bminimum\b", r"\bmin\b", r"\blowest\b", r"\bsmallest\b"],
    },
    "max": {
        "label": "maximum",
        "patterns": [r"\bmaximum\b", r"\bmax\b", r"\bhighest\b", r"\blargest\b"],
    },
    "sum": {
        "label": "total",
        "patterns": [r"\btotal\b", r"\bsum\b", r"\boverall\b"],
    },
    "count": {
        "label": "count",
        "patterns": [r"\bcount\b", r"\bhow many\b", r"\bnumber of\b"],
    },
}


def _detect_statistical_operation(query: str) -> Optional[str]:
    for operation, spec in STATISTICAL_OPERATIONS.items():
        if any(re.search(pattern, query, re.I) for pattern in spec["patterns"]):
            return operation
    return None


def _infer_metric_column(df: pd.DataFrame, query: str) -> Optional[str]:
    query_lower = query.lower()
    candidates: List[str] = []
    if re.search(r"\bsales|revenue|amount|total|gmv|value|price|profit\b", query_lower):
        candidates.extend(["sales", "revenue", "amount", "total", "gmv", "value", "price", "profit"])
    if re.search(r"\bunits?|quantity|qty|sold|volume\b", query_lower):
        candidates.extend(["units", "unit", "quantity", "qty", "sold", "volume"])
    candidates.extend(["sales", "revenue", "amount", "total", "price", "units", "qty", "quantity", "sold"])
    return _find_col(df, candidates)


def _infer_group_column(df: pd.DataFrame, query: str) -> Optional[str]:
    query_lower = query.lower()
    group_specs = [
        (["product", "products", "item", "items", "sku", "skus"], ["product", "item", "sku", "name"]),
        (["category", "categories", "department"], ["category", "subcategory", "department"]),
        (["channel", "channels", "source", "referralsource", "referral source", "platform"], ["channel", "source", "referral", "platform", "store"]),
        (["customer", "customers", "client"], ["customer", "client"]),
        (["region", "state", "city", "country"], ["region", "state", "city", "country"]),
    ]
    if not re.search(r"\b(by|per|each|every|across|for each|grouped by|break.*down)\b", query_lower):
        return None
    for query_terms, columns in group_specs:
        if any(term in query_lower for term in query_terms):
            return _find_col(df, columns)
    return None


def _calculate_stat(values: pd.Series, operation: str) -> float:
    if operation == "std":
        return float(values.std(ddof=1))
    if operation == "var":
        return float(values.var(ddof=1))
    if operation == "mean":
        return float(values.mean())
    if operation == "median":
        return float(values.median())
    if operation == "min":
        return float(values.min())
    if operation == "max":
        return float(values.max())
    if operation == "count":
        return float(values.count())
    return float(values.sum())


def _agent_statistical_inference(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    """
    Multi-purpose statistical inference agent for descriptive/statistical questions.
    It detects the requested statistic and optional grouping dimension from the query
    instead of relying on one-off product or revenue rules.
    """
    operation = _detect_statistical_operation(query)
    if not operation:
        return None

    metric_col = _infer_metric_column(df, query)
    if not metric_col:
        return None

    scoped_df = df.copy()
    scoped_df[metric_col] = pd.to_numeric(scoped_df[metric_col], errors="coerce")
    group_col = _infer_group_column(scoped_df, query)
    label = STATISTICAL_OPERATIONS[operation]["label"]

    if group_col:
        grouped = (
            scoped_df.dropna(subset=[metric_col, group_col])
            .groupby(group_col)[metric_col]
            .agg(
                value=lambda series: _calculate_stat(series, operation),
                count="count",
                mean="mean",
            )
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["value"])
        )
        if grouped.empty:
            return None
        grouped = grouped.sort_values("value", ascending=False)
        rows = []
        for name, row in grouped.head(12).iterrows():
            formatted = _format_metric(float(row["value"]), metric_col, operation)
            rows.append(f"{name}: {formatted} (n={int(row['count'])})")
        overflow = "" if len(grouped) <= 12 else f" Showing the top 12 of {len(grouped)} groups by {label}."
        sentence = (
            f"The {label} of {metric_col} by {group_col} is: "
            f"{'; '.join(rows)}.{overflow}"
        )
        excerpt = f"{label} of {metric_col} grouped by {group_col}; {len(grouped)} groups"
        followups = [
            f"Create a chart of {label} by {group_col}",
            f"Which {group_col} has the highest variability?",
            f"Compare mean and {label} by {group_col}",
        ]
    else:
        values = scoped_df[metric_col].dropna()
        if values.empty:
            return None
        value = _calculate_stat(values, operation)
        formatted = _format_metric(value, metric_col, operation)
        sentence = (
            f"The {label} of {metric_col} across the uploaded data is {formatted}, "
            f"calculated from {len(values):,} rows."
        )
        excerpt = f"{label} of {metric_col}: {formatted} from {len(values):,} rows"
        followups = [
            f"Break this down by product",
            f"Break this down by channel",
            f"Create a distribution chart for {metric_col}",
        ]

    return {
        "agent": "statistical_inference_agent",
        "sentence": sentence,
        "citation": Citation(source=filename, ref=f"{label} {metric_col}", excerpt=excerpt),
        "followups": followups,
    }


def _agent_generic_metric(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    operation = _detect_operation(query)
    date_filter = _detect_month_filter(query)
    if not operation and date_filter:
        operation = "sum"
    if not operation:
        return None

    metric_col = _find_col(df, ["sales", "revenue", "amount", "total", "price", "units", "qty", "quantity", "sold"])
    if not metric_col:
        return None
    if not any(keyword in query.lower() for keyword in ["sales", "revenue", "amount", "total", "price", "unit", "sold", "quantity"]):
        return None

    # Skip when the user is asking for a per-product leader — _agent_product_revenue handles that
    if re.search(r"which product|product.*max|product.*highest|product.*most|max.*product|highest.*product", query, re.I):
        return None

    date_col = _find_col(df, ["date", "time", "month", "period"])
    scoped_df = df.copy()
    scope_label = "across the full uploaded dataset"

    if date_filter:
        if not date_col:
            return None
        scoped_df["_metric_date"] = pd.to_datetime(scoped_df[date_col], errors="coerce")
        scoped_df = scoped_df[
            (scoped_df["_metric_date"] >= date_filter["start"])
            & (scoped_df["_metric_date"] <= date_filter["end"])
        ]
        scope_label = f"for {date_filter['label']}"

    values = pd.to_numeric(scoped_df[metric_col], errors="coerce").dropna()
    if values.empty:
        return {
            "agent": "generic_metric_agent",
            "sentence": f"I checked {metric_col} {scope_label}, but there were no matching rows to calculate from.",
            "citation": Citation(source=filename, ref=f"{metric_col} filter", excerpt=f"No rows matched {scope_label}"),
            "followups": ["Check another month", "Show the available date range"],
        }

    if operation == "mean":
        value = float(values.mean())
        label = "mean"
    elif operation == "median":
        value = float(values.median())
        label = "median"
    elif operation == "min":
        value = float(values.min())
        label = "minimum"
    elif operation == "max":
        value = float(values.max())
        label = "maximum"
    elif operation == "count":
        value = float(values.count())
        label = "count"
    else:
        value = float(values.sum())
        label = "total"

    formatted = _format_metric(value, metric_col, operation)
    row_count = len(values)
    channel_col = _find_col(scoped_df, ["channel", "source", "platform", "store"])
    detail = ""
    followups = [
        "Compare this with the same period last year",
        "Break this down by product",
    ]

    if channel_col and not re.search(r"channel|online|retail|marketplace|platform", query, re.I):
        channels = scoped_df.groupby(channel_col)[metric_col].sum().sort_values(ascending=False)
        if not channels.empty:
            top_channel = str(channels.index[0])
            top_value = _format_metric(float(channels.iloc[0]), metric_col, "sum")
            detail = f" I used overall sales across all channels; {top_channel} was the largest channel at {top_value}."
            followups.insert(0, "Break this down by channel")

    ideas = " I can also compare last year vs current year, isolate a specific channel, or find which products drove the number."
    sentence = f"The {label} {metric_col} {scope_label} is {formatted}, calculated from {row_count:,} matching rows.{detail}{ideas}"

    return {
        "agent": "generic_metric_agent",
        "sentence": sentence,
        "citation": Citation(
            source=filename,
            ref=f"{label} {metric_col}",
            excerpt=f"{scope_label}: {formatted} from {row_count:,} rows",
        ),
        "followups": followups,
    }


def _agent_product_units(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    units_col = _find_col(df, ["units", "unit", "qty", "quantity", "sold", "volume"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    if not product_col or not units_col:
        return None
    if not re.search(
        r"selling|sold|sell|velocity|volume|units|fastest|max unit|most unit|top unit",
        query, re.I
    ):
        return None
    # If the query is specifically about revenue, let _agent_product_revenue handle it
    if re.search(r"revenue|sales amount|total sales|by revenue|in revenue", query, re.I):
        return None

    df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
    product_units = df.groupby(product_col)[units_col].sum().sort_values(ascending=False)
    if product_units.empty:
        return None

    product = str(product_units.index[0])
    units = float(product_units.iloc[0])
    revenue = None
    if revenue_col:
        df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
        revenue = float(df.groupby(product_col)[revenue_col].sum().get(product, 0))

    sentence = f"{product} is selling the most, with {units:,.0f} units sold"
    if revenue is not None:
        sentence += f" and {_money(revenue)} in revenue"
    sentence += "."

    return {
        "agent": "product_units_agent",
        "sentence": sentence,
        "citation": Citation(
            source=filename,
            ref="units sold aggregation",
            excerpt=f"{product}: {units:,.0f} units" + (f", {_money(revenue)} revenue" if revenue is not None else ""),
        ),
    }


def _agent_product_revenue(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    units_col = _find_col(df, ["units", "unit", "qty", "quantity", "sold", "volume"])
    if not product_col or not revenue_col:
        return None
    if not re.search(
        r"revenue|top product|best product|performing product"
        r"|highest sales|most sales|max sales|max revenue"
        r"|which product|product.*max|product.*highest|product.*most"
        r"|most.*sales|most.*revenue|highest.*sales|highest.*revenue"
        r"|best.*sales|best.*revenue|highest.*selling|best selling.*revenue",
        query, re.I
    ):
        return None

    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
    product_revenue = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False)
    if product_revenue.empty:
        return None

    product = str(product_revenue.index[0])
    revenue = float(product_revenue.iloc[0])
    total = float(product_revenue.sum()) or 1
    share = round(revenue / total * 100, 1)
    units_part = ""
    if units_col:
        df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
        units = float(df.groupby(product_col)[units_col].sum().get(product, 0))
        units_part = f" It sold {units:,.0f} units."

    # Include top-3 for richer context
    top3 = product_revenue.head(3)
    runner_up = (
        f" Runner-up: {top3.index[1]} at {_money(float(top3.iloc[1]))}."
        if len(top3) > 1 else ""
    )

    return {
        "agent": "product_revenue_agent",
        "sentence": (
            f"{product} had the highest sales at {_money(revenue)} ({share}% of total revenue).{units_part}{runner_up}"
        ),
        "citation": Citation(
            source=filename,
            ref="product revenue aggregation",
            excerpt=f"{product}: {_money(revenue)} revenue ({share}% share)",
        ),
    }


def _agent_best_month(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    date_col = _find_col(df, ["date", "time", "month", "period"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    if not date_col or not revenue_col:
        return None
    if not re.search(r"month|best period|peak|strongest|best-performing", query, re.I):
        return None

    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
    df["_mm_date"] = pd.to_datetime(df[date_col], errors="coerce")
    monthly = df.dropna(subset=["_mm_date"]).set_index("_mm_date").resample("ME")[revenue_col].sum()
    if monthly.empty:
        return None

    best_idx = monthly.idxmax()
    best_val = float(monthly.max())
    label = best_idx.strftime("%B %Y")
    return {
        "agent": "time_series_agent",
        "sentence": f"Your best-performing month was {label}, with {_money(best_val)} in revenue.",
        "citation": Citation(
            source=filename,
            ref="monthly revenue aggregation",
            excerpt=f"{label}: {_money(best_val)}",
        ),
    }


def _agent_at_risk(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    units_col = _find_col(df, ["units", "unit", "qty", "quantity", "sold", "volume"])
    date_col = _find_col(df, ["date", "time", "month", "period"])
    if not product_col or not revenue_col:
        return None
    if not re.search(r"risk|stop|reduce|discontinue|liquidate|underperform|attention|declin", query, re.I):
        return None

    metric = units_col or revenue_col
    df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)

    if date_col:
        df["_risk_date"] = pd.to_datetime(df[date_col], errors="coerce")
        valid = df.dropna(subset=["_risk_date"])
        if not valid.empty:
            cutoff = valid["_risk_date"].median()
            early = valid[valid["_risk_date"] <= cutoff].groupby(product_col)[metric].sum()
            late = valid[valid["_risk_date"] > cutoff].groupby(product_col)[metric].sum()
            products = sorted(set(early.index) | set(late.index))
            declines = []
            for product in products:
                before = float(early.get(product, 0))
                after = float(late.get(product, 0))
                if before > 0:
                    decline = (before - after) / before * 100
                    declines.append((str(product), decline, before, after))
            declines.sort(key=lambda item: item[1], reverse=True)
            declines = [item for item in declines if item[1] > 0][:3]
            if declines:
                names = ", ".join(f"{name} ({decline:.0f}% down)" for name, decline, _, _ in declines)
                return {
                    "agent": "risk_agent",
                    "sentence": f"The products needing attention are {names}.",
                    "citation": Citation(
                        source=filename,
                        ref="first-half vs second-half trend",
                        excerpt=names,
                    ),
                }

    low_revenue = df.groupby(product_col)[revenue_col].sum().sort_values().head(3)
    names = ", ".join(str(name) for name in low_revenue.index)
    return {
        "agent": "risk_agent",
        "sentence": f"The lowest-revenue products are {names}; review them before increasing spend.",
        "citation": Citation(source=filename, ref="bottom revenue aggregation", excerpt=names),
    }


def _agent_channel(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    channel_col = _find_col(df, ["channel", "source", "platform", "store"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    if not channel_col or not revenue_col:
        return None
    if not re.search(r"channel|platform|source|retail|online|marketplace", query, re.I):
        return None

    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
    channels = df.groupby(channel_col)[revenue_col].sum().sort_values(ascending=False)
    if channels.empty:
        return None
    top = str(channels.index[0])
    value = float(channels.iloc[0])
    return {
        "agent": "channel_agent",
        "sentence": f"{top} is the strongest channel at {_money(value)} in revenue.",
        "citation": Citation(source=filename, ref="channel revenue aggregation", excerpt=f"{top}: {_money(value)}"),
    }


def _agent_explain_obsolescence(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    """
    Detects 'why is X marked as liquidate/discontinue/discount/monitor?' patterns
    and computes a plain-English explanation of the composite risk score for that product.
    """
    if not re.search(
        r"why|explain|reason|because|obsolescence|liquidate|discontinue|discount|mark|flagged|action|radar|at.?risk",
        query, re.I
    ):
        return None

    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    date_col = _find_col(df, ["date", "time", "month", "period"])
    category_col = _find_col(df, ["category", "cat", "group", "type"])

    if not product_col or not revenue_col:
        return None

    # Try to match a product name from the query
    products = df[product_col].dropna().unique()
    query_lower = query.lower()
    matched_product: Optional[str] = None

    for p in products:
        if str(p).lower() in query_lower:
            matched_product = str(p)
            break

    # If no exact match, find the highest-risk product and explain it
    if not matched_product:
        # Require the query to be specifically about obsolescence actions
        if not re.search(r"liquidate|discontinue|discount|obsolescence|radar|flagged|marked", query, re.I):
            return None
        # Compute risk for all products and pick the riskiest
        best_risk = -1
        for p in products:
            p = str(p)
            _, _, risk, _, _, _bd2 = _compute_product_risk(
                product_name=p, df=df, product_col=product_col, metric_col=revenue_col,
                date_col=date_col, category_col=category_col,
            )
            if risk > best_risk:
                best_risk = risk
                matched_product = p

    if not matched_product:
        return None

    level, action, risk, velocity_decline_pct, rationale, _bd = _compute_product_risk(
        product_name=matched_product,
        df=df,
        product_col=product_col,
        metric_col=revenue_col,
        date_col=date_col,
        category_col=category_col,
    )

    # Build a detailed, readable explanation
    risk_label = {"high": "high-risk", "medium": "medium-risk", "low": "low-risk"}.get(level, "risk")
    decline_detail = (
        f"its sales velocity declined {velocity_decline_pct:.0f}% in the last 90-day window compared to the prior period"
        if velocity_decline_pct > 0
        else "it has stable or growing sales velocity (risk driven by category trend and depreciation factors)"
    )

    sentence = (
        f"{matched_product} is marked as '{action}' because {decline_detail}. "
        f"Its composite risk score is {risk}/100 ({risk_label}). {rationale}"
    )

    return {
        "agent": "explain_obsolescence_agent",
        "sentence": sentence,
        "citation": Citation(
            source=filename,
            ref=f"velocity decline + risk score for {matched_product}",
            excerpt=f"Risk: {risk}/100 · Action: {action} · Velocity decline: {velocity_decline_pct:.0f}%",
        ),
        "followups": [
            f"Which other products are at risk of {action.lower()}?",
            "Show me the full obsolescence radar",
            f"What budget action should I take for {matched_product}?",
        ],
    }


def _agent_product_summary(filename: str, df: pd.DataFrame, query: str) -> Optional[Dict[str, Any]]:
    """
    Catch-all for any question involving products and a metric that no specific
    agent matched. Returns the full product revenue + units leaderboard so Gemini
    always has numbers to work with.
    """
    if _detect_statistical_operation(query):
        return None

    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    units_col = _find_col(df, ["units", "unit", "qty", "quantity", "sold", "volume"])

    if not product_col or not revenue_col:
        return None
    if not re.search(
        r"product|item|sku|sales|revenue|units|sold|max|top|best|highest|most|lowest|worst|least|which|what",
        query, re.I,
    ):
        return None

    df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0)
    by_revenue = df.groupby(product_col)[revenue_col].sum().sort_values(ascending=False)
    if by_revenue.empty:
        return None

    top = str(by_revenue.index[0])
    top_rev = float(by_revenue.iloc[0])
    total_rev = float(by_revenue.sum()) or 1
    share = round(top_rev / total_rev * 100, 1)

    summary_parts = [f"{top} leads with {_money(top_rev)} in revenue ({share}% of total)."]
    if len(by_revenue) > 1:
        second = str(by_revenue.index[1])
        summary_parts.append(f"Runner-up: {second} at {_money(float(by_revenue.iloc[1]))}.")

    units_part = ""
    if units_col:
        df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
        by_units = df.groupby(product_col)[units_col].sum().sort_values(ascending=False)
        if not by_units.empty:
            top_u = str(by_units.index[0])
            units_val = int(by_units.iloc[0])
            if top_u != top:
                units_part = f" By units, {top_u} leads with {units_val:,} sold."
            else:
                units_part = f" It also leads in units with {units_val:,} sold."

    sentence = " ".join(summary_parts) + units_part

    return {
        "agent": "product_summary_agent",
        "sentence": sentence,
        "citation": Citation(
            source=filename,
            ref="full product revenue leaderboard",
            excerpt=f"Top: {top} at {_money(top_rev)} ({share}% share)",
        ),
        "followups": [
            "Break this down by channel",
            "Show me the monthly trend for this product",
            "Which products are declining?",
        ],
    }


STAT_AGENTS = [
    _agent_explain_obsolescence,   # first — intercepts "why is X marked" questions
    _agent_product_revenue,        # "which product had the max/highest sales/revenue"
    _agent_product_units,          # "which product sold the most units"
    _agent_best_month,             # "what was my best month"
    _agent_at_risk,                # "which products are at risk / should I stop"
    _agent_channel,                # "which channel performs best"
    _agent_statistical_inference,  # grouped/ungrouped descriptive inference questions
    _agent_generic_metric,         # "what was total/average/max/min X [in month Y]"
    _agent_product_summary,        # catch-all — fires on any remaining product/sales question
]


def _generate_chart_code(query: str, df: pd.DataFrame, data_summary: str) -> Optional[str]:
    """Backward-compatible wrapper around the chart harness code generator."""
    plan = _plan_chart(query, df, data_summary)
    return _generate_chart_code_from_plan(query, df, data_summary, plan)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _find_mentioned_value(query: str, values: List[Any]) -> Optional[str]:
    q_norm = _normalize_text(query)
    best: tuple[int, Optional[str]] = (0, None)
    for raw in values:
        value = str(raw)
        v_norm = _normalize_text(value)
        if not v_norm:
            continue
        if v_norm in q_norm:
            score = len(v_norm)
        else:
            tokens = [token for token in v_norm.split() if len(token) >= 2]
            matches = sum(1 for token in tokens if token in q_norm)
            score = matches * 10 if tokens and matches >= max(1, len(tokens) - 1) else 0
        if score > best[0]:
            best = (score, value)
    return best[1]


def _fallback_chart_plan(query: str, df: pd.DataFrame) -> Dict[str, Any]:
    chart_type = _detect_chart_type(query)
    metric_col = _find_col(df, ["revenue", "sales", "amount", "total", "price", "units", "qty", "quantity", "sold"])
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    date_col = _find_col(df, ["date", "time", "month", "period"])
    category_col = _find_col(df, ["category", "cat", "group", "type"])
    channel_col = _find_col(df, ["channel", "source", "platform", "store"])
    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

    dimension_col = None
    if re.search(r"channel|platform|source|retail|online|marketplace", query, re.I):
        dimension_col = channel_col
    elif re.search(r"category|segment|type", query, re.I):
        dimension_col = category_col
    elif re.search(r"product|item|sku", query, re.I):
        dimension_col = product_col
    elif chart_type == "line":
        dimension_col = date_col
    elif chart_type in {"pie", "bar"}:
        dimension_col = channel_col or category_col or product_col

    filter_col = None
    filter_value = None
    if product_col:
        mentioned = _find_mentioned_value(query, df[product_col].dropna().unique().tolist())
        if mentioned:
            filter_col = product_col
            filter_value = mentioned

    if chart_type == "scatter" and len(numeric_cols) >= 2:
        metric_col = numeric_cols[1]
        dimension_col = numeric_cols[0]

    return {
        "chart_type": chart_type,
        "metric_col": metric_col,
        "dimension_col": dimension_col,
        "filter_col": filter_col,
        "filter_value": filter_value,
        "title": _extract_chart_title(query),
        "reasoning": "Fallback chart plan from query keywords and dataframe schema.",
    }


def _plan_chart(query: str, df: pd.DataFrame, data_summary: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Planner agent: creates a structured chart plan from the user request."""
    fallback = _fallback_chart_plan(query, df)
    if not settings.gemini_api_key:
        return fallback

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        product_col = _find_col(df, ["product", "item", "sku", "name"])
        channel_col = _find_col(df, ["channel", "source", "platform", "store"])
        category_col = _find_col(df, ["category", "cat", "group", "type"])
        value_hints = {}
        for col in [product_col, channel_col, category_col]:
            if col:
                value_hints[col] = [str(v) for v in df[col].dropna().unique().tolist()[:30]]

        prompt = f"""You are a visualization planner for a BI chatbot.
Return only valid JSON.

User request: {query}

Columns: {json.dumps(df.columns.tolist())}
Candidate values: {json.dumps(value_hints)}
Data summary:
{data_summary[:2500]}

Session retrieval context:
{_context_for_prompt(context, max_chars=3000)}

Choose a plan with these keys:
chart_type: one of histogram, pie, bar, line, scatter
metric_col: numeric metric column to plot, or null
dimension_col: grouping/x-axis column, or null
filter_col: column to filter, or null
filter_value: exact value to filter if the user mentions one, or null
title: short title
reasoning: one short sentence

Rules:
- If the user asks for a pie chart, chart_type must be pie.
- If the user asks for a histogram, chart_type must be histogram even if a product is mentioned.
- If a product such as NVMe SSD 2TB is mentioned, set filter_col to the product column and filter_value to that exact dataset value.
- Sales normally maps to revenue unless the user explicitly asks for units sold.
"""
        response = model.generate_content(prompt, generation_config={"temperature": 0.05, "max_output_tokens": 450})
        raw = (response.text or "").strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        plan = json.loads(raw)
        merged = {**fallback, **{k: v for k, v in plan.items() if k in fallback or k in {"reasoning"}}}

        if fallback.get("filter_value") and not merged.get("filter_value"):
            merged["filter_col"] = fallback.get("filter_col")
            merged["filter_value"] = fallback.get("filter_value")
        if re.search(r"histo\w*", query, re.I):
            merged["chart_type"] = "histogram"
        if re.search(r"pie", query, re.I):
            merged["chart_type"] = "pie"
        return merged
    except Exception as exc:
        logger.warning("Chart planner failed: %s", exc)
        return fallback


def _context_for_prompt(context: Optional[Dict[str, Any]], max_chars: int = 3000) -> str:
    if not context:
        return ""
    payload = {
        "files": context.get("files", []),
        "elastic_docs": [
            {
                "source_file": doc.get("source_file"),
                "row_number": doc.get("row_number"),
                "page_number": doc.get("page_number"),
                "doc_type": doc.get("doc_type"),
                "content": doc.get("content", "")[:500],
            }
            for doc in context.get("elastic_docs", [])[:8]
        ],
    }
    return json.dumps(payload, default=str)[:max_chars]


def _json_for_code(value: Any) -> str:
    return json.dumps(value)


def _fallback_chart_code_from_plan(plan: Dict[str, Any], df: pd.DataFrame) -> Optional[str]:
    chart_type = plan.get("chart_type") or "bar"
    metric_col = plan.get("metric_col") or _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    dimension_col = plan.get("dimension_col")
    filter_col = plan.get("filter_col")
    filter_value = plan.get("filter_value")
    title = plan.get("title") or "Generated Chart"

    if not metric_col and chart_type != "count":
        return None

    filter_lines = ""
    filter_summary = "all rows"
    if filter_col and filter_value and filter_col in df.columns:
        filter_lines = (
            f'plot_df = plot_df[plot_df[{_json_for_code(filter_col)}].astype(str).str.lower() == '
            f'{_json_for_code(str(filter_value).lower())}]\n'
        )
        filter_summary = f"{filter_col} = {filter_value}"

    if chart_type == "pie":
        if not dimension_col or dimension_col not in df.columns:
            dimension_col = _find_col(df, ["channel", "category", "product", "item", "sku", "name"])
        if not dimension_col:
            return None
        return f"""import plotly.express as px
plot_df = df.copy()
{filter_lines}plot_df[{_json_for_code(metric_col)}] = plot_df[{_json_for_code(metric_col)}].astype(float)
grouped = plot_df.groupby({_json_for_code(dimension_col)})[{_json_for_code(metric_col)}].sum().reset_index()
fig = px.pie(grouped, names={_json_for_code(dimension_col)}, values={_json_for_code(metric_col)}, title={_json_for_code(title)}, template="plotly_dark")
fig.update_traces(textposition="inside", textinfo="percent+label")
summary = f'Created a pie chart for {{len(grouped)}} segments using {metric_col} with filter {filter_summary}.'
"""

    if chart_type == "line":
        if not dimension_col or dimension_col not in df.columns:
            dimension_col = _find_col(df, ["date", "time", "month", "period"])
        if not dimension_col:
            return None
        return f"""import pandas as pd
import plotly.express as px
plot_df = df.copy()
{filter_lines}plot_df[{_json_for_code(dimension_col)}] = pd.to_datetime(plot_df[{_json_for_code(dimension_col)}], errors="coerce")
plot_df[{_json_for_code(metric_col)}] = plot_df[{_json_for_code(metric_col)}].astype(float)
grouped = plot_df.dropna(subset=[{_json_for_code(dimension_col)}]).set_index({_json_for_code(dimension_col)}).resample("ME")[{_json_for_code(metric_col)}].sum().reset_index()
fig = px.line(grouped, x={_json_for_code(dimension_col)}, y={_json_for_code(metric_col)}, title={_json_for_code(title)}, template="plotly_dark", markers=True)
summary = f'Created a monthly trend chart over {{len(grouped)}} points using {metric_col} with filter {filter_summary}.'
"""

    if chart_type == "scatter":
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        x_col = dimension_col if dimension_col in df.columns else (numeric_cols[0] if numeric_cols else None)
        y_col = metric_col if metric_col in df.columns else (numeric_cols[1] if len(numeric_cols) > 1 else None)
        if not x_col or not y_col:
            return None
        return f"""import plotly.express as px
plot_df = df.copy()
{filter_lines}fig = px.scatter(plot_df, x={_json_for_code(x_col)}, y={_json_for_code(y_col)}, title={_json_for_code(title)}, template="plotly_dark")
summary = f'Created a scatter plot of {y_col} against {x_col} with {{len(plot_df)}} rows.'
"""

    if chart_type == "histogram":
        return f"""import plotly.express as px
plot_df = df.copy()
{filter_lines}plot_df[{_json_for_code(metric_col)}] = plot_df[{_json_for_code(metric_col)}].astype(float)
fig = px.histogram(plot_df, x={_json_for_code(metric_col)}, nbins=12, title={_json_for_code(title)}, template="plotly_dark")
fig.update_layout(xaxis_title={_json_for_code(metric_col)}, yaxis_title="Count")
summary = f'Created a histogram of {metric_col} for {{len(plot_df)}} rows with filter {filter_summary}.'
"""

    if not dimension_col or dimension_col not in df.columns:
        dimension_col = _find_col(df, ["product", "item", "sku", "name", "channel", "category"])
    if not dimension_col:
        return None
    return f"""import plotly.express as px
plot_df = df.copy()
{filter_lines}plot_df[{_json_for_code(metric_col)}] = plot_df[{_json_for_code(metric_col)}].astype(float)
grouped = plot_df.groupby({_json_for_code(dimension_col)})[{_json_for_code(metric_col)}].sum().reset_index().sort_values({_json_for_code(metric_col)}, ascending=False)
fig = px.bar(grouped, x={_json_for_code(dimension_col)}, y={_json_for_code(metric_col)}, title={_json_for_code(title)}, template="plotly_dark")
summary = f'Created a bar chart for {{len(grouped)}} groups using {metric_col} with filter {filter_summary}.'
"""


def _generate_chart_code_from_plan(
    query: str,
    df: pd.DataFrame,
    data_summary: str,
    plan: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Coding agent: writes Plotly code from the chart plan, with fallback code if LLM is unavailable."""
    if not settings.gemini_api_key:
        return _fallback_chart_code_from_plan(plan, df)

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        col_info = f"Columns: {', '.join(df.columns.tolist())}\nSample rows:\n{df.head(5).to_string(index=False)}"
        sanitized_query = query.replace('"', "'").replace('\\', '')
        prompt = f"""Write Python code to answer this visualization request: "{sanitized_query}"

DataFrame variable name: `df`
{col_info}
Session context:
{_context_for_prompt(context, max_chars=3000)}

Structured chart plan:
{json.dumps(plan)}

Rules:
- Import only from: pandas, numpy, plotly.express, plotly.graph_objects
- Assign the final figure to `fig`
- Assign a 1-2 sentence plain-English summary to `summary` (no markdown, no em-dashes)
- Do NOT call fig.show()
- Follow the structured chart plan exactly, including chart_type, filter_col, filter_value, metric_col, and dimension_col
- For pie charts, use px.pie with names and values
- For histograms, use px.histogram even when a product filter is present
- If filter_col/filter_value are present, filter df before plotting
- Use a dark-friendly Plotly template: template="plotly_dark"

Return ONLY the Python code block, no explanation."""

        response = model.generate_content(prompt, generation_config={"temperature": 0.1, "max_output_tokens": 600})
        raw = (response.text or "").strip()
        raw = re.sub(r"^```python\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        code = raw.strip()
        return code or _fallback_chart_code_from_plan(plan, df)
    except Exception as exc:
        logger.warning("Chart code generation failed: %s", exc)
        return _fallback_chart_code_from_plan(plan, df)


def _repair_chart_code(query: str, df: pd.DataFrame, plan: Dict[str, Any], code: str, error: str) -> Optional[str]:
    """Reviewer/repair agent: fixes generated code after a sandbox failure."""
    if not settings.gemini_api_key:
        return _fallback_chart_code_from_plan(plan, df)
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""Repair this Plotly code for a restricted sandbox.
Return only Python code.

User request: {query}
Chart plan: {json.dumps(plan)}
Sandbox error: {error}
Columns: {json.dumps(df.columns.tolist())}

Broken code:
{code}

Rules:
- Import only pandas, numpy, plotly.express, plotly.graph_objects.
- Do not use open, eval, exec, getattr, setattr, type, dir, vars, object.
- Assign final Plotly figure to fig and plain-English summary to summary.
"""
        response = model.generate_content(prompt, generation_config={"temperature": 0.05, "max_output_tokens": 650})
        raw = (response.text or "").strip()
        raw = re.sub(r"^```python\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return raw.strip() or _fallback_chart_code_from_plan(plan, df)
    except Exception as exc:
        logger.warning("Chart repair failed: %s", exc)
        return _fallback_chart_code_from_plan(plan, df)


def _summarize_chart_result(query: str, plan: Dict[str, Any], result_summary: str) -> str:
    chart_type = str(plan.get("chart_type") or "chart")
    title = str(plan.get("title") or _extract_chart_title(query))
    filter_value = plan.get("filter_value")
    filter_text = f" for {filter_value}" if filter_value else ""
    metric = plan.get("metric_col") or "the selected metric"
    return (
        f"I created a {chart_type} chart{filter_text} in ZScratchpad. "
        f"{result_summary or f'The chart uses {metric} from your uploaded data.'} "
        "Open the scratchpad card to inspect the chart, and I can also explain the pattern or create another view like a pie chart, trend line, or channel breakdown."
    )


def _fallback_chart_code(query: str, df: pd.DataFrame) -> Optional[str]:
    """Generate a basic histogram/bar chart without Gemini."""
    product_col = _find_col(df, ["product", "item", "sku", "name"])
    revenue_col = _find_col(df, ["revenue", "sales", "amount", "total", "price"])
    if not revenue_col:
        return None

    if product_col and re.search(r"bar|by product|product", query, re.I):
        return f"""import plotly.express as px
grouped = df.groupby("{product_col}")["{revenue_col}"].sum().reset_index()
fig = px.bar(grouped, x="{product_col}", y="{revenue_col}", title="Revenue by Product", template="plotly_dark")
summary = "Bar chart showing total revenue for each product."
"""
    return f"""import plotly.express as px
fig = px.histogram(df, x="{revenue_col}", nbins=20, title="{revenue_col.title()} Distribution", template="plotly_dark")
summary = "Histogram showing the distribution of {revenue_col}."
"""


def _detect_chart_type(query: str) -> str:
    q = query.lower()
    if "pie" in q:
        return "pie"
    if "histogram" in q or "histo" in q:
        return "histogram"
    if "scatter" in q:
        return "scatter"
    if re.search(r"line|trend|over time", q):
        return "line"
    return "bar"


def _extract_chart_title(query: str) -> str:
    q = query.strip().rstrip("?")
    q = re.sub(r"^(can you |could you |please |show me |give me |create |make |generate |draw )", "", q, flags=re.I)
    return q[:60].title()


def _apply_business_rules_to_frames(
    frames: List[Dict[str, Any]],
    rules: Optional[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], str]:
    """
    Returns (filtered_frames, policy_context_text).
    Filters rows from each frame's DataFrame according to active month-exclusion rules.
    """
    if not rules or not rules.get("exclude_months"):
        return frames, ""

    import calendar as _cal
    from app.services.analytics import _datetime_series, _find_date_col

    excluded_months: List[int] = rules["exclude_months"]
    source: str = rules.get("source_filename", "policy.pdf")
    month_names = [_cal.month_name[m] for m in excluded_months]

    filtered: List[Dict[str, Any]] = []
    for frame in frames:
        df: pd.DataFrame = frame["df"].copy()
        date_col = _find_date_col(df)
        if date_col:
            dates = _datetime_series(df[date_col])
            mask = dates.dt.month.isin(excluded_months)
            df = df[~mask].reset_index(drop=True)
        filtered.append({**frame, "df": df})

    names_str = ", ".join(month_names)
    policy_context = (
        f"ACTIVE BUSINESS RULES (from {source}):\n"
        f"The following months are excluded from all profit/revenue calculations "
        f"as per company policy: {names_str}.\n"
        f"When answering any question about totals, profit, revenue, or calculations, "
        f"DO NOT include data from {names_str}. "
        f"Always mention this exclusion in your answer."
    )
    return filtered, policy_context


def load_data_node(state: AgentState) -> AgentState:
    try:
        from app.services.analysis_context import get_analysis_context

        context = get_analysis_context(state["session_id"], query=state["query"])
        frames = context.get("frames") or _load_session_dataframes(state["session_id"])
        state["analysis_context"] = context
        if context.get("elastic_docs") and not state.get("retrieved_docs"):
            state["retrieved_docs"] = context.get("elastic_docs", [])
    except Exception as exc:
        logger.warning("Analysis context load failed: %s", exc)
        frames = _load_session_dataframes(state["session_id"])

    rules = get_session_business_rules(state["session_id"])
    frames, policy_context = _apply_business_rules_to_frames(frames, rules)

    state["dataframes"] = frames
    state["data_summary"] = _build_data_summary(frames)
    state["policy_context"] = policy_context
    return state


def classify_node(state: AgentState) -> AgentState:
    query = state["query"]

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
        r"histo\w*|bar chart|line chart|scatter|plot|chart|graph|visuali[sz]e|show me a|draw",
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


def statistics_node(state: AgentState) -> AgentState:
    filename, df = _combined_frame(state.get("dataframes", []))
    if df is None or filename is None:
        state["stats_results"] = []
        state["error"] = "no_structured_data"
        return state

    results: List[Dict[str, Any]] = []
    suggested_followups: List[str] = []
    for agent in STAT_AGENTS:
        try:
            result = agent(filename, df.copy(), state["query"])
            if result:
                results.append(result)
                suggested_followups.extend(result.get("followups", []))
        except Exception as exc:
            logger.warning("%s failed: %s", getattr(agent, "__name__", "stat_agent"), exc)
    state["stats_results"] = results
    state["suggested_followups"] = list(dict.fromkeys(suggested_followups))[:4]
    return state


def retrieval_node(state: AgentState) -> AgentState:
    from app.services.chat_service import _elastic_search

    docs = _elastic_search(state["session_id"], state["query"], top_k=10)
    if not docs:
        docs = _local_pdf_search(state["session_id"], state["query"], top_k=10)
    if not docs:
        docs = state.get("retrieved_docs", [])
    state["retrieved_docs"] = docs
    return state


def visualization_node(state: AgentState) -> AgentState:
    from app.services.sandbox import run_chart_code
    from app.services.scratchpad import save_artifact

    query = state["query"]
    session_id = state["session_id"]
    _, df = _combined_frame(state.get("dataframes", []))

    if df is None:
        state["answer"] = "Upload a CSV or Excel file first so I have data to chart."
        state["citations"] = []
        return state

    plan = _plan_chart(query, df, state.get("data_summary", ""), state.get("analysis_context"))
    code = _generate_chart_code_from_plan(query, df, state.get("data_summary", ""), plan, state.get("analysis_context"))
    if not code:
        state["answer"] = "I could not generate chart code for that request. Try rephrasing, for example: show me a histogram of RTX 3050 sales or create a pie chart by channel."
        state["citations"] = []
        return state

    result = run_chart_code(code, df)
    if not result["ok"]:
        repaired_code = _repair_chart_code(query, df, plan, code, result["error"])
        if repaired_code:
            code = repaired_code
            result = run_chart_code(code, df)
    if not result["ok"]:
        fallback_code = _fallback_chart_code_from_plan(plan, df)
        if fallback_code and fallback_code != code:
            code = fallback_code
            result = run_chart_code(code, df)
    if not result["ok"]:
        state["answer"] = f"The chart ran into an issue: {result['error']}. Please try a simpler request."
        state["citations"] = []
        return state

    title = plan.get("title") or _extract_chart_title(query)
    artifact = {
        "type": plan.get("chart_type") or _detect_chart_type(query),
        "title": title,
        "chart": result["chart"],
        "summary": result["summary"],
        "metadata": {
            "query": query,
            "chart_type": plan.get("chart_type"),
            "metric": plan.get("metric_col"),
            "dimension": plan.get("dimension_col"),
            "filter": f"{plan.get('filter_col')}={plan.get('filter_value')}" if plan.get("filter_col") and plan.get("filter_value") else "",
            "planner": plan.get("reasoning", ""),
        },
    }
    report_id = save_artifact(session_id, artifact)
    state["scratchpad_link"] = f"/ui/scratchpad/{session_id}/{report_id}"
    state["answer"] = _summarize_chart_result(query, plan, result["summary"])
    state["citations"] = []
    state["followups"] = [
        "Explain the chart pattern",
        "Create a pie chart by channel",
        "Show this as a monthly trend",
    ]
    return state


def hypothesis_clarify_node(state: AgentState) -> AgentState:
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
    from app.services.sandbox import run_chart_code
    from app.services.scratchpad import save_artifact

    query = state["query"]
    session_id = state["session_id"]
    _, df = _combined_frame(state.get("dataframes", []))

    if df is None:
        state["answer"] = "Upload a CSV or Excel file first."
        state["citations"] = []
        return state

    params = dict(re.findall(r"(\w+)=([^\s,]+)", query))
    metric = params.get("metric", "revenue").strip()
    group_a = params.get("group_a", "").strip()
    group_b = params.get("group_b", "").strip()
    try:
        alpha = float(params.get("alpha", "0.05").strip())
    except ValueError:
        alpha = 0.05

    category_col = _find_col(df, ["category", "cat", "group", "type"])
    metric_col = _find_col(df, [metric.lower()]) or metric

    import re as _re
    def _safe_str(s: str) -> str:
        return _re.sub(r"[^a-zA-Z0-9 _\-\.]", "", s)

    group_a = _safe_str(group_a)
    group_b = _safe_str(group_b)
    metric_col = _safe_str(metric_col)
    safe_cat_col = _safe_str(category_col or "category")

    code = f"""import plotly.graph_objects as go
from scipy import stats
import numpy as np

cat_col = "{safe_cat_col}"
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
    title=f"Hypothesis Test: {{group_a}} vs {{group_b}} on {{metric_col}}",
    template="plotly_dark",
    yaxis_title=metric_col,
)

verdict = "Reject the null hypothesis" if reject else "Fail to reject the null hypothesis"
summary = (
    f"t-statistic: {{t_stat:.4f}}, p-value: {{p_value:.4f}} (alpha={{alpha}}). "
    f"{{verdict}}. "
    f"{{group_a}} mean: {{a_data.mean():.2f}}, {{group_b}} mean: {{b_data.mean():.2f}}. "
    f"The difference is {{'statistically significant' if reject else 'not statistically significant'}} "
    f"at the {{alpha}} level."
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
    state["scratchpad_link"] = f"/ui/scratchpad/{session_id}/{report_id}"
    state["answer"] = result["summary"]
    state["citations"] = []
    return state


def _local_pdf_search(session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Fallback retrieval over PDFs held in the in-memory session store."""
    query_terms = {
        term
        for term in re.findall(r"[a-zA-Z0-9]{3,}", query.lower())
        if term not in {"the", "and", "for", "with", "from", "this", "that", "what", "which"}
    }
    if not query_terms:
        return []

    ensure_session_loaded(session_id)
    with store_lock:
        session_files = dict(session_store.get(session_id, {}))

    hits: List[Dict[str, Any]] = []
    for file_data in session_files.values():
        if file_data.get("file_type") != "pdf":
            continue
        pages = (file_data.get("text") or "").split("\n")
        for page_idx, page_text in enumerate(pages, start=1):
            clean_text = page_text.strip()
            if not clean_text:
                continue
            lower = clean_text.lower()
            score = sum(1 for term in query_terms if term in lower)
            if score <= 0:
                continue
            hits.append(
                {
                    "content": clean_text[:1200],
                    "source_file": file_data.get("filename", "policy.pdf"),
                    "page_number": page_idx,
                    "row_number": None,
                    "doc_type": "unstructured",
                    "score": score,
                }
            )

    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return hits[:top_k]


def _retrieval_fallback_answer(retrieved_docs: List[Dict[str, Any]]) -> str:
    snippets = []
    for doc in retrieved_docs[:3]:
        source = doc.get("source_file", "uploaded document")
        ref = f"page {doc.get('page_number')}" if doc.get("page_number") else "matching row"
        excerpt = re.sub(r"\s+", " ", doc.get("content", "")).strip()[:260]
        if excerpt:
            snippets.append(f"{source} ({ref}) says: {excerpt}")
    if not snippets:
        return ""
    return "Based on your uploaded data, " + " ".join(snippets)


def synthesis_node(state: AgentState) -> AgentState:
    stats_results = state.get("stats_results", [])
    retrieved_docs = state.get("retrieved_docs", [])
    data_summary = state.get("data_summary", "")
    policy_context = state.get("policy_context", "")

    # ── No data at all ──────────────────────────────────────────────────────
    if not stats_results and not retrieved_docs:
        if state.get("error") == "no_structured_data":
            state["answer"] = (
                "Upload a CSV or Excel file first — once I have your data I can answer "
                "questions about revenue, products, channels, and more."
            )
        elif settings.gemini_api_key and data_summary:
            answer = _gemini_conversational(
                query=state["query"],
                local_facts="",
                retrieved_docs=[],
                history=state.get("history", []),
                data_summary=data_summary,
                policy_context=policy_context,
            )
            state["answer"] = answer or "I couldn't find relevant data in your uploaded files for this question."
        else:
            state["answer"] = "I couldn't find relevant data in your uploaded files for this question."
        state["citations"] = []
        return state

    # ── Build local facts string from stat agent results ────────────────────
    local_facts = " ".join(r["sentence"] for r in stats_results)

    # ── Always use Gemini when key is available ─────────────────────────────
    if settings.gemini_api_key:
        gemini_answer = _gemini_conversational(
            query=state["query"],
            local_facts=local_facts,
            retrieved_docs=retrieved_docs,
            history=state.get("history", []),
            data_summary=data_summary,
            policy_context=policy_context,
        )
        if gemini_answer:
            state["answer"] = gemini_answer
        else:
            answer = f"Based on your uploaded data, {local_facts}".strip() if local_facts else _retrieval_fallback_answer(retrieved_docs)
            if policy_context:
                import calendar as _cal
                from app.services.business_rules_service import get_session_business_rules
                rules = get_session_business_rules(state["session_id"])
                if rules and rules.get("exclude_months"):
                    names = ", ".join(_cal.month_name[m] for m in rules["exclude_months"])
                    answer += f" (Note: {names} data excluded per policy — {rules.get('source_filename', 'policy.pdf')})"
            state["answer"] = answer
    elif local_facts:
        answer = f"Based on your uploaded data, {local_facts}".strip()
        if policy_context:
            import calendar as _cal
            from app.services.business_rules_service import get_session_business_rules
            rules = get_session_business_rules(state["session_id"])
            if rules and rules.get("exclude_months"):
                names = ", ".join(_cal.month_name[m] for m in rules["exclude_months"])
                answer += f" (Note: {names} data excluded per policy — {rules.get('source_filename', 'policy.pdf')})"
        state["answer"] = answer
    elif retrieved_docs:
        state["answer"] = _retrieval_fallback_answer(retrieved_docs)
    else:
        state["answer"] = f"Based on your uploaded data, {local_facts}".strip()

    # ── Citations as plain dicts (avoid Pydantic serialization in graph state) ──
    citation_dicts: List[Dict[str, str]] = []
    for result in stats_results:
        if result.get("citation"):
            c = result["citation"]
            citation_dicts.append({
                "source": c.source if hasattr(c, "source") else c.get("source", ""),
                "ref": c.ref if hasattr(c, "ref") else c.get("ref", ""),
                "excerpt": c.excerpt if hasattr(c, "excerpt") else c.get("excerpt", ""),
            })
    for doc in retrieved_docs[:3]:
        ref = f"page {doc['page_number']}" if doc.get("page_number") else f"row {doc.get('row_number', '?')}"
        citation_dicts.append({
            "source": doc.get("source_file", "uploaded-data"),
            "ref": ref,
            "excerpt": (doc.get("content") or "")[:200],
        })
    state["citations"] = citation_dicts
    return state


def followup_node(state: AgentState) -> AgentState:
    if state.get("followups"):
        return state

    # Prefer suggestions surfaced by individual stat agents (most contextual)
    if state.get("suggested_followups"):
        state["followups"] = state["suggested_followups"][:3]
        return state

    query = state["query"].lower()
    answer = (state.get("answer") or "").lower()

    # Choose chips based on what was just answered so they don't repeat the same question
    if re.search(r"month|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", query):
        state["followups"] = [
            "Which products drove that month?",
            "Compare it to the same month last year",
            "Break this down by channel",
        ]
    elif re.search(r"channel|platform|source|retail|online", query):
        state["followups"] = [
            "Which product performs best in this channel?",
            "Show me the channel trend over time",
            "Compare channels side by side",
        ]
    elif re.search(r"risk|stop|reduce|liquidate|discontinue|obsolescence", query):
        state["followups"] = [
            "What's the revenue trend for these products?",
            "Which channel should I pull back from first?",
            "Run a Monte Carlo simulation on the highest-risk product",
        ]
    elif re.search(r"selling|sold|units|velocity", query):
        state["followups"] = [
            "What channel drives the most of these units?",
            "Which product has the highest revenue per unit?",
            "Are any of these at risk of obsolescence?",
        ]
    elif re.search(r"revenue|sales|product|top|best|max|highest", query):
        state["followups"] = [
            "What was this product's best month?",
            "Which channel contributed most to this revenue?",
            "Compare first half vs second half of the year",
        ]
    elif re.search(r"budget|invest|allocat|spend", query):
        state["followups"] = [
            "Show me the full budget recommendations",
            "Which channel has the best ROI?",
            "Simulate a 20% budget shift to the top channel",
        ]
    else:
        state["followups"] = [
            "What was my best-performing month?",
            "Which product is selling the most?",
            "Are there any at-risk products?",
        ]
    return state


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
- Do not start with "Based on your uploaded data" -- be direct."""


def _gemini_conversational(
    query: str,
    local_facts: str,
    retrieved_docs: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    data_summary: str = "",
    policy_context: str = "",
) -> str:
    """
    Gemini-powered synthesis that is always conversational.
    local_facts = pre-computed stat agent findings (ground truth)
    data_summary = full data snapshot built from DataFrames
    policy_context = active business-rule exclusions (injected before user question)
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=_GEMINI_SYSTEM)

        docs_text = "\n".join(
            f"[{i}] {doc.get('source_file')} "
            f"(row/page {doc.get('row_number') or doc.get('page_number')}): "
            f"{doc.get('content', '')[:400]}"
            for i, doc in enumerate(retrieved_docs[:5], 1)
        )

        hist_text = "\n".join(
            f"{t.get('role', 'user').upper()}: {t.get('content', '')}"
            for t in history[-8:]
        )

        context_blocks: List[str] = []
        if policy_context:
            context_blocks.append(policy_context)
        if local_facts:
            context_blocks.append(f"COMPUTED FINDINGS (verified from user data — treat as facts):\n{local_facts}")
        if data_summary:
            context_blocks.append(f"FULL DATA SNAPSHOT:\n{data_summary}")
        if docs_text:
            context_blocks.append(f"RETRIEVED DOCUMENT CONTEXT:\n{docs_text}")
        if hist_text:
            context_blocks.append(f"CONVERSATION HISTORY:\n{hist_text}")

        context_blocks.append(f"USER QUESTION: {query}")

        prompt = "\n\n".join(context_blocks)

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.45, "max_output_tokens": 500},
        )
        return (response.text or "").strip()
    except Exception as exc:
        logger.warning("Gemini conversational synthesis failed: %s", exc)
        return ""


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
    graph.add_edge("visualization", "followup")
    graph.add_edge("hypothesis_run", "followup")
    graph.add_edge("hypothesis_clarify", END)
    return graph.compile()


try:
    compiled_chat_graph = _build_graph()
except Exception as exc:  # pragma: no cover - only used before dependencies are installed
    logger.warning("LangGraph unavailable, chat graph disabled: %s", exc)
    compiled_chat_graph = None


async def answer_query_graph(
    session_id: str,
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> ChatMessage:
    initial: AgentState = {
        "session_id": session_id,
        "query": query,
        "history": history or [],
        "stats_results": [],
        "retrieved_docs": [],
        "citations": [],
        "followups": [],
        "error": None,
    }

    if compiled_chat_graph is None:
        from app.services.chat_service import _canned_response

        return _canned_response(query, session_id)

    result = await compiled_chat_graph.ainvoke(initial)

    # Reconstruct Citation objects from the plain dicts stored in graph state
    raw_citations = result.get("citations") or []
    citations = [
        Citation(source=c["source"], ref=c["ref"], excerpt=c["excerpt"])
        for c in raw_citations
        if isinstance(c, dict) and c.get("source")
    ] or None

    return ChatMessage(
        role="assistant",
        content=result.get("answer") or "I couldn't find relevant data in your uploaded files for this question.",
        citations=citations,
        followups=result.get("followups") or None,
        scratchpad_link=result.get("scratchpad_link") or None,
        clarification_form=result.get("clarification_form") or None,
    )
