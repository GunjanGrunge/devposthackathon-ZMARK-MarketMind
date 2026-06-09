"""
Session-scoped artifact store for ZScratchpad.

Stores transient chart/report data (Plotly JSON, summaries) keyed by (session_id, report_id).
Thread-safe via global lock and persisted to disk until the session is explicitly cleared.
"""
from __future__ import annotations

import copy
import pickle
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_store: Dict[str, Dict[str, Dict[str, Any]]] = {}
_lock = threading.Lock()
SCRATCHPAD_CACHE_DIR = Path(__file__).resolve().parents[2] / ".scratchpad_cache"


def _safe_session_id(session_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", session_id)


def _session_cache_dir(session_id: str) -> Path:
    return SCRATCHPAD_CACHE_DIR / _safe_session_id(session_id)


def _artifact_cache_path(session_id: str, report_id: str) -> Path:
    safe_report_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", report_id)
    return _session_cache_dir(session_id) / f"{safe_report_id}.pkl"


def save_artifact(session_id: str, artifact: Dict[str, Any]) -> str:
    """Save an artifact to the session scratchpad and return the report ID."""
    report_id = f"rpt_{uuid.uuid4().hex[:8]}"
    artifact_copy = copy.deepcopy(artifact)
    with _lock:
        if session_id not in _store:
            _store[session_id] = {}
        _store[session_id][report_id] = artifact_copy

    cache_dir = _session_cache_dir(session_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _artifact_cache_path(session_id, report_id)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("wb") as handle:
        pickle.dump(artifact_copy, handle)
    tmp_path.replace(path)
    return report_id


def get_artifact(session_id: str, report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an artifact from the session scratchpad. Returns None if not found."""
    with _lock:
        artifact = _store.get(session_id, {}).get(report_id)
        if artifact is not None:
            return copy.deepcopy(artifact)

    path = _artifact_cache_path(session_id, report_id)
    if not path.exists():
        return None

    with path.open("rb") as handle:
        artifact = pickle.load(handle)

    with _lock:
        if session_id not in _store:
            _store[session_id] = {}
        _store[session_id][report_id] = copy.deepcopy(artifact)
    return copy.deepcopy(artifact)


def delete_session_artifacts(session_id: str) -> None:
    """Delete all artifacts for a session."""
    with _lock:
        _store.pop(session_id, None)
    cache_dir = _session_cache_dir(session_id)
    if cache_dir.exists():
        import shutil

        shutil.rmtree(cache_dir, ignore_errors=True)
