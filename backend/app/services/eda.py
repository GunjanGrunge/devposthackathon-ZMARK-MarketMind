import io
import logging
import pickle
import re
import threading
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import pdfplumber
from app.schemas.upload import ColumnSchema
from app.services.elastic import ElasticsearchService

logger = logging.getLogger("eda")

# Thread-safe global session storage
# Format: session_store[session_id][file_id] = {
#     "df": DataFrame (or None for PDFs),
#     "text": str (for PDFs),
#     "filename": str,
#     "file_type": str
# }
session_store: Dict[str, Dict[str, Any]] = {}
store_lock = threading.Lock()
SESSION_CACHE_DIR = Path(__file__).resolve().parents[2] / ".session_cache"

def _session_cache_path(session_id: str) -> Path:
    safe_session_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", session_id)
    return SESSION_CACHE_DIR / f"{safe_session_id}.pkl"

def _stable_dataframe_for_pickle(df: pd.DataFrame) -> pd.DataFrame:
    """Avoid pandas extension arrays that can fail across Python/pandas runtimes."""
    stable = df.copy()
    for col in stable.columns:
        try:
            if pd.api.types.is_extension_array_dtype(stable[col].dtype):
                stable[col] = stable[col].astype(object)
        except Exception:
            stable[col] = stable[col].astype(object)
    return stable

def _stable_session_for_pickle(session_data: Dict[str, Any]) -> Dict[str, Any]:
    stable_session: Dict[str, Any] = {}
    for file_id, file_data in session_data.items():
        stable_file = dict(file_data)
        df = stable_file.get("df")
        if isinstance(df, pd.DataFrame):
            stable_file["df"] = _stable_dataframe_for_pickle(df)
        stable_session[file_id] = stable_file
    return stable_session

def save_session_to_disk(session_id: str) -> None:
    """Persists the current in-memory session until the user explicitly clears it."""
    SESSION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_cache_path(session_id)
    tmp_path = path.with_suffix(".tmp")
    with store_lock:
        session_data = _stable_session_for_pickle(session_store.get(session_id, {}))
    with tmp_path.open("wb") as handle:
        pickle.dump(session_data, handle)
    tmp_path.replace(path)

def ensure_session_loaded(session_id: str) -> None:
    """Loads a persisted session into memory if it is not already present."""
    with store_lock:
        if session_id in session_store:
            return

    path = _session_cache_path(session_id)
    if not path.exists():
        return

    try:
        with path.open("rb") as handle:
            session_data = pickle.load(handle)
    except Exception as exc:
        logger.warning("Ignoring incompatible session cache %s: %s", path, exc)
        try:
            corrupt_path = path.with_suffix(".corrupt")
            path.replace(corrupt_path)
        except Exception:
            try:
                path.unlink()
            except Exception:
                pass
        with store_lock:
            session_store.setdefault(session_id, {})
        return
    with store_lock:
        session_store.setdefault(session_id, session_data)

def clear_session_from_disk(session_id: str) -> None:
    """Deletes the persisted session cache for an explicit clear-session action."""
    path = _session_cache_path(session_id)
    if path.exists():
        path.unlink()

def normalize_filename(filename: str) -> str:
    return filename.strip().lower()

def clean_column_name(col: Any) -> str:
    """Helper to clean column names to snake_case or clean strings."""
    return str(col).strip().lower()

def _dedupe_columns(columns: List[Any]) -> List[str]:
    seen: Dict[str, int] = {}
    cleaned: List[str] = []
    for index, col in enumerate(columns, start=1):
        name = str(col).strip() if pd.notna(col) and str(col).strip() else f"column_{index}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        cleaned.append(name if count == 0 else f"{name}_{count + 1}")
    return cleaned

