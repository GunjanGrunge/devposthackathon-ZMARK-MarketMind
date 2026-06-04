import pandas as pd
from app.services.sandbox import run_chart_code


def test_histogram_produces_chart_json():
    df = pd.DataFrame({"product_name": ["A", "A", "B"], "revenue": [100, 200, 150]})
    code = """
import plotly.express as px
fig = px.histogram(df, x="revenue", nbins=5, title="Revenue Distribution")
summary = f"Revenue histogram across {len(df)} rows."
"""
    result = run_chart_code(code, df)
    assert result["ok"] is True
    assert "data" in result["chart"]
    assert "Revenue Distribution" in result["summary"] or "rows" in result["summary"]


def test_dangerous_import_is_blocked():
    df = pd.DataFrame({"x": [1]})
    code = "import os; os.system('rm -rf /')\nfig = None\nsummary = ''"
    result = run_chart_code(code, df)
    assert result["ok"] is False


def test_missing_fig_returns_error():
    df = pd.DataFrame({"x": [1, 2]})
    code = "summary = 'no chart here'"  # no fig assignment
    result = run_chart_code(code, df)
    assert result["ok"] is False
    assert "fig" in result["error"].lower()


def test_non_plotly_fig_is_rejected():
    df = pd.DataFrame({"x": [1]})
    code = "fig = {'fake': 'dict'}\nsummary = ''"
    result = run_chart_code(code, df)
    assert result["ok"] is False
