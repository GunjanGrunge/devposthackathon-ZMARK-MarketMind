import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.services.eda import session_store
from app.services import eda as eda_module
from app.services.scratchpad import get_artifact, save_artifact
from app.services.elastic import ElasticsearchService
from app.core.config import settings

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_session():
    yield
    try:
        from app.services.elastic import ElasticsearchService
        if ElasticsearchService.is_configured():
            ElasticsearchService.delete_session_index("test-session")
    except Exception:
        pass


def test_upload_missing_session_id():
    response = client.post(
        "/api/v1/upload",
        files={"file": ("test.csv", b"col1,col2\n1,2", "text/csv")}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "missing_session_id"

def test_upload_invalid_file_type():
    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "test-session"},
        files={"file": ("test.txt", b"plain text", "text/plain")}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_file_type"


@pytest.mark.parametrize("extension", ["xlsm", "xlsb", "ods", "xl"])
def test_upload_accepts_spreadsheet_extension(extension):
    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": f"extension-{extension}"},
        files={"file": (f"workbook.{extension}", b"not a workbook", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "parsing_error"


def test_upload_file_too_large():
    # Construct a 51MB payload
    large_payload = b"0" * (50 * 1024 * 1024 + 10)
    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "test-session"},
        files={"file": ("test.csv", large_payload, "text/csv")}
    )
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"

