from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, Optional

_store: Dict[str, Dict[str, Dict[str, Any]]] = {}
_lock = threading.Lock()


def save_artifact(session_id: str, artifact: Dict[str, Any]) -> str:
    """Save an artifact to the session scratchpad and return the report ID."""
    report_id = f"rpt_{uuid.uuid4().hex[:8]}"
    with _lock:
        if session_id not in _store:
            _store[session_id] = {}
        _store[session_id][report_id] = artifact
    return report_id


def get_artifact(session_id: str, report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an artifact from the session scratchpad. Returns None if not found."""
    with _lock:
        return _store.get(session_id, {}).get(report_id)


def delete_session_artifacts(session_id: str) -> None:
    """Delete all artifacts for a session."""
    with _lock:
        _store.pop(session_id, None)
