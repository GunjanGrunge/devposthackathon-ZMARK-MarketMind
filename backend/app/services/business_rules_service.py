"""
business_rules_service.py — Extracts and caches policy/business rules from
PDF files uploaded to a session.

Parsed rules are applied by analytics.py when computing profit/revenue KPIs so
that policy-driven exclusions (e.g. "exclude May month") are honoured and
surfaced in the dashboard summary.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("business_rules")

# Month name → int (1-based)
_MONTH_MAP: Dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Patterns that suggest a PDF contains business / policy rules
_POLICY_SIGNALS = re.compile(
    r"\b(business rules?|policy|exclude|exclusion|not (to )?consider|disregard|"
    r"omit|shall not|should not|must not|do not include|not included)\b",
    re.I,
)

# Match "exclude <month>", "not include <month>", "omit <month>", etc.
_EXCLUDE_MONTH_PATTERN = re.compile(
    r"\b(?:exclude|excludes|excluding|not (?:to )?(?:consider|include)|"
    r"omit|omits|omitting|disregard|ignore)\b[^.]*?\b("
    + "|".join(_MONTH_MAP.keys()) + r")\b",
    re.I,
)

# Match "<month> (?:month|profit|revenue|sales) (?:is|are|will be)? excluded"
_MONTH_IS_EXCLUDED_PATTERN = re.compile(
    r"\b(" + "|".join(_MONTH_MAP.keys()) + r")\b[^.]*?\b"
    r"(?:month|profit|revenue|sales|data)?[^.]*?\b"
    r"(?:excluded|excluded from|not counted|not considered|not included)\b",
    re.I,
)

# Threaded cache: session_id → rules dict
_rules_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _is_policy_document(text: str) -> bool:
    """Returns True if the PDF text looks like a business-rules / policy document."""
    return bool(_POLICY_SIGNALS.search(text))


def extract_business_rules(text: str, source_filename: str = "policy.pdf") -> Dict[str, Any]:
    """
    Parse plain-text content from a PDF and return a structured rules dict:

    {
        "exclude_months": [5],          # list of month ints (1-12)
        "source_filename": "rules.pdf",
        "raw_notes": ["As per policy, May is excluded from profit calculations"]
    }
    """
    exclude_months: List[int] = []
    raw_notes: List[str] = []

    for pattern in (_EXCLUDE_MONTH_PATTERN, _MONTH_IS_EXCLUDED_PATTERN):
        for match in pattern.finditer(text):
            month_name = match.group(1).lower()
            month_num = _MONTH_MAP.get(month_name)
            if month_num and month_num not in exclude_months:
                exclude_months.append(month_num)
                raw_notes.append(match.group(0).strip())

    return {
        "exclude_months": sorted(exclude_months),
        "source_filename": source_filename,
        "raw_notes": raw_notes,
    }


def get_session_business_rules(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns the merged business rules extracted from all policy PDFs in the
    session, or None if no policy PDFs are present.

    Caller is responsible for loading the session (ensure_session_loaded) before
    calling this function.  Importing here would cause a circular dependency.
    """
    from app.services.eda import session_store, store_lock  # deferred import

    with store_lock:
        files = dict(session_store.get(session_id, {}))

    # Check cache: use file count + filenames as a cheap validity key
    cache_key = "|".join(
        sorted(f"{fid}:{d.get('filename')}" for fid, d in files.items())
    )
    with _cache_lock:
        cached = _rules_cache.get(session_id)
        if cached and cached.get("_cache_key") == cache_key:
            return cached if cached.get("exclude_months") else None

    merged: Dict[str, Any] = {
        "exclude_months": [],
        "source_filename": None,
        "raw_notes": [],
        "_cache_key": cache_key,
    }

    found_policy = False
    for _fid, fdata in files.items():
        if fdata.get("file_type") != "pdf":
            continue
        text: str = fdata.get("text") or ""
        if not text or not _is_policy_document(text):
            continue

        found_policy = True
        rules = extract_business_rules(text, source_filename=fdata.get("filename", "policy.pdf"))

        for m in rules["exclude_months"]:
            if m not in merged["exclude_months"]:
                merged["exclude_months"].append(m)
        merged["raw_notes"].extend(rules["raw_notes"])
        if merged["source_filename"] is None:
            merged["source_filename"] = rules["source_filename"]

    merged["exclude_months"].sort()

    with _cache_lock:
        _rules_cache[session_id] = merged

    if not found_policy or not merged["exclude_months"]:
        return None

    return merged


def invalidate_rules_cache(session_id: str) -> None:
    with _cache_lock:
        _rules_cache.pop(session_id, None)
