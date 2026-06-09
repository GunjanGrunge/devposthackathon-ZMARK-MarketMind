"""
chat_service.py — Hybrid semantic search (Elastic ELSER) + Gemini-grounded
answer generation for the ZmaRk chat assistant.
Falls back to a canned responder when Elastic or Gemini are unavailable so
the frontend always gets a useful response.
"""
import logging
import os
import re
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.services.eda import ensure_session_loaded, session_store, store_lock
from app.schemas.analytics import Citation, ChatMessage

logger = logging.getLogger("chat")


# ────────────────────────────────────────────────────────────────────────────
# Elastic hybrid search
# ────────────────────────────────────────────────────────────────────────────
def _elastic_search(session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Runs hybrid BM25 + sparse-vector (ELSER) search against the session index.
    Returns a list of hit dicts with keys: content, source_file, page_number, row_number.
    """
    from app.services.elastic import ElasticsearchService
    if not ElasticsearchService.is_configured():
        return []

    try:
        es = ElasticsearchService.get_client()
        index_name = f"marketmind-{session_id}"
        if not es.indices.exists(index=index_name):
            return []

        query_body = {
            "size": top_k,
            "query": {
                "bool": {
                    "should": [
                        # BM25 full-text
                        {"match": {"content": {"query": query, "boost": 1.0}}},
                        # ELSER sparse-vector semantic
                        {
                            "sparse_vector": {
                                "field": "embedding",
                                "inference_id": ".elser-2-elasticsearch",
                                "query": query,
                                "boost": 2.0,
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": ["content", "source_file", "page_number", "row_number", "doc_type"],
        }

        resp = es.search(index=index_name, body=query_body)
        hits = []
        for h in resp["hits"]["hits"]:
            src = h.get("_source", {})
            hits.append({
                "content": src.get("content", ""),
                "source_file": src.get("source_file", "data"),
                "page_number": src.get("page_number"),
                "row_number": src.get("row_number"),
                "doc_type": src.get("doc_type", ""),
                "score": h.get("_score", 0),
            })
        return hits

    except Exception as exc:
        logger.warning("Elastic search failed: %s", exc)
        return []


# ────────────────────────────────────────────────────────────────────────────
# Gemini LLM call
# ────────────────────────────────────────────────────────────────────────────
def _gemini_answer(query: str, context_chunks: List[Dict[str, Any]],
                    history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Sends the retrieved context + conversation history to Gemini and returns
    a grounded, concise answer.
    """
    try:
        import google.generativeai as genai
        api_key = settings.gemini_api_key
        if not api_key:
            raise ValueError("No Gemini API key")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")

        # Build context block
        ctx_text = ""
        for i, chunk in enumerate(context_chunks[:5], 1):
            src = chunk["source_file"]
            loc = f"page {chunk['page_number']}" if chunk.get("page_number") else f"row {chunk.get('row_number', '?')}"
            ctx_text += f"\n[{i}] {src} ({loc}):\n{chunk['content'][:600]}\n"

        system_prompt = (
            "You are ZmaRk, a business intelligence assistant. "
            "Answer the user's question using ONLY the provided data context. "
            "Be concise (2–4 sentences). Always start with 'Based on your uploaded data, …'. "
            "Cite your sources by referencing the bracketed numbers [1], [2], etc."
        )

        user_msg = f"Context:\n{ctx_text}\n\nQuestion: {query}"

        # Build chat history for multi-turn
        chat_history = []
        if history:
            for turn in history[-6:]:  # last 3 turns
                role = "user" if turn.get("role") == "user" else "model"
                chat_history.append({"role": role, "parts": [turn.get("content", "")]})

        response = model.generate_content(
            [system_prompt, user_msg],
            generation_config={"max_output_tokens": 400, "temperature": 0.3},
        )
        return response.text.strip()

    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        return ""


# ────────────────────────────────────────────────────────────────────────────
# Canned fallback responder (keyword-driven)
# ────────────────────────────────────────────────────────────────────────────
def _canned_response(query: str, session_id: str) -> ChatMessage:
    """Builds a locally grounded answer from session DataFrames."""
    lc = query.lower()

    ensure_session_loaded(session_id)
    with store_lock:
        session_files = dict(session_store.get(session_id, {}))

    dfs = [(fdata["filename"], fdata["df"])
           for fdata in session_files.values()
           if fdata.get("df") is not None]

    if not dfs:
        return ChatMessage(
            role="assistant",
            content="Upload a data file first so I can answer questions about it.",
            followups=["How do I upload a file?"],
        )

    import pandas as pd
    filename, df = dfs[0]

    rev_col = next((c for c in df.columns if any(k in c.lower() for k in ["revenue", "sales", "amount", "total"])), None)
    prod_col = next((c for c in df.columns if any(k in c.lower() for k in ["product", "item", "name"])), None)
    date_col = next((c for c in df.columns if any(k in c.lower() for k in ["date", "time", "month"])), None)
    ch_col = next((c for c in df.columns if any(k in c.lower() for k in ["channel", "source", "platform"])), None)

    if rev_col:
        df[rev_col] = pd.to_numeric(df[rev_col], errors="coerce").fillna(0)

    # ── Month / trend ──
    if re.search(r"month|best|peak|highest revenue|strongest", lc) and date_col and rev_col:
        try:
            df["_d"] = pd.to_datetime(df[date_col], errors="coerce")
            monthly = df.set_index("_d").resample("ME")[rev_col].sum()
            best_month = monthly.idxmax().strftime("%b '%y")
            best_val = monthly.max()
            return ChatMessage(
                role="assistant",
                content=f"Based on your uploaded data, your strongest month was {best_month} at ${best_val:,.0f}.",
                citations=[Citation(source=filename, ref="monthly aggregation", excerpt=f"Peak revenue: {best_month} = ${best_val:,.0f}")],
                followups=["What caused any anomalies?", "Break down by channel"],
            )
        except Exception:
            pass

    # ── At-risk / stop investing ──
    if re.search(r"stop|invest|at[- ]?risk|risk|discontinu|liquidat|drop|reduce", lc) and prod_col and rev_col:
        prod_rev = df.groupby(prod_col)[rev_col].sum().sort_values()
        worst = prod_rev.index[:2].tolist()
        worst_str = " and ".join(worst)
        return ChatMessage(
            role="assistant",
            content=f"Based on your uploaded data, the lowest-revenue products are {worst_str}. Consider reviewing their investment levels.",
            citations=[Citation(source=filename, ref=f"product revenue aggregation", excerpt=f"Bottom performers: {worst_str}")],
            followups=["What discount strategy would help?", "Which channel is underperforming?"],
        )

    # ── Product volume / velocity ──
    units_col = next((c for c in df.columns if any(k in c.lower() for k in ["unit", "qty", "quantity", "sold"])), None)
    asks_top_seller = re.search(
        r"velocit|fastest|units|moving|volume|selling|sold|sell|highest sold|highly sold|most sold|selling the most|top selling|best selling",
        lc,
    )
    if asks_top_seller and prod_col and units_col:
        df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
        product_units = df.groupby(prod_col)[units_col].sum().sort_values(ascending=False)
        fastest = product_units.index[0]
        units = float(product_units.iloc[0])
        revenue_text = ""
        excerpt = f"Top units sold: {fastest} = {units:,.0f} units"
        if rev_col:
            product_revenue = df.groupby(prod_col)[rev_col].sum()
            revenue = float(product_revenue.get(fastest, 0))
            revenue_text = f" It generated ${revenue:,.0f} in revenue."
            excerpt += f"; revenue ${revenue:,.0f}"
        return ChatMessage(
            role="assistant",
            content=f"Based on your uploaded data, {fastest} is selling the most, with {units:,.0f} units sold.{revenue_text}",
            citations=[Citation(source=filename, ref="units sold aggregation", excerpt=excerpt)],
            followups=["What is the revenue from this product?", "Which channel sells it best?"],
        )

    # ── Product revenue performance ──
    if re.search(r"top product|best product|highest revenue product|most revenue|revenue product|performing product|product performance", lc) and prod_col and rev_col:
        product_revenue = df.groupby(prod_col)[rev_col].sum().sort_values(ascending=False)
        top_product = product_revenue.index[0]
        revenue = float(product_revenue.iloc[0])
        units_text = ""
        excerpt = f"Top product by revenue: {top_product} = ${revenue:,.0f}"
        if units_col:
            df[units_col] = pd.to_numeric(df[units_col], errors="coerce").fillna(0)
            units = float(df.groupby(prod_col)[units_col].sum().get(top_product, 0))
            units_text = f" It also sold {units:,.0f} units."
            excerpt += f"; units {units:,.0f}"
        return ChatMessage(
            role="assistant",
            content=f"Based on your uploaded data, {top_product} is the top product by revenue at ${revenue:,.0f}.{units_text}",
            citations=[Citation(source=filename, ref="product revenue aggregation", excerpt=excerpt)],
            followups=["Which product is selling the most by units?", "Which channel sells it best?"],
        )

    # ── Channel ──
    if re.search(r"channel|online|retail|marketplace|platform", lc) and ch_col and rev_col:
        ch_rev = df.groupby(ch_col)[rev_col].sum().sort_values(ascending=False)
        top_ch = ch_rev.index[0]
        top_val = ch_rev.iloc[0]
        return ChatMessage(
            role="assistant",
            content=f"Based on your uploaded data, {top_ch} is your strongest channel at ${top_val:,.0f}.",
            citations=[Citation(source=filename, ref="channel revenue aggregation", excerpt=f"Top channel: {top_ch} = ${top_val:,.0f}")],
            followups=["Should I shift budget to this channel?", "Which products perform best here?"],
        )

    # ── Generic fallback ──
    total = float(df[rev_col].sum()) if rev_col else 0
    return ChatMessage(
        role="assistant",
        content=f"Based on your uploaded data ({filename}, {len(df):,} rows), I can help with revenue trends, product performance, channel mix, and at-risk SKUs. Total revenue in the dataset: ${total:,.0f}.",
        citations=[Citation(source=filename, ref=f"rows 1–{len(df)}", excerpt=f"Session dataset: {len(df)} rows, total revenue ${total:,.0f}")],
        followups=[
            "What was my best-performing month?",
            "Which product has the highest sales velocity?",
            "Are there any at-risk products?",
        ],
    )


# ────────────────────────────────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────────────────────────────────
def answer_query(session_id: str, query: str,
                  history: Optional[List[Dict[str, str]]] = None) -> ChatMessage:
    """
    1. Retrieve top-k context chunks from Elastic hybrid search.
    2. Pass to Gemini for a grounded answer.
    3. Fall back to the canned DataFrame responder if either step fails.
    """
    hits = _elastic_search(session_id, query)

    # Try Gemini if we have context
    if hits:
        answer_text = _gemini_answer(query, hits, history)
        if answer_text:
            # Build citations from top-3 hits
            citations = []
            for h in hits[:3]:
                ref = f"page {h['page_number']}" if h.get("page_number") else f"row {h.get('row_number', '?')}"
                excerpt = h["content"][:200].strip()
                citations.append(Citation(source=h["source_file"], ref=ref, excerpt=excerpt))

            return ChatMessage(
                role="assistant",
                content=answer_text,
                citations=citations if citations else None,
                followups=[
                    "Tell me more about this",
                    "What should I do about it?",
                    "Show me the breakdown by channel",
                ],
            )

    # Fallback: derive answer directly from cached DataFrames
    return _canned_response(query, session_id)
