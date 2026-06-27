"""Admin Concierge API — The Seven VIP Onboarding & Manual Activation."""
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Any

from app import database as db
from app.services import concierge_service, founders_pass

router = APIRouter(prefix="/api/admin/concierge", tags=["admin-concierge"])


# ── Request Models ───────────────────────────────────────────────

class CaptureInquiryRequest(BaseModel):
    email: str
    tier: str = Field(default="the_seven", pattern=r"^(the_seven|founding_patron)$")
    name: str = ""
    notes: str = ""
    preferred_number: int | None = Field(default=None, ge=1, le=7)


class ManualActivateRequest(BaseModel):
    user_id: str
    tier: str = Field(pattern=r"^(the_seven|founding_patron)$")
    inquiry_id: str | None = None
    activated_by: str = "concierge"
    notes: str = ""


class UpdateInquiryStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(new|contacted|reviewing|approved|rejected|onboarded|cancelled)$")
    notes: str = ""


class MarkEmailSentRequest(BaseModel):
    activation_id: str


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/capture-inquiry")
def capture_inquiry(req: CaptureInquiryRequest):
    """
    Capture a concierge inquiry from the landing page.
    Used when someone clicks 'Inquire' on The Seven tier.
    """
    try:
        inquiry = concierge_service.capture_inquiry(
            email=req.email,
            tier=req.tier,
            name=req.name,
            notes=req.notes,
            preferred_number=req.preferred_number,
        )
        return {"ok": True, "inquiry": inquiry}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/activate")
def manual_activate(req: ManualActivateRequest):
    """
    Manually activate a Founder's Pass for a VIP user.
    
    This is the admin endpoint for concierge onboarding:
    1. Creates the founder pass record (with commission discount)
    2. Logs the activation
    3. Updates inquiry status if referenced
    4. Marks welcome email as pending
    
    For The Seven: 3% lifetime commission, 10x staking limits
    For Founding Patron: 4% lifetime commission, 5x staking limits
    """
    user = db.get_user(req.user_id)
    if user is None:
        raise HTTPException(404, f"User {req.user_id} not found")
    
    try:
        result = concierge_service.manual_activate(
            user_id=req.user_id,
            tier=req.tier,
            inquiry_id=req.inquiry_id,
            activated_by=req.activated_by,
            notes=req.notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/inquiries")
def list_inquiries(status: str | None = None):
    """List all concierge inquiries, optionally filtered by status."""
    return concierge_service.list_inquiries(status)


@router.patch("/inquiries/{inquiry_id}")
def update_inquiry(inquiry_id: str, req: UpdateInquiryStatusRequest):
    """Update a concierge inquiry's status."""
    try:
        result = concierge_service.update_inquiry_status(inquiry_id, req.status, req.notes)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/activations")
def list_activations(tier: str | None = None):
    """List all concierge activations."""
    return concierge_service.list_activations(tier)


@router.post("/mark-email-sent")
def mark_email_sent(req: MarkEmailSentRequest):
    """Mark welcome email as sent for an activation."""
    try:
        result = concierge_service.mark_welcome_email_sent(req.activation_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/availability")
def get_tier_availability():
    """Get availability info for concierge tiers (The Seven + Founding Patron)."""
    avail = founders_pass.get_availability()
    return {
        "the_seven": avail.get("the_seven"),
        "founding_patron": avail.get("founding_patron"),
    }