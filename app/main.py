"""
Seven Bet — Peer-to-peer betting platform.
Entry point for the uvicorn server.
"""
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import migrate as db_migrate
from app.services.founders_pass import migrate as fp_migrate
from app.services.kyc_service import migrate as kyc_migrate
from app.services.geo_service import migrate as geo_migrate
from app.services.concierge_service import migrate as concierge_migrate
from app.routers import users, bets, platform, founders_pass, kyc, geo, admin_concierge, updates, email_router

app = FastAPI(title="Seven Bet", version="1.0.0")

# Run migrations on startup (wrap in try/except to avoid crashing on Vercel)
import traceback
for _migrate_fn, _name in [
    (db_migrate, "db"),
    (fp_migrate, "founders_pass"),
    (kyc_migrate, "kyc"),
    (geo_migrate, "geo"),
    (concierge_migrate, "concierge"),
]:
    try:
        _migrate_fn()
    except Exception as _e:
        print(f"[WARN] Migration '{_name}' failed: {_e}")
        traceback.print_exc()

# Register API routers
app.include_router(users.router)
app.include_router(bets.router)
app.include_router(platform.router)
app.include_router(founders_pass.router)
app.include_router(kyc.router)
app.include_router(geo.router)
app.include_router(admin_concierge.router)
app.include_router(email_router.router)

# Serve static files (CSS, JS, images)
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve index.html at root
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

# SPA fallback: serve index.html for all non-API, non-file routes
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Don't interfere with API routes (handled above)
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3000,
        reload=False,
    )