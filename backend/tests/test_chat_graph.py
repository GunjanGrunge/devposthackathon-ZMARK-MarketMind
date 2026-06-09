import pytest
import pandas as pd

from app.services.chat_graph import answer_query_graph
from app.services.eda import session_store
from app.core.config import settings
from app.services.scratchpad import delete_session_artifacts, get_artifact


@pytest.fixture(autouse=True)
def clear_test_session():
    session_store.pop("chat-test", None)
    delete_session_artifacts("chat-test")
    yield
    session_store.pop("chat-test", None)
    delete_session_artifacts("chat-test")


@pytest.mark.asyncio
async def test_langgraph_chat_answers_top_selling_product(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    df = pd.read_csv("../uploads/sales_analytics_demo.csv")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales_analytics_demo.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "which product is selling the most?", [])

    assert "Based on your uploaded data" in message.content
    assert "PS5 DualSense" in message.content
    assert message.citations


@pytest.mark.asyncio
async def test_langgraph_chat_answers_top_revenue_product(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    df = pd.read_csv("../uploads/sales_analytics_demo.csv")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales_analytics_demo.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "which product has the most revenue?", [])

    assert "Based on your uploaded data" in message.content
    assert "RTX 4070" in message.content
    assert message.citations


@pytest.mark.asyncio
async def test_langgraph_chat_answers_mean_sales(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales.csv",
            "df": pd.DataFrame(
                [
                    {"order_date": "2025-01-01", "product_name": "Alpha", "revenue": 10, "channel": "Online"},
                    {"order_date": "2025-01-02", "product_name": "Beta", "revenue": 20, "channel": "Retail"},
                    {"order_date": "2025-01-03", "product_name": "Gamma", "revenue": 30, "channel": "Online"},
                ]
            ),
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "what is the mean for sales?", [])

    assert "Based on your uploaded data" in message.content
    assert "mean revenue" in message.content
    assert "$20" in message.content
    assert "overall sales across all channels" in message.content
    assert "Break this down by channel" in message.followups
    assert message.citations


@pytest.mark.asyncio
async def test_langgraph_chat_answers_grouped_statistical_inference(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales.csv",
            "df": pd.DataFrame(
                [
                    {"product_name": "Chair", "revenue": 100},
                    {"product_name": "Chair", "revenue": 160},
                    {"product_name": "Phone", "revenue": 20},
                    {"product_name": "Phone", "revenue": 80},
                    {"product_name": "Printer", "revenue": 50},
                    {"product_name": "Printer", "revenue": 50},
                ]
            ),
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "what is the std dev for sales of each product", [])

    assert "Based on your uploaded data" in message.content
    assert "sample standard deviation" in message.content
    assert "by product_name" in message.content
    assert "Chair" in message.content
    assert "Phone" in message.content
    assert "leads with" not in message.content
    assert message.citations
    assert message.citations[0].ref == "sample standard deviation revenue"
    assert "Create a chart" in message.followups[0]


@pytest.mark.asyncio
async def test_langgraph_chat_answers_sales_for_month_with_followup_ideas(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales.csv",
            "df": pd.DataFrame(
                [
                    {"order_date": "2025-01-01", "product_name": "Alpha", "revenue": 100, "channel": "Online"},
                    {"order_date": "2025-01-12", "product_name": "Beta", "revenue": 200, "channel": "Retail"},
                    {"order_date": "2025-02-01", "product_name": "Gamma", "revenue": 999, "channel": "Online"},
                ]
            ),
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "what were sales for Jan 2025?", [])

    assert "January 2025" in message.content
    assert "$300" in message.content
    assert "current year" in message.content
    assert "specific channel" in message.content
    assert "Break this down by channel" in message.followups
    assert message.citations


@pytest.mark.asyncio
async def test_langgraph_chat_retrieves_policy_pdf_from_session_memory(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store["chat-test"] = {
        "p1": {
            "filename": "returns_policy.pdf",
            "df": None,
            "file_type": "pdf",
            "text": "Returns require approval within 30 days. Damaged items need a support ticket.",
            "elastic_status": "local-only",
        }
    }

    message = await answer_query_graph("chat-test", "what is the return policy approval window?", [])

    assert "Based on your uploaded data" in message.content
    assert "30 days" in message.content
    assert message.citations
    assert message.citations[0].source == "returns_policy.pdf"


@pytest.mark.asyncio
async def test_langgraph_creates_histogram_scratchpad_for_filtered_product(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    df = pd.read_csv("../uploads/sales_analytics_demo.csv")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales_analytics_demo.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "can you create a histogram for sales of NVMe SSD 2TB", [])

    assert message.scratchpad_link
    assert message.scratchpad_link.startswith("/ui/scratchpad/")
    assert "histogram" in message.content.lower()
    assert "NVMe SSD 2TB" in message.content
    report_id = message.scratchpad_link.rsplit("/", 1)[-1]
    artifact = get_artifact("chat-test", report_id)
    assert artifact["type"] == "histogram"
    assert artifact["metadata"]["metric"] == "revenue"
    assert artifact["metadata"]["filter"] == "product_name=NVMe SSD 2TB"
    assert artifact["chart"]["data"][0]["type"] == "histogram"


@pytest.mark.asyncio
async def test_langgraph_routes_misspelled_histogram_to_visualization(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    df = pd.read_csv("../uploads/sales_analytics_demo.csv")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales_analytics_demo.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "can you crate a histoghram for sales of nvme ssd 2tb", [])

    assert message.scratchpad_link
    assert message.scratchpad_link.startswith("/ui/scratchpad/")
    assert "histogram" in message.content.lower()
    report_id = message.scratchpad_link.rsplit("/", 1)[-1]
    artifact = get_artifact("chat-test", report_id)
    assert artifact["type"] == "histogram"
    assert artifact["metadata"]["filter"] == "product_name=NVMe SSD 2TB"


@pytest.mark.asyncio
async def test_langgraph_creates_pie_chart_scratchpad(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    df = pd.read_csv("../uploads/sales_analytics_demo.csv")
    session_store["chat-test"] = {
        "f1": {
            "filename": "sales_analytics_demo.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    message = await answer_query_graph("chat-test", "create a pie chart of sales by channel", [])

    assert message.scratchpad_link
    assert message.scratchpad_link.startswith("/ui/scratchpad/")
    assert "pie" in message.content.lower()
    report_id = message.scratchpad_link.rsplit("/", 1)[-1]
    artifact = get_artifact("chat-test", report_id)
    assert artifact["type"] == "pie"
    assert artifact["metadata"]["dimension"] == "channel"
    assert artifact["chart"]["data"][0]["type"] == "pie"
