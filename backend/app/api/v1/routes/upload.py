import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Header, status
from fastapi.responses import JSONResponse
from app.schemas.upload import UploadResponse, SchemaResponse
from app.services.eda import EDAService, ensure_session_loaded, normalize_filename, session_store, store_lock

router = APIRouter()
logger = logging.getLogger("upload")

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_FILES_PER_SESSION = 10
SUPPORTED_EXTENSIONS = {"csv", "xlsx", "xls", "xlsm", "xlsb", "xltx", "xltm", "ods", "xl", "pdf"}

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    try:
        if not x_session_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "missing_session_id",
                    "message": "X-Session-ID header is required"
                }
            )

        # Read content to check file size
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "file_too_large",
                    "message": "Max 50MB per file"
                }
            )

        # Validate file extension
        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_EXTENSIONS:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": "unsupported_file_type",
                    "message": "Supported files: CSV, XLSX, XLS, XLSM, XLSB, XLTX, XLTM, ODS, and PDF"
                }
            )

        normalized_filename = normalize_filename(filename)
        ensure_session_loaded(x_session_id)
        with store_lock:
            session_files = session_store.get(x_session_id, {})
            is_replacement = any(
                normalize_filename(existing.get("filename", "")) == normalized_filename
                for existing in session_files.values()
            )
            if not is_replacement and len(session_files) >= MAX_FILES_PER_SESSION:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={
                        "error": "max_files_reached",
                        "message": f"Maximum {MAX_FILES_PER_SESSION} files per session reached"
                    }
                )

        file_id = str(uuid.uuid4())
        result = EDAService.parse_file(
            session_id=x_session_id,
            file_id=file_id,
            filename=filename,
            content=content
        )
        return UploadResponse(**result)
    except Exception as e:
        logger.exception("Upload failed for session %s", x_session_id)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "parsing_error",
                "message": f"Failed to parse file: {str(e)}"
            }
        )

@router.get("/upload/{file_id}/schema", response_model=SchemaResponse)
async def get_file_schema(
    file_id: str,
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "missing_session_id",
                "message": "X-Session-ID header is required"
            }
        )

    try:
        columns = EDAService.get_schema(session_id=x_session_id, file_id=file_id)
        return SchemaResponse(file_id=file_id, columns=columns)
    except KeyError as ke:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "file_not_found",
                "message": str(ke).strip("'")
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": f"Failed to retrieve schema: {str(e)}"
            }
        )
