from fastapi import APIRouter, Header, status
from fastapi.responses import JSONResponse
from app.schemas.analytics import (
    DashboardResponse, SessionFilesResponse, SessionFile,
    ObsolescenceResponse, BudgetResponse, MonteCarloRequest, MonteCarloResponse,
)
from app.services.analytics import (
    compute_dashboard,
    compute_obsolescence,
    compute_budget_recommendations,
    compute_monte_carlo_simulation,
)
from app.services.analysis_context import invalidate_analysis_context
from app.services.eda import clear_session_from_disk, ensure_session_loaded, session_store, store_lock
from app.services.elastic import ElasticsearchService
from app.services.scratchpad import delete_session_artifacts

router = APIRouter()


@router.get("/session/files", response_model=SessionFilesResponse)
async def list_session_files(
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Returns the list of files indexed in the current session."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )

    ensure_session_loaded(x_session_id)
    with store_lock:
        session_files = dict(session_store.get(x_session_id, {}))

    files = []
    for fid, fdata in session_files.items():
        df = fdata.get("df")
        file_type = fdata.get("file_type", "csv")
        row_count = len(df) if df is not None else None
        page_count = len(fdata.get("text", "").split("\n")) if fdata.get("text") else None

        # Rough size estimate
        size_bytes = len(fdata.get("text", "").encode()) if fdata.get("text") else (
            df.memory_usage(deep=True).sum() if df is not None else 0
        )
        size_str = f"{size_bytes // 1024} KB" if size_bytes < 1_048_576 else f"{size_bytes // 1_048_576} MB"

        files.append(SessionFile(
            id=fid,
            name=fdata["filename"],
            type=file_type,
            size=size_str,
            rows=row_count,
            pages=page_count,
            status=fdata.get("elastic_status", "indexed"),
        ))

    return SessionFilesResponse(session_id=x_session_id, files=files)


@router.delete("/session")
async def clear_session(
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Clears the current session from memory and drops its Elastic index."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )

    with store_lock:
        removed_files = len(session_store.pop(x_session_id, {}))

    clear_session_from_disk(x_session_id)
    delete_session_artifacts(x_session_id)
    invalidate_analysis_context(x_session_id)
    elastic_index_deleted = ElasticsearchService.delete_session_index(x_session_id)
    return {
        "session_id": x_session_id,
        "cleared": True,
        "files_removed": removed_files,
        "elastic_index_deleted": elastic_index_deleted,
    }


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Computes and returns full dashboard analytics for the current session."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )

    try:
        result = compute_dashboard(x_session_id)
        return result
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "analytics_error", "message": str(e)}
        )


@router.get("/power/obsolescence", response_model=ObsolescenceResponse)
async def get_obsolescence(
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Returns risk-scored obsolescence radar data for every product in the session."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )
    try:
        return compute_obsolescence(x_session_id)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "obsolescence_error", "message": str(e)}
        )


@router.get("/power/budget-recommendations", response_model=BudgetResponse)
async def get_budget_recommendations(
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Returns ROI-ranked budget reallocation recommendations for the session."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )
    try:
        return compute_budget_recommendations(x_session_id)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "budget_error", "message": str(e)}
        )


@router.get("/power/test-route")
async def test_route():
    """Test route to verify routing is working."""
    return {"test": "route_works"}


@router.post("/power/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo(
    body: MonteCarloRequest,
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """Runs a Monte Carlo simulation agent against the current session data."""
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )
    try:
        return compute_monte_carlo_simulation(
            session_id=x_session_id,
            product=body.product,
            budget_change_pct=body.budget_change_pct,
            horizon_days=body.horizon_days,
            simulations=body.simulations,
        )
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "monte_carlo_input_error", "message": str(e)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "monte_carlo_error", "message": str(e)}
        )
