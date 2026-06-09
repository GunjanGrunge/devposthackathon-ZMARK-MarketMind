import pytest
import pandas as pd

from app.services.analytics import (
    compute_budget_recommendations,
    compute_dashboard,
    compute_monte_carlo_simulation,
    compute_obsolescence,
)
from app.core.config import settings
from app.services.eda import session_store


def test_business_summary_is_specific_to_uploaded_data():
    session_store.pop("summary-session", None)


def test_dashboard_does_not_treat_geography_as_product(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("geo-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2025-01-01", "City": "New York", "State": "New York", "Segment": "Consumer", "Class": "Standard", "Sales": 100},
            {"Order Date": "2025-01-02", "City": "New York", "State": "New York", "Segment": "Consumer", "Class": "Standard", "Sales": 200},
            {"Order Date": "2025-02-01", "City": "Boston", "State": "Massachusetts", "Segment": "Corporate", "Class": "Express", "Sales": 150},
        ]
    )
    session_store["geo-session"] = {
        "f1": {
            "filename": "geo-sales.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("geo-session")

    assert dashboard.revenue_trend.labels == ["Jan '25", "Feb '25"]
    assert dashboard.products == []
    assert dashboard.channels == []
    assert dashboard.categories == []
    assert dashboard.kpi.top_product is None

    session_store.pop("geo-session", None)


def test_dashboard_prefers_real_product_category_over_segment(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("superstore-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2025-01-01", "Product Name": "Desk", "Category": "Furniture", "Segment": "Consumer", "City": "New York", "Sales": 100, "Quantity": 1},
            {"Order Date": "2025-01-02", "Product Name": "Chair", "Category": "Furniture", "Segment": "Corporate", "City": "Boston", "Sales": 300, "Quantity": 3},
            {"Order Date": "2025-02-01", "Product Name": "Paper", "Category": "Office Supplies", "Segment": "Consumer", "City": "New York", "Sales": 50, "Quantity": 5},
        ]
    )
    session_store["superstore-session"] = {
        "f1": {
            "filename": "superstore.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("superstore-session")

    assert {product.name for product in dashboard.products} == {"Desk", "Chair", "Paper"}
    assert "New York" not in {product.name for product in dashboard.products}
    assert {point.label for point in dashboard.categories} == {"Furniture", "Office Supplies"}
    assert "Consumer" not in {point.label for point in dashboard.categories}

    session_store.pop("superstore-session", None)


def test_dashboard_infers_common_sales_export_columns(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("alternate-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2025-01-03", "Product Name": "Alpha", "Category": "Hardware", "Segment": "Enterprise", "Channel": "Online", "Sales": "$1,200", "Quantity": 3},
            {"Order Date": "2025-01-18", "Product Name": "Beta", "Category": "Hardware", "Segment": "SMB", "Channel": "Retail", "Sales": "$800", "Quantity": 2},
            {"Order Date": "2025-02-02", "Product Name": "Alpha", "Category": "Hardware", "Segment": "Enterprise", "Channel": "Online", "Sales": "$1,500", "Quantity": 5},
            {"Order Date": "2025-02-14", "Product Name": "Gamma", "Category": "Software", "Segment": "SMB", "Channel": "Retail", "Sales": "$600", "Quantity": 4},
        ]
    )
    session_store["alternate-session"] = {
        "f1": {
            "filename": "export.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("alternate-session")

    assert dashboard.kpi.total_revenue == 4100
    assert dashboard.revenue_trend.labels == ["Jan '25", "Feb '25"]
    assert dashboard.revenue_trend.values == [2.0, 2.1]
    assert dashboard.products
    assert dashboard.products[0].name == "Alpha"
    assert dashboard.products[0].velocity == 8
    assert dashboard.channels
    assert dashboard.categories

    session_store.pop("alternate-session", None)


def test_business_summary_identifies_dataset_focus(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("peripheral-summary-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2026-01-01", "Product Name": "USB Mouse", "Category": "Computer Peripherals", "Channel": "Online", "Sales": 1200, "Quantity": 12},
            {"Order Date": "2026-01-02", "Product Name": "Mechanical Keyboard", "Category": "Computer Peripherals", "Channel": "Retail", "Sales": 1800, "Quantity": 8},
            {"Order Date": "2026-02-03", "Product Name": "Webcam", "Category": "Computer Peripherals", "Channel": "Online", "Sales": 900, "Quantity": 5},
        ]
    )
    session_store["peripheral-summary-session"] = {
        "f1": {
            "filename": "peripheral-sales.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("peripheral-summary-session")

    assert dashboard.summary.startswith("This dataset appears to focus on sales of Computer Peripherals")
    assert "USB Mouse" in dashboard.summary
    assert "Mechanical Keyboard" in dashboard.summary
    assert "Webcam" in dashboard.summary

    session_store.pop("peripheral-summary-session", None)


def test_power_mode_infers_alternate_sales_columns(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("power-alt-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2025-01-01", "Item": "Alpha", "Department": "Hardware", "Market": "Online", "Amount": 1200, "Qty": 8},
            {"Order Date": "2025-02-01", "Item": "Alpha", "Department": "Hardware", "Market": "Online", "Amount": 900, "Qty": 6},
            {"Order Date": "2025-03-01", "Item": "Beta", "Department": "Software", "Market": "Retail", "Amount": 400, "Qty": 5},
            {"Order Date": "2025-04-01", "Item": "Beta", "Department": "Software", "Market": "Retail", "Amount": 100, "Qty": 1},
            {"Order Date": "2025-05-01", "Item": "Gamma", "Department": "Services", "Market": "Partner", "Amount": 700, "Qty": 3},
            {"Order Date": "2025-06-01", "Item": "Gamma", "Department": "Services", "Market": "Partner", "Amount": 900, "Qty": 6},
        ]
    )
    session_store["power-alt-session"] = {
        "f1": {
            "filename": "power-export.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    obsolescence = compute_obsolescence("power-alt-session")
    budget = compute_budget_recommendations("power-alt-session")

    assert obsolescence.items
    assert {item.name for item in obsolescence.items} == {"Alpha", "Beta", "Gamma"}
    assert budget.increase
    assert budget.reduce

    session_store.pop("power-alt-session", None)


def test_monte_carlo_simulation_uses_uploaded_session_data(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("mc-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2026-01-01", "Item": "Alpha", "Amount": 100},
            {"Order Date": "2026-01-02", "Item": "Alpha", "Amount": 140},
            {"Order Date": "2026-01-03", "Item": "Alpha", "Amount": 120},
            {"Order Date": "2026-01-01", "Item": "Beta", "Amount": 500},
            {"Order Date": "2026-01-02", "Item": "Beta", "Amount": 520},
        ]
    )
    session_store["mc-session"] = {
        "f1": {
            "filename": "custom-sales.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    result = compute_monte_carlo_simulation(
        "mc-session",
        product="Alpha",
        budget_change_pct=20,
        horizon_days=30,
        simulations=1000,
    )

    assert result.product == "Alpha"
    assert result.horizon_days == 30
    assert result.simulations == 1000
    assert result.expected_revenue > result.baseline_revenue
    assert result.distribution
    assert "Alpha" in result.summary
    assert "historical revenue observations" in result.assumptions[0]

    with pytest.raises(ValueError):
        compute_monte_carlo_simulation("mc-session", product="DemoOnly")

    session_store.pop("mc-session", None)


def test_dashboard_uses_row_count_velocity_when_quantity_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    session_store.pop("no-units-session", None)
    df = pd.DataFrame(
        [
            {"Order Date": "2025-01-01", "Item": "Alpha", "Sales": 100},
            {"Order Date": "2025-01-02", "Item": "Alpha", "Sales": 120},
            {"Order Date": "2025-01-03", "Item": "Beta", "Sales": 80},
        ]
    )
    session_store["no-units-session"] = {
        "f1": {
            "filename": "orders.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("no-units-session")

    alpha = next(product for product in dashboard.products if product.name == "Alpha")
    assert alpha.velocity == 2

    session_store.pop("no-units-session", None)
    df = pd.DataFrame(
        [
            {"order_date": "2026-01-01", "product_name": "Alpha", "category": "GPUs", "channel": "Online", "revenue": 1000, "units_sold": 5},
            {"order_date": "2026-01-15", "product_name": "Alpha", "category": "GPUs", "channel": "Online", "revenue": 2000, "units_sold": 8},
            {"order_date": "2026-02-01", "product_name": "Beta", "category": "Accessories", "channel": "Retail", "revenue": 300, "units_sold": 20},
            {"order_date": "2026-02-15", "product_name": "Gamma", "category": "Displays", "channel": "Online", "revenue": 100, "units_sold": 1},
        ]
    )
    session_store["summary-session"] = {
        "f1": {
            "filename": "sales.csv",
            "df": df,
            "file_type": "csv",
            "text": "",
        }
    }

    dashboard = compute_dashboard("summary-session")

    assert "Alpha" in dashboard.summary
    assert "Gamma" in dashboard.summary
    assert "Online" in dashboard.summary
    assert "$3,400" in dashboard.summary
    assert "Use the chat assistant" not in dashboard.summary

    session_store.pop("summary-session", None)
