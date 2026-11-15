from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import agents_api, circular, citizen, core, ops
from .config import FRONTEND_DIST, UPLOAD_DIR, settings
from .database.db import SessionLocal, init_schema
from .database.seed import seed_if_empty

log = logging.getLogger("vyarthx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    with SessionLocal() as db:
        seeded = seed_if_empty(db)
        log.info("VYARTHX ready (seeded=%s, demo=%s)", seeded, settings.DEMO_MODE)
    yield


app = FastAPI(title="VYARTHX API", version="1.0.0", description="India's AI-Powered City Waste Intelligence & Circular Economy Platform", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", f"http://127.0.0.1:{settings.PORT}", f"http://localhost:{settings.PORT}"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (core.router, citizen.router, ops.router, circular.router, agents_api.router):
    app.include_router(r, prefix="/api")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. The action was not completed. Please try again.", "type": type(exc).__name__})


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

if (FRONTEND_DIST / "index.html").exists():
    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        f = (FRONTEND_DIST / full_path).resolve()
        if full_path and FRONTEND_DIST.resolve() in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
else:

    @app.get("/", include_in_schema=False)
    def root():
        return {"app": "VYARTHX", "note": "Frontend build not found. Run the frontend build or use run.bat. API docs at /docs."}
