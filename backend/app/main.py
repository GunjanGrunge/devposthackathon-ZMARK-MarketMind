import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.upload import router as upload_router
from app.api.v1.routes.scratchpad import router as scratchpad_router


app = FastAPI(
    title="ZmaRk API Gateway",
    description="FastAPI backend for ZmaRk / MarketMind ingestion, analytics, and agent chat",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["Analytics"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(scratchpad_router, prefix="/api/v1", tags=["Scratchpad"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")
LEGACY_UI_DIR = os.path.join(PROJECT_ROOT, "zmark")
FRONTEND_ASSETS = os.path.join(FRONTEND_DIST, "assets")

if os.path.isdir(FRONTEND_ASSETS):
    app.mount("/ui/assets", StaticFiles(directory=FRONTEND_ASSETS), name="ui-assets")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "ZmaRk API running",
        "docs": "/docs",
        "frontend": "/ui",
        "legacy_frontend": "/legacy-ui",
    }


@app.get("/ui")
@app.get("/ui/")
async def serve_ui():
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {
        "error": "react_frontend_not_built",
        "message": "Run `npm install` and `npm run build` in frontend/, or run the Vite dev server.",
    }


@app.get("/ui/{path:path}")
async def serve_ui_spa(path: str):
    asset_path = os.path.join(FRONTEND_DIST, path)
    if os.path.exists(asset_path) and os.path.isfile(asset_path):
        return FileResponse(asset_path)

    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")

    raise HTTPException(status_code=404, detail="React frontend has not been built.")


LEGACY_MIME = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".jsx": "application/javascript",
    ".json": "application/json",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}


@app.get("/legacy-ui")
@app.get("/legacy-ui/")
async def serve_legacy_ui():
    index_path = os.path.join(LEGACY_UI_DIR, "ZmaRk.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Legacy frontend not found.")


@app.get("/legacy-ui/{filename:path}")
async def serve_legacy_ui_asset(filename: str):
    file_path = os.path.join(LEGACY_UI_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        ext = os.path.splitext(filename)[1].lower()
        return FileResponse(file_path, media_type=LEGACY_MIME.get(ext, "application/octet-stream"))
    raise HTTPException(status_code=404, detail=f"Legacy asset not found: {filename}")
