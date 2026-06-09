import pytest
import shutil
import uuid
from pathlib import Path

from app.services import eda as eda_module
from app.services import scratchpad as scratchpad_module


@pytest.fixture(autouse=True)
def isolated_session_cache(monkeypatch):
    base_dir = Path(__file__).resolve().parents[1] / ".test_session_cache" / uuid.uuid4().hex
    monkeypatch.setattr(eda_module, "SESSION_CACHE_DIR", base_dir / "sessions")
    monkeypatch.setattr(scratchpad_module, "SCRATCHPAD_CACHE_DIR", base_dir / "scratchpad")
    yield
    shutil.rmtree(base_dir, ignore_errors=True)
