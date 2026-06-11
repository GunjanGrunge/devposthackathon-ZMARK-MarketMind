"""
Tests for business_rules_service.py — PDF business rules extraction and
application to compute_dashboard.
"""
import pytest
import pandas as pd

from app.services.business_rules_service import (
    extract_business_rules,
    get_session_business_rules,
    invalidate_rules_cache,
    _is_policy_document,
)
from app.services.eda import session_store, store_lock
from app.services.analytics import compute_dashboard
from app.core.config import settings


# ──────────────────────────────────────────────────────────────────────────────
# extract_business_rules
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractBusinessRules:
    def test_exclude_may_month(self):
        text = "As per policy, we should exclude May month profit from the annual total."
        rules = extract_business_rules(text, "policy.pdf")
        assert 5 in rules["exclude_months"]
        assert rules["source_filename"] == "policy.pdf"

    def test_exclude_month_abbreviated(self):
        text = "Business rule: do not include Feb revenue in quarterly report."
        rules = extract_business_rules(text)
        assert 2 in rules["exclude_months"]

    def test_month_is_excluded_pattern(self):
        text = "January profit is excluded from the total calculation."
        rules = extract_business_rules(text)
        assert 1 in rules["exclude_months"]

    def test_multiple_months(self):
        text = "Exclude May and exclude December from profit calculations."
        rules = extract_business_rules(text)
        assert 5 in rules["exclude_months"]
        assert 12 in rules["exclude_months"]

    def test_no_exclusions_in_plain_text(self):
        text = "This is a regular sales report for Q1 2025."
        rules = extract_business_rules(text)
        assert rules["exclude_months"] == []

    def test_months_are_sorted(self):
        text = "Omit December. Do not include January."
        rules = extract_business_rules(text)
        assert rules["exclude_months"] == sorted(rules["exclude_months"])

    def test_raw_notes_populated(self):
        text = "Policy: exclude May month profit from all calculations."
        rules = extract_business_rules(text)
        assert len(rules["raw_notes"]) > 0


# ──────────────────────────────────────────────────────────────────────────────
# _is_policy_document
# ──────────────────────────────────────────────────────────────────────────────

class TestIsPolicyDocument:
    def test_policy_document_detected(self):
        text = "This document outlines the business rules for the finance team."
        assert _is_policy_document(text) is True

    def test_exclude_keyword_detected(self):
        text = "We must exclude certain months from profit reporting."
        assert _is_policy_document(text) is True

    def test_plain_sales_data_not_detected(self):
        text = "Product, Revenue, Units\nAlpha, 1000, 50\nBeta, 2000, 100"
        assert _is_policy_document(text) is False


# ──────────────────────────────────────────────────────────────────────────────
# get_session_business_rules
# ──────────────────────────────────────────────────────────────────────────────

SESSION_ID = "test-rules-session"


@pytest.fixture(autouse=True)
def clean_session():
    session_store.pop(SESSION_ID, None)
    invalidate_rules_cache(SESSION_ID)
    yield
    session_store.pop(SESSION_ID, None)
    invalidate_rules_cache(SESSION_ID)


def _seed_session(pdf_text: str | None = None, has_data: bool = True):
    files = {}
    if has_data:
        df = pd.DataFrame([
            {"date": "2025-01-15", "profit": 1000},
            {"date": "2025-05-10", "profit": 2500},
            {"date": "2025-06-20", "profit": 1500},
        ])
        files["data-file"] = {"filename": "sales.csv", "df": df, "file_type": "csv", "text": ""}
    if pdf_text is not None:
        files["policy-file"] = {"filename": "rules.pdf", "df": None, "file_type": "pdf", "text": pdf_text}
    with store_lock:
        session_store[SESSION_ID] = files


