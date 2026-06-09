import pytest
from app.services.scratchpad import save_artifact, get_artifact, delete_session_artifacts, _store


@pytest.fixture(autouse=True)
def clear_store():
    """Clear the global _store before and after each test for isolation."""
    _store.clear()
    yield
    _store.clear()


def test_save_and_get_artifact():
    artifact = {
        "type": "histogram",
        "title": "RTX 3050 Sales",
        "chart": {"data": [{"type": "histogram", "x": [1, 2, 3]}], "layout": {}},
        "summary": "Test summary",
        "metadata": {},
    }
    report_id = save_artifact("sess-001", artifact)
    assert report_id.startswith("rpt_")
    result = get_artifact("sess-001", report_id)
    assert result is not None
    assert result["title"] == "RTX 3050 Sales"


def test_get_missing_artifact_returns_none():
    assert get_artifact("sess-999", "rpt_missing") is None


def test_delete_session_clears_artifacts():
    save_artifact("sess-del", {"type": "histogram", "title": "x", "chart": {}, "summary": "", "metadata": {}})
    delete_session_artifacts("sess-del")
    assert get_artifact("sess-del", "rpt_0000") is None


def test_artifact_survives_memory_reset():
    artifact = {
        "type": "pie",
        "title": "Revenue by Channel",
        "chart": {"data": [{"type": "pie", "labels": ["Online"], "values": [100]}], "layout": {}},
        "summary": "Pie chart summary",
        "metadata": {"metric": "revenue"},
    }
    report_id = save_artifact("sess-persist", artifact)

    _store.clear()
    result = get_artifact("sess-persist", report_id)

    assert result is not None
    assert result["type"] == "pie"
    assert result["title"] == "Revenue by Channel"
