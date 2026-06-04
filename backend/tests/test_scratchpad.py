from app.services.scratchpad import save_artifact, get_artifact, delete_session_artifacts


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