def _infer_excel_header_row(raw: pd.DataFrame) -> int:
    header_keywords = {
        "date", "time", "month", "period", "product", "sku", "item", "name",
        "category", "segment", "channel", "region", "sales", "revenue", "amount",
        "price", "cost", "profit", "units", "quantity", "qty",
    }
    best_row = 0
    best_score = -1
    for row_index in range(min(len(raw), 25)):
        values = [value for value in raw.iloc[row_index].tolist() if pd.notna(value) and str(value).strip()]
        if len(values) < 2:
            continue
        text_values = [str(value).strip().lower() for value in values]
        text_count = sum(1 for value in values if not isinstance(value, (int, float)))
        keyword_count = sum(
            1
            for value in text_values
            if any(keyword in value for keyword in header_keywords)
        )
        score = len(values) + (text_count * 2) + (keyword_count * 4)
        if score > best_score:
            best_score = score
            best_row = row_index
    return best_row

def _read_excel_sheet(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    raw = pd.read_excel(workbook, sheet_name=sheet_name, header=None)
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return raw

    header_row = _infer_excel_header_row(raw)
    columns = _dedupe_columns(raw.iloc[header_row].tolist())
    sheet_df = raw.iloc[header_row + 1:].copy()
    sheet_df.columns = columns
    sheet_df = sheet_df.dropna(how="all").dropna(axis=1, how="all")
    return sheet_df

def _detect_spreadsheet_format(content: bytes, ext: str) -> str:
    if ext != "xl":
        return ext
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "xls"
    if content.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "xl/workbook.bin" in names:
                    return "xlsb"
                if "mimetype" in names:
                    mimetype = archive.read("mimetype").decode("utf-8", errors="ignore")
                    if "opendocument.spreadsheet" in mimetype:
                        return "ods"
                return "xlsx"
        except zipfile.BadZipFile:
            pass
    raise ValueError("Unable to identify the spreadsheet format for .xl file")

def _spreadsheet_engine(ext: str) -> str:
    if ext in {"xlsx", "xlsm", "xltx", "xltm"}:
        return "openpyxl"
    if ext == "xls":
        return "xlrd"
    if ext == "xlsb":
        return "pyxlsb"
    if ext == "ods":
        return "odf"
    raise ValueError(f"Unsupported spreadsheet format: {ext}")

def _read_excel_workbook(content: bytes, ext: str) -> pd.DataFrame:
    """Reads every non-empty worksheet into one dataframe, preserving sheet provenance."""
    detected_ext = _detect_spreadsheet_format(content, ext)
    engine = _spreadsheet_engine(detected_ext)
    workbook = pd.ExcelFile(io.BytesIO(content), engine=engine)
    frames: List[pd.DataFrame] = []
    for sheet_name in workbook.sheet_names:
        sheet_df = _read_excel_sheet(workbook, sheet_name)
        if sheet_df.empty:
            continue
        if len(workbook.sheet_names) > 1:
            sheet_df.insert(0, "__sheet_name", sheet_name)
        frames.append(sheet_df)
    if not frames:
        raise ValueError("Excel workbook does not contain any non-empty sheets")
    return pd.concat(frames, ignore_index=True, sort=False)

def is_date_column(col_series: pd.Series, col_name: str) -> bool:
    """Heuristic to determine if a column is a date."""
    col_name_clean = col_name.lower()
    if any(k in col_name_clean for k in ["date", "time", "timestamp"]):
        return True
    
    sampled = col_series.dropna()
    if sampled.empty:
        return False
    
    if pd.api.types.is_numeric_dtype(sampled.dtype):
        return False
        
    try:
        # Take a sample to test parsing
        sample = sampled.head(20).astype(str)
        if sample.str.isdigit().all():
            return False
        pd.to_datetime(sample, errors="raise")
        return True
    except Exception:
        return False

def detect_column_schema(col_name: str, col_series: pd.Series) -> ColumnSchema:
    """Runs heuristics to identify the column type, role, and confidence."""
    col_name_lower = col_name.lower()
    unique_count = col_series.nunique()
    is_numeric = pd.api.types.is_numeric_dtype(col_series.dtype)

    # 1. Date Column Heuristic
    if is_date_column(col_series, col_name):
        return ColumnSchema(
            name=col_name,
            type="date",
            role="Date",
            confidence=0.98
        )

    # 2. Revenue Column Heuristic
    if is_numeric:
        revenue_keywords = ["revenue", "sales", "amount", "price", "total"]
        if any(keyword in col_name_lower for keyword in revenue_keywords):
            return ColumnSchema(
                name=col_name,
                type="currency",
                role="Revenue",
                confidence=0.97
            )

    # 3. Product Column Heuristic
    if not is_numeric:
        product_keywords = ["product", "item", "sku", "name"]
        if any(keyword in col_name_lower for keyword in product_keywords) and 5 <= unique_count <= 100:
            return ColumnSchema(
                name=col_name,
                type="string",
                role="Product",
                confidence=0.96
            )

    # 4. Category Column Heuristic
    if not is_numeric:
        category_keywords = ["category", "cat", "group", "type"]
        if any(keyword in col_name_lower for keyword in category_keywords) and unique_count < 50:
            return ColumnSchema(
                name=col_name,
                type="string",
                role="Category",
                confidence=0.93
            )

    # Fallbacks
    if is_numeric:
        return ColumnSchema(
            name=col_name,
            type="numeric",
            role="Metric",
            confidence=0.80
        )
    else:
        return ColumnSchema(
            name=col_name,
            type="string",
            role="Dimension",
            confidence=0.80
        )

class EDAService:
    @staticmethod
    def parse_file(session_id: str, file_id: str, filename: str, content: bytes) -> Dict[str, Any]:
        """Parses CSV, Excel, or PDF files and stores them in session cache."""
        ext = filename.split(".")[-1].lower()
        df = None
        text_content = ""
        row_count = None
        page_count = None
        pages_text = []

        if ext == "csv":
            df = pd.read_csv(io.BytesIO(content))
            row_count = len(df)
            file_type = "csv"
        elif ext in {"xlsx", "xls", "xlsm", "xlsb", "xltx", "xltm", "ods", "xl"}:
            df = _read_excel_workbook(content, ext)
            row_count = len(df)
            file_type = _detect_spreadsheet_format(content, ext)
        elif ext == "pdf":
            file_type = "pdf"
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                page_count = len(pdf.pages)
                for p in pdf.pages:
                    txt = p.extract_text()
                    pages_text.append(txt if txt else "")
            text_content = "\n".join(pages_text)
        else:
            raise ValueError("Unsupported file type")

        ElasticsearchService.delete_file_documents(session_id, filename)
        if df is not None:
            elastic_indexed = ElasticsearchService.index_structured_data(session_id, filename, df)
        else:
            elastic_indexed = ElasticsearchService.index_unstructured_data(session_id, filename, pages_text)

        # Cache in thread-safe memory store
        with store_lock:
            if session_id not in session_store:
                session_store[session_id] = {}
            normalized = normalize_filename(filename)
            duplicate_ids = [
                existing_id
                for existing_id, existing_data in session_store[session_id].items()
                if normalize_filename(existing_data.get("filename", "")) == normalized
            ]
            for existing_id in duplicate_ids:
                del session_store[session_id][existing_id]
            session_store[session_id][file_id] = {
                "df": df,
                "text": text_content,
                "filename": filename,
                "file_type": file_type,
                "elastic_status": "indexed" if elastic_indexed else "local-only",
            }
        save_session_to_disk(session_id)
        try:
            from app.services.analysis_context import invalidate_analysis_context

            invalidate_analysis_context(session_id)
        except Exception:
            pass

        return {
            "session_id": session_id,
            "file_id": file_id,
            "filename": filename,
            "file_type": file_type,
            "row_count": row_count,
            "page_count": page_count,
            "indexing_status": "complete"
        }

    @staticmethod
    def get_schema(session_id: str, file_id: str) -> List[ColumnSchema]:
        """Runs column schema heuristics for a cached DataFrame."""
        ensure_session_loaded(session_id)
        with store_lock:
            session_files = session_store.get(session_id)
            if not session_files:
                raise KeyError("Session not found")
            file_data = session_files.get(file_id)
            if not file_data:
                raise KeyError("File not found")

        df = file_data.get("df")
        if df is None:
            # PDFs or files without tabular representation don't have schemas
            return []

        columns_schema = []
        for col_name in df.columns:
            columns_schema.append(detect_column_schema(col_name, df[col_name]))

        return columns_schema
