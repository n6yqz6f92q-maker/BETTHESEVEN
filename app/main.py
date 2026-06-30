"""
Seven Bet — Peer-to-peer betting platform.
Entry point for the uvicorn server.
"""
import os
import sys
import html as html_mod

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from app.database import migrate as db_migrate, get_bet
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

# Read index.html template once at startup
_index_html_path = os.path.join(static_dir, "index.html")
try:
    with open(_index_html_path, "r") as f:
        _INDEX_HTML = f.read()
except Exception:
    _INDEX_HTML = ""


def _build_og_html(bet: dict | None = None) -> str:
    """Build OpenGraph meta tags for social sharing."""
    if bet:
        title = html_mod.escape(bet.get("title", "Bet"))
        stake = bet.get("stake", 0)
        status = bet.get("status", "open")
        creator = html_mod.escape(bet.get("creator_username", "Someone"))
        og_title = f"You've been challenged to a Seven Bet: {title}"
        og_desc = f"{creator} bet ${stake:.2f} — {len(bet.get('participants', []) or [])} participant(s). Status: {status}. Peer-to-peer betting with zero bookmaker margins."
        og_url = f"https://bettheseven.com/bet/{html_mod.escape(bet.get('id', ''))}"
    else:
        og_title = "Seven Bet — The Gold Standard of P2P Betting"
        og_desc = "Bet against people, not the house. Peer-to-peer betting with zero bookmaker margins. Just 7% fee on winnings. Join for free."
        og_url = "https://bettheseven.com/"

    return f"""
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{og_desc}">
    <meta property="og:url" content="{og_url}">
    <meta property="og:image" content="https://bettheseven.com/static/og-preview.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Seven Bet">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@sevenbet">
    <meta name="twitter:title" content="{og_title}">
    <meta name="twitter:description" content="{og_desc}">
    <meta name="twitter:image" content="https://bettheseven.com/static/og-preview.png">
    <title>{og_title} | Seven Bet</title>
    """


# Serve index.html at root with OG tags
@app.get("/")
async def serve_index():
    og_html = _build_og_html()
    content = _INDEX_HTML.replace("<!-- {{OG_TAGS}} -->", og_html)
    return HTMLResponse(content=content)


# SPA fallback with dynamic OG tags for bet pages
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Don't interfere with API routes (handled above)
    if full_path.startswith("api/") or full_path.startswith("static/"):
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")

    bet = None
    # Check if this is a bet detail page
    if full_path.startswith("bet/"):
        bet_id = full_path.split("/")[1] if "/" in full_path else ""
        if bet_id:
            try:
                bet_raw = get_bet(bet_id)
                if bet_raw:
                    # Fetch participant count for richer OG tags
                    from app.database import get_participants
                    participants = get_participants(bet_id)
                    bet_raw["participants"] = participants
                    # Get creator username
                    from app.database import get_user
                    creator = get_user(bet_raw["creator_id"])
                    if creator:
                        bet_raw["creator_username"] = creator.get("username", "Someone")
                    else:
                        bet_raw["creator_username"] = "Someone"
                    bet = bet_raw
            except Exception:
                pass

    og_html = _build_og_html(bet)
    content = _INDEX_HTML.replace("<!-- {{OG_TAGS}} -->", og_html)
    return HTMLResponse(content=content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3000,
        reload=False,
    )