class TestGetSessionBusinessRules:
    def test_returns_none_when_no_pdf(self):
        _seed_session(pdf_text=None)
        assert get_session_business_rules(SESSION_ID) is None

    def test_returns_none_when_pdf_has_no_policy_signals(self):
        _seed_session(pdf_text="Monthly sales data summary for Q1 2025.")
        assert get_session_business_rules(SESSION_ID) is None

    def test_returns_rules_for_policy_pdf(self):
        _seed_session(pdf_text="Business rule: exclude May month profit from the total.")
        rules = get_session_business_rules(SESSION_ID)
        assert rules is not None
        assert 5 in rules["exclude_months"]
        assert rules["source_filename"] == "rules.pdf"

    def test_caches_result(self):
        _seed_session(pdf_text="Policy: omit December revenue.")
        r1 = get_session_business_rules(SESSION_ID)
        r2 = get_session_business_rules(SESSION_ID)
        assert r1 == r2

    def test_invalidate_cache_clears_result(self):
        _seed_session(pdf_text="Policy: exclude May profit.")
        get_session_business_rules(SESSION_ID)  # populate cache
        invalidate_rules_cache(SESSION_ID)
        session_store.pop(SESSION_ID, None)
        _seed_session(pdf_text=None)  # replace with no-PDF session
        assert get_session_business_rules(SESSION_ID) is None


# ──────────────────────────────────────────────────────────────────────────────
# compute_dashboard integration — policy rules applied
# ──────────────────────────────────────────────────────────────────────────────

DASH_SESSION = "test-dashboard-rules-session"


@pytest.fixture(autouse=True)
def clean_dash_session():
    session_store.pop(DASH_SESSION, None)
    invalidate_rules_cache(DASH_SESSION)
    yield
    session_store.pop(DASH_SESSION, None)
    invalidate_rules_cache(DASH_SESSION)


def _seed_dashboard_session(pdf_text: str | None = None):
    df = pd.DataFrame([
        {"date": "2025-01-15", "product": "Alpha", "profit": 1000},
        {"date": "2025-02-10", "product": "Alpha", "profit": 1200},
        {"date": "2025-05-05", "product": "Beta",  "profit": 2500},
        {"date": "2025-06-20", "product": "Beta",  "profit": 1800},
    ])
    files = {
        "data": {"filename": "sales.csv", "df": df, "file_type": "csv", "text": ""},
    }
    if pdf_text:
        files["policy"] = {"filename": "rules.pdf", "df": None, "file_type": "pdf", "text": pdf_text}
    with store_lock:
        session_store[DASH_SESSION] = files


