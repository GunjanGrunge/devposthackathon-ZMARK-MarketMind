"""
LangGraph-backed chat orchestration for MarketMind.

The graph uses small specialist analysis nodes for statistical questions, then
optionally augments with Elastic retrieval and Gemini synthesis when configured.
It intentionally avoids sample data: every answer is derived from the current
session_store or retrieved session documents.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd

from app.core.config import settings
from app.schemas.analytics import ChatMessage, Citation
from app.services.eda import ensure_session_loaded, session_store, store_lock
from app.services.analytics import _compute_product_risk, _find_col as _analytics_find_col

logger = logging.getLogger("chat_graph")


class AgentState(TypedDict, total=False):
    session_id: str
    query: str
    history: List[Dict[str, str]]
    dataframes: List[Dict[str, Any]]
    data_summary: str               # text snapshot of uploaded data for Gemini context
    route: str
    stats_results: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, str]]  # plain dicts; reconstructed as Citation objects at boundary
    followups: List[str]
    suggested_followups: List[str]
    error: Optional[str]


def _find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
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
    _agent_generic_metric,         # "what was total/average/max/min X [in month Y]"
    _agent_product_summary,        # catch-all — fires on any remaining product/sales question
]


def load_data_node(state: AgentState) -> AgentState:
    frames = _load_session_dataframes(state["session_id"])
    state["dataframes"] = frames
    state["data_summary"] = _build_data_summary(frames)
    return state


def classify_node(state: AgentState) -> AgentState:
    query = state["query"]
    if re.search(r"regulation|policy|compliance|pdf|document|clause|packaging", query, re.I):
        state["route"] = "retrieval"
    else:
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
    state["retrieved_docs"] = docs
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

    # ── No data at all ──────────────────────────────────────────────────────
    if not stats_results and not retrieved_docs:
        if state.get("error") == "no_structured_data":
            state["answer"] = (
                "Upload a CSV or Excel file first — once I have your data I can answer "
                "questions about revenue, products, channels, and more."
            )
        elif settings.gemini_api_key and data_summary:
            # Data is loaded but no specific agent matched — let Gemini answer from the data summary
            answer = _gemini_conversational(
                query=state["query"],
                local_facts="",
                retrieved_docs=[],
                history=state.get("history", []),
                data_summary=data_summary,
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
        )
        if gemini_answer:
            state["answer"] = gemini_answer
        else:
            # Gemini failed — fall back to local plain answer
            state["answer"] = (
                f"Based on your uploaded data, {local_facts}".strip()
                if local_facts
                else _retrieval_fallback_answer(retrieved_docs)
            )
    elif local_facts:
        state["answer"] = f"Based on your uploaded data, {local_facts}".strip()
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
) -> str:
    """
    Gemini-powered synthesis that is always conversational.
    local_facts = pre-computed stat agent findings (ground truth)
    data_summary = full data snapshot built from DataFrames
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
        },
    )
    graph.add_edge("statistics", "retrieval")
    graph.add_edge("retrieval", "synthesis")
    graph.add_edge("synthesis", "followup")
    graph.add_edge("followup", END)
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
    )
