"""Platform/info API routes."""
from fastapi import APIRouter, Query
from app import database as db

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.get("/stats")
def get_platform_stats():
    return db.platform_stats()


@router.get("/leaderboard")
def get_leaderboard(limit: int = Query(default=10, ge=1, le=100)):
    return db.leaderboard(limit)