class TestComputeDashboardWithRules:
    def test_no_rules_includes_all_months(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_dashboard_session()
        dashboard = compute_dashboard(DASH_SESSION)
        # 1000 + 1200 + 2500 + 1800 = 6500
        assert dashboard.kpi.total_revenue == pytest.approx(6500, rel=0.01)
        assert dashboard.policy_exclusions == []

    def test_rules_exclude_may_from_total(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_dashboard_session(pdf_text="Business rule: exclude May month profit from the annual total.")
        dashboard = compute_dashboard(DASH_SESSION)
        # May row (2500) should be excluded → total = 1000 + 1200 + 1800 = 4000
        assert dashboard.kpi.total_revenue == pytest.approx(4000, rel=0.01)

    def test_policy_exclusions_field_populated(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_dashboard_session(pdf_text="Policy: do not consider May profit.")
        dashboard = compute_dashboard(DASH_SESSION)
        assert len(dashboard.policy_exclusions) == 1
        excl = dashboard.policy_exclusions[0]
        assert excl.type == "month"
        assert "May" in excl.description
        assert excl.excluded_amount == pytest.approx(2500, rel=0.01)
        assert excl.source_filename == "rules.pdf"

    def test_policy_notice_in_summary(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_dashboard_session(pdf_text="Business rules: exclude May month from profit calculations.")
        dashboard = compute_dashboard(DASH_SESSION)
        assert "policy" in dashboard.summary.lower() or "per policy" in dashboard.summary.lower()
        assert "May" in dashboard.summary

    def test_zero_excluded_amount_when_no_matching_rows(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_dashboard_session(pdf_text="Policy: exclude March profit.")
        dashboard = compute_dashboard(DASH_SESSION)
        # No March rows in data — exclusion recorded with 0 amount
        excl = next((e for e in dashboard.policy_exclusions if "March" in e.description), None)
        assert excl is not None
        assert excl.excluded_amount == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# chat_graph integration — business rules applied to chatbot answers
# ──────────────────────────────────────────────────────────────────────────────

import asyncio
from app.services.chat_graph import answer_query_graph, _apply_business_rules_to_frames

CHAT_SESSION = "test-chat-rules-session"


@pytest.fixture(autouse=True)
def clean_chat_session():
    from app.services.scratchpad import delete_session_artifacts
    session_store.pop(CHAT_SESSION, None)
    invalidate_rules_cache(CHAT_SESSION)
    delete_session_artifacts(CHAT_SESSION)
    yield
    session_store.pop(CHAT_SESSION, None)
    invalidate_rules_cache(CHAT_SESSION)
    delete_session_artifacts(CHAT_SESSION)


def _seed_chat_session(pdf_text: str | None = None):
    df = pd.DataFrame([
        {"date": "2025-01-15", "product": "Alpha", "profit": 1000},
        {"date": "2025-02-10", "product": "Alpha", "profit": 1200},
        {"date": "2025-05-05", "product": "Beta",  "profit": 2500},
        {"date": "2025-06-20", "product": "Beta",  "profit": 1800},
    ])
    files = {
        "data": {"filename": "sales.csv", "df": df, "file_type": "csv", "text": ""},
    }
    if pdf_text:
        files["policy"] = {"filename": "rules.pdf", "df": None, "file_type": "pdf", "text": pdf_text}
    with store_lock:
        session_store[CHAT_SESSION] = files


class TestApplyBusinessRulesToFrames:
    def test_no_rules_returns_unchanged_frames(self):
        df = pd.DataFrame([{"date": "2025-05-01", "profit": 500}])
        frames = [{"file_id": "f1", "filename": "test.csv", "df": df}]
        filtered, ctx = _apply_business_rules_to_frames(frames, None)
        assert len(filtered[0]["df"]) == 1
        assert ctx == ""

    def test_may_rows_filtered(self):
        df = pd.DataFrame([
            {"date": "2025-01-01", "profit": 100},
            {"date": "2025-05-01", "profit": 999},
            {"date": "2025-06-01", "profit": 200},
        ])
        frames = [{"file_id": "f1", "filename": "test.csv", "df": df}]
        rules = {"exclude_months": [5], "source_filename": "rules.pdf"}
        filtered, ctx = _apply_business_rules_to_frames(frames, rules)
        assert len(filtered[0]["df"]) == 2
        assert 999 not in filtered[0]["df"]["profit"].values

    def test_policy_context_string_contains_month_name(self):
        df = pd.DataFrame([{"date": "2025-05-01", "profit": 500}])
        frames = [{"file_id": "f1", "filename": "test.csv", "df": df}]
        rules = {"exclude_months": [5], "source_filename": "policy.pdf"}
        _, ctx = _apply_business_rules_to_frames(frames, rules)
        assert "May" in ctx
        assert "policy.pdf" in ctx

    def test_multiple_months_filtered(self):
        df = pd.DataFrame([
            {"date": "2025-01-01", "profit": 100},
            {"date": "2025-05-01", "profit": 500},
            {"date": "2025-12-01", "profit": 700},
        ])
        frames = [{"file_id": "f1", "filename": "test.csv", "df": df}]
        rules = {"exclude_months": [5, 12], "source_filename": "rules.pdf"}
        filtered, ctx = _apply_business_rules_to_frames(frames, rules)
        assert len(filtered[0]["df"]) == 1
        assert "May" in ctx and "December" in ctx


class TestChatbotBusinessRulesIntegration:
    def test_no_policy_includes_may_in_stats(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_chat_session()
        msg = asyncio.get_event_loop().run_until_complete(
            answer_query_graph(CHAT_SESSION, "what is the total profit?", [])
        )
        # All rows included → total 6500
        assert "6,500" in msg.content or "6500" in msg.content

    def test_policy_excludes_may_from_chat_answer(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_chat_session(pdf_text="Business rule: exclude May month profit from the annual total.")
        msg = asyncio.get_event_loop().run_until_complete(
            answer_query_graph(CHAT_SESSION, "what is the total profit?", [])
        )
        # May row (2500) excluded → total 4000
        assert "4,000" in msg.content or "4000" in msg.content
        # Should NOT mention 6500
        assert "6,500" not in msg.content and "6500" not in msg.content

    def test_policy_note_appears_in_chat_answer(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        _seed_chat_session(pdf_text="Policy: do not include May profit.")
        msg = asyncio.get_event_loop().run_until_complete(
            answer_query_graph(CHAT_SESSION, "what is the total profit?", [])
        )
        lower = msg.content.lower()
        assert "may" in lower or "policy" in lower or "excluded" in lower
