"""Geolocation API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import database as db
from app.services import geo_service

router = APIRouter(prefix="/api/geolocation", tags=["geolocation"])


class VerifyLocationRequest(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    jurisdiction: str
    ipAddress: str = ""
    vpnDetected: bool = False
    accuracy: float = 0
    timestamp: str = ""


@router.post("/verify")
def verify_location(req: VerifyLocationRequest):
    """Verify a user's location via GeoComply data."""
    user = db.get_user(req.user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    result = geo_service.verify_location(req.user_id, req.model_dump())

    if result["status"] == "denied":
        # Return 403 for denied locations (VPN, wrong jurisdiction)
        from fastapi import HTTPException
        raise HTTPException(403, result["reason"])

    return {"ok": True, "location": result}


@router.get("/status/{user_id}")
def get_location_status(user_id: str):
    """Get the latest verified location for a user."""
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return geo_service.get_user_location(user_id)


@router.get("/jurisdictions")
def list_jurisdictions():
    """List all permitted betting jurisdictions."""
    return geo_service.AVAILABLE_JURISDICTIONS