def test_upload_valid_csv():
    csv_content = (
        "order_date,product_name,category,revenue,units_sold\n"
        "2026-06-01,RTX 4070,GPUs,84200,42\n"
        "2026-06-02,PS5 DualSense,Accessories,62400,38\n"
        "2026-06-03,Gaming Monitor 27,Displays,51800,24\n"
        "2026-06-04,Mech Keyboard TKL,Peripherals,38600,31\n"
        "2026-06-05,NVMe SSD 2TB,Storage,33200,19\n"
    )
    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "test-session"},
        files={"file": ("sales.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session"
    assert data["file_type"] == "csv"
    assert data["row_count"] == 5
    assert data["indexing_status"] == "complete"
    assert "file_id" in data
    
    file_id = data["file_id"]
    
    # Verify schema detection endpoint
    schema_response = client.get(
        f"/api/v1/upload/{file_id}/schema",
        headers={"X-Session-ID": "test-session"}
    )
    assert schema_response.status_code == 200
    schema_data = schema_response.json()
    assert schema_data["file_id"] == file_id
    columns = {col["name"]: col for col in schema_data["columns"]}
    
    # Assert roles based on schema rules
    assert columns["order_date"]["role"] == "Date"
    assert columns["product_name"]["role"] == "Product"
    assert columns["category"]["role"] == "Category"
    assert columns["revenue"]["role"] == "Revenue"
    assert columns["units_sold"]["role"] == "Metric"


def test_upload_valid_xlsx_reads_all_sheets_and_indexes(monkeypatch):
    session_store.pop("xlsx-session", None)
    indexed = []
    monkeypatch.setattr(ElasticsearchService, "delete_file_documents", lambda session_id, filename: True)
    monkeypatch.setattr(
        ElasticsearchService,
        "index_structured_data",
        lambda session_id, filename, df: indexed.append((session_id, filename, df.copy())) or True,
    )

    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"order_date": pd.Timestamp("2026-06-01"), "product_name": "Alpha", "revenue": 100},
                {"order_date": pd.Timestamp("2026-06-02"), "product_name": "Beta", "revenue": 200},
            ]
        ).to_excel(writer, sheet_name="North", index=False)
        pd.DataFrame(
            [{"order_date": pd.Timestamp("2026-06-03"), "product_name": "Gamma", "revenue": 300}]
        ).to_excel(writer, sheet_name="South", index=False)

    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "xlsx-session"},
        files={
            "file": (
                "sales.xlsx",
                workbook.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_type"] == "xlsx"
    assert data["row_count"] == 3
    assert indexed
    indexed_df = indexed[0][2]
    assert indexed_df["__sheet_name"].tolist() == ["North", "North", "South"]
    assert set(indexed_df["product_name"]) == {"Alpha", "Beta", "Gamma"}


def test_upload_valid_xlsm_uses_excel_ingestion(monkeypatch):
    session_store.pop("xlsm-session", None)
    monkeypatch.setattr(ElasticsearchService, "delete_file_documents", lambda session_id, filename: True)
    monkeypatch.setattr(ElasticsearchService, "index_structured_data", lambda session_id, filename, df: True)

    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [{"order_date": pd.Timestamp("2026-06-01"), "product_name": "Alpha", "revenue": 100}]
        ).to_excel(writer, index=False)

    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "xlsm-session"},
        files={
            "file": (
                "sales.xlsm",
                workbook.getvalue(),
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["file_type"] == "xlsm"
    assert response.json()["row_count"] == 1


def test_upload_xlsx_with_title_rows_infers_header(monkeypatch):
    session_store.pop("xlsx-title-session", None)
    indexed = []
    monkeypatch.setattr(ElasticsearchService, "delete_file_documents", lambda session_id, filename: True)
    monkeypatch.setattr(
        ElasticsearchService,
        "index_structured_data",
        lambda session_id, filename, df: indexed.append(df.copy()) or True,
    )

    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["Sales Export", None, None],
                [None, None, None],
                ["order_date", "product_name", "revenue"],
                [pd.Timestamp("2026-06-01"), "Alpha", 100],
                [pd.Timestamp("2026-06-02"), "Beta", 200],
            ]
        ).to_excel(writer, sheet_name="Sales", index=False, header=False)

    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "xlsx-title-session"},
        files={
            "file": (
                "sales-title.xlsx",
                workbook.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["row_count"] == 2
    assert indexed
    assert indexed[0]["product_name"].tolist() == ["Alpha", "Beta"]
    assert indexed[0]["revenue"].tolist() == [100, 200]


def test_upload_valid_pdf():
    # Minimal valid PDF structure
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 712 Td (Hello PDF World) Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000213 00000 n\n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\n"
        b"startxref\n308\n%%EOF"
    )

    response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "test-session"},
        files={"file": ("document.pdf", pdf_content, "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session"
    assert data["file_type"] == "pdf"
    assert data["page_count"] == 1


def test_upload_same_filename_replaces_existing_session_file(monkeypatch):
    session_store.pop("duplicate-session", None)
    elastic_calls = []
    monkeypatch.setattr(
        ElasticsearchService,
        "delete_file_documents",
        lambda session_id, filename: elastic_calls.append(("delete", session_id, filename)) or True,
    )
    monkeypatch.setattr(
        ElasticsearchService,
        "index_structured_data",
        lambda session_id, filename, df: elastic_calls.append(("index", session_id, filename)) or True,
    )
    first_csv = "order_date,product_name,revenue\n2026-06-01,Old Product,100\n"
    second_csv = "order_date,product_name,revenue\n2026-06-02,New Product,500\n"

    first = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "duplicate-session"},
        files={"file": ("sales.csv", first_csv.encode("utf-8"), "text/csv")},
    )
    second = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "duplicate-session"},
        files={"file": ("sales.csv", second_csv.encode("utf-8"), "text/csv")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(session_store["duplicate-session"]) == 1
    remaining = next(iter(session_store["duplicate-session"].values()))
    assert remaining["filename"] == "sales.csv"
    assert remaining["df"]["product_name"].iloc[0] == "New Product"
    assert elastic_calls == [
        ("delete", "duplicate-session", "sales.csv"),
        ("index", "duplicate-session", "sales.csv"),
        ("delete", "duplicate-session", "sales.csv"),
        ("index", "duplicate-session", "sales.csv"),
    ]


def test_upload_max_files_reached_but_replacement_allowed(monkeypatch):
    monkeypatch.setattr(ElasticsearchService, "delete_file_documents", lambda session_id, filename: False)
    monkeypatch.setattr(ElasticsearchService, "index_structured_data", lambda session_id, filename, df: False)
    session_store["limit-session"] = {
        f"id-{i}": {
            "filename": f"file-{i}.csv",
            "df": pd.DataFrame([{"revenue": i}]),
            "text": "",
            "file_type": "csv",
        }
        for i in range(10)
    }

    new_response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "limit-session"},
        files={"file": ("extra.csv", b"revenue\n100\n", "text/csv")},
    )
    assert new_response.status_code == 422
    assert new_response.json()["error"] == "max_files_reached"

    replacement_response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "limit-session"},
        files={"file": ("file-0.csv", b"revenue\n200\n", "text/csv")},
    )
    assert replacement_response.status_code == 200
    assert len(session_store["limit-session"]) == 10


