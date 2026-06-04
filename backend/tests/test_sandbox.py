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
