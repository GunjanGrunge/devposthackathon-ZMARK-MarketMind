from fastapi.testclient import TestClient
from app.main import app
from app.services.scratchpad import save_artifact, _store

client = TestClient(app)


def test_get_artifact_returns_200():
    # Clear store before test
    _store.clear()

    artifact = {
        "type": "histogram",
        "title": "RTX 3050 Revenue",
        "chart": {"data": [], "layout": {}},
        "summary": "Test",
        "metadata": {"product": "RTX 3050"},
    }
    report_id = save_artifact("sess-route-001", artifact)
    resp = client.get(f"/api/v1/scratchpad/sess-route-001/{report_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_id"] == report_id
    assert data["title"] == "RTX 3050 Revenue"

    # Clean up
    _store.clear()


def test_get_missing_artifact_returns_404():
    # Clear store before test
    _store.clear()

    resp = client.get("/api/v1/scratchpad/sess-route-001/rpt_missing")
    assert resp.status_code == 404