def test_clear_session_removes_memory_and_elastic_index(monkeypatch):
    deleted = []
    monkeypatch.setattr(
        ElasticsearchService,
        "delete_session_index",
        lambda session_id: deleted.append(session_id) or True,
    )
    session_store["clear-session"] = {
        "file-1": {
            "filename": "policy.pdf",
            "df": None,
            "text": "policy text",
            "file_type": "pdf",
        }
    }
    report_id = save_artifact(
        "clear-session",
        {"type": "pie", "title": "x", "chart": {}, "summary": "", "metadata": {}},
    )

    response = client.delete(
        "/api/v1/session",
        headers={"X-Session-ID": "clear-session"},
    )

    assert response.status_code == 200
    assert response.json()["files_removed"] == 1
    assert response.json()["elastic_index_deleted"] is True
    assert "clear-session" not in session_store
    assert deleted == ["clear-session"]
    assert get_artifact("clear-session", report_id) is None


def test_session_files_survive_memory_reset_from_disk(monkeypatch):
    monkeypatch.setattr(ElasticsearchService, "delete_file_documents", lambda session_id, filename: False)
    monkeypatch.setattr(ElasticsearchService, "index_structured_data", lambda session_id, filename, df: False)
    session_store.pop("persist-session", None)

    upload_response = client.post(
        "/api/v1/upload",
        headers={"X-Session-ID": "persist-session"},
        files={"file": ("sales.csv", b"order_date,revenue\n2025-01-01,100\n", "text/csv")},
    )
    assert upload_response.status_code == 200
    assert eda_module._session_cache_path("persist-session").exists()

    session_store.pop("persist-session", None)
    files_response = client.get(
        "/api/v1/session/files",
        headers={"X-Session-ID": "persist-session"},
    )

    assert files_response.status_code == 200
    files = files_response.json()["files"]
    assert len(files) == 1
    assert files[0]["name"] == "sales.csv"

    clear_response = client.delete(
        "/api/v1/session",
        headers={"X-Session-ID": "persist-session"},
    )
    assert clear_response.status_code == 200
    assert not eda_module._session_cache_path("persist-session").exists()


def test_session_files_ignores_incompatible_cache():
    session_id = "bad-cache-session"
    session_store.pop(session_id, None)
    path = eda_module._session_cache_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a pickle")

    files_response = client.get(
        "/api/v1/session/files",
        headers={"X-Session-ID": session_id},
    )

    assert files_response.status_code == 200
    assert files_response.json()["files"] == []
    assert not path.exists()
    session_store.pop(session_id, None)
    corrupt_path = path.with_suffix(".corrupt")
    if corrupt_path.exists():
        corrupt_path.unlink()


def test_elastic_config_uses_elastic_key(monkeypatch):
    monkeypatch.setattr(settings, "elastic_url", "https://example.es")
    monkeypatch.setattr(settings, "elastic_key", "api-key")
    monkeypatch.setattr(settings, "elastic_cluster", "")

    assert ElasticsearchService.is_configured() is True
    assert ElasticsearchService.api_key() == "api-key"


def test_elastic_safe_value_serializes_excel_scalars():
    from app.services.elastic import _elastic_safe_value

    assert _elastic_safe_value(pd.Timestamp("2026-06-01")) == "2026-06-01T00:00:00"
    assert _elastic_safe_value(pd.NA) is None
    assert _elastic_safe_value(float("nan")) is None
