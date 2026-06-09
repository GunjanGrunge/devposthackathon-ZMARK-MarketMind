import pandas as pd

from app.services import analysis_context
from app.services.eda import session_store


def test_analysis_context_refreshes_elastic_docs_per_query(monkeypatch):
    session_store["context-session"] = {
        "f1": {
            "filename": "sales.xlsx",
            "df": pd.DataFrame([{"product_name": "Alpha", "revenue": 100}]),
            "file_type": "xlsx",
            "text": "",
        }
    }
    analysis_context.invalidate_analysis_context("context-session")
    queries = []

    def fake_elastic_context(session_id, query, top_k=12):
        queries.append(query)
        return [{"source_file": "sales.xlsx", "content": f"context for {query}"}]

    monkeypatch.setattr(analysis_context, "_elastic_context", fake_elastic_context)

    first = analysis_context.get_analysis_context("context-session", query="revenue")
    second = analysis_context.get_analysis_context("context-session", query="profit")

    assert first["elastic_docs"][0]["content"] == "context for revenue"
    assert second["elastic_docs"][0]["content"] == "context for profit"
    assert queries == ["revenue", "profit"]

    session_store.pop("context-session", None)
    analysis_context.invalidate_analysis_context("context-session")
