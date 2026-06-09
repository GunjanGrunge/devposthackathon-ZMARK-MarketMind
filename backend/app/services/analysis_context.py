"""
Session-scoped analytical context shared by dashboard and chat orchestration.

The context is intentionally cached per session so uploads, dashboard cards, and
chat/chart agents operate from the same file/schema/retrieval snapshot until the
user clears or replaces session files.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

import pandas as pd

from app.services.eda import ensure_session_loaded, session_store, store_lock
from app.services.elastic import ElasticsearchService

logger = logging.getLogger("analysis_context")

_context_cache: Dict[str, Dict[str, Any]] = {}


def invalidate_analysis_context(session_id: str) -> None:
    _context_cache.pop(session_id, None)


def _session_signature(files: Dict[str, Dict[str, Any]]) -> str:
    parts: List[str] = []
    for file_id, file_data in sorted(files.items()):
        df = file_data.get("df")
        shape = df.shape if isinstance(df, pd.DataFrame) else (0, 0)
        columns = ",".join(map(str, df.columns.tolist())) if isinstance(df, pd.DataFrame) else ""
        if isinstance(df, pd.DataFrame):
            try:
                content_hash = hashlib.sha256(
                    df.head(200).to_json(date_format="iso", default_handler=str).encode("utf-8")
                ).hexdigest()
            except Exception:
                content_hash = ""
        else:
            content_hash = hashlib.sha256(str(file_data.get("text", "")[:2000]).encode("utf-8")).hexdigest()
        parts.append(f"{file_id}:{file_data.get('filename')}:{file_data.get('file_type')}:{shape}:{columns}:{content_hash}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _elastic_context(session_id: str, query: str = "business revenue product channel trend", top_k: int = 12) -> List[Dict[str, Any]]:
    if not ElasticsearchService.is_configured():
        return []

    try:
        es = ElasticsearchService.get_client()
        index_name = f"marketmind-{session_id}"
        if not es.indices.exists(index=index_name):
            return []
        resp = es.search(
            index=index_name,
            body={
                "size": top_k,
                "_source": {"excludes": ["embedding"]},
                "query": {
                    "bool": {
                        "filter": [{"term": {"session_id": session_id}}],
                        "should": [
                            {"match": {"content": {"query": query, "boost": 2}}},
                            {"term": {"doc_type": "structured"}},
                            {"term": {"doc_type": "unstructured"}},
                        ],
                    }
                },
            },
        )
        return [hit.get("_source", {}) for hit in resp.get("hits", {}).get("hits", [])]
    except Exception as exc:
        logger.warning("Elastic analysis context retrieval failed for %s: %s", session_id, exc)
        return []


def get_analysis_context(session_id: str, query: str = "business revenue product channel trend") -> Dict[str, Any]:
    ensure_session_loaded(session_id)
    with store_lock:
        files = dict(session_store.get(session_id, {}))

    signature = _session_signature(files)
    cached = _context_cache.get(session_id)
    if cached and cached.get("signature") == signature:
        return {**cached, "elastic_docs": _elastic_context(session_id, query=query)}

    frames: List[Dict[str, Any]] = []
    file_summaries: List[Dict[str, Any]] = []
    for file_id, file_data in files.items():
        df = file_data.get("df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            frames.append({"file_id": file_id, "filename": file_data.get("filename", "uploaded-data"), "df": df.copy()})
            file_summaries.append(
                {
                    "file_id": file_id,
                    "filename": file_data.get("filename", "uploaded-data"),
                    "file_type": file_data.get("file_type", "csv"),
                    "rows": int(len(df)),
                    "columns": [str(col) for col in df.columns.tolist()],
                    "sample_rows": df.head(5).where(pd.notna(df.head(5)), None).to_dict(orient="records"),
                }
            )
        elif file_data.get("file_type") == "pdf":
            text = file_data.get("text") or ""
            file_summaries.append(
                {
                    "file_id": file_id,
                    "filename": file_data.get("filename", "uploaded-document"),
                    "file_type": "pdf",
                    "characters": len(text),
                    "sample_text": text[:1200],
                }
            )

    context = {
        "session_id": session_id,
        "signature": signature,
        "frames": frames,
        "files": file_summaries,
    }
    _context_cache[session_id] = context
    return {**context, "elastic_docs": _elastic_context(session_id, query=query)}
