"""Gold Upgrade API routes — Open Access."""
import os
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from app import database as db
from app.services import founders_pass

router = APIRouter(prefix="/api/founders-pass", tags=["founders-pass"])


class ActivatePassRequest(BaseModel):
    user_id: str
    tier: str = Field(pattern=r"^(entry|standard|premium|founding_patron|the_seven)$")
    payment_ref: str = ""


class CancelRequest(BaseModel):
    user_id: str
    pass_id: str


class ROICalculatorRequest(BaseModel):
    monthly_volume: float = Field(gt=0, default=10000)


@router.get("/availability")
def get_availability():
    """Get remaining Gold Upgrade count per tier."""
    return founders_pass.get_availability()


@router.get("/purchase-info/{tier}")
def get_purchase_info(tier: str):
    """Get purchase info for a specific Gold tier."""
    if tier not in founders_pass.TIERS:
        raise HTTPException(400, f"Unknown tier: {tier}")
    try:
        info = founders_pass.get_purchase_info(tier)
        return {"ok": True, "info": info}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/my-pass")
def get_my_pass(user_id: str = Query("")):
    """Get the current user's Gold Upgrade pass by user ID."""
    if not user_id:
        raise HTTPException(400, "user_id query parameter is required")
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    my_pass = founders_pass.get_my_pass(user_id)
    return {"ok": True, "pass": my_pass}


@router.get("/my-pass-by-username")
def get_my_pass_by_username(username: str = Query("")):
    """Get the current user's Gold Upgrade pass by username."""
    if not username:
        raise HTTPException(400, "username query parameter is required")
    my_pass = founders_pass.get_pass_by_username(username)
    return {"ok": True, "pass": my_pass}


@router.get("/hall-of-fame")
def get_hall_of_fame():
    """Public listing of all Gold members."""
    return founders_pass.get_hall_of_fame()


@router.post("/activate")
def activate_pass(req: ActivatePassRequest):
    """Activate a Gold Upgrade after payment."""
    user = db.get_user(req.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    try:
        result = founders_pass.activate_pass(req.tier, req.user_id, req.payment_ref)
        return {"ok": True, "pass": result}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/cancel")
def cancel_pass(req: CancelRequest):
    """Cancel/refund a Gold Upgrade pass."""
    user = db.get_user(req.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    try:
        result = founders_pass.cancel_pass(req.pass_id, req.user_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/calculate-roi")
def calculate_roi(req: ROICalculatorRequest):
    """Calculate ROI for all Gold tiers."""
    return {"ok": True, "results": founders_pass.calculate_roi(req.monthly_volume)}


@router.get("/calculate-roi")
def calculate_roi_get(monthly_volume: float = 10000):
    """GET version of ROI calculator."""
    if monthly_volume <= 0:
        raise HTTPException(400, "Monthly volume must be positive")
    return {"ok": True, "results": founders_pass.calculate_roi(monthly_volume)}
