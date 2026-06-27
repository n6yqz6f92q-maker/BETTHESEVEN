"""KYC/Verification API routes."""
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app import database as db
from app.services import kyc_service

router = APIRouter(prefix="/api/kyc", tags=["kyc"])


class StartVerificationRequest(BaseModel):
    user_id: str


@router.post("/start")
def start_verification(req: StartVerificationRequest):
    """Start a Veriff identity verification session for a user."""
    user = db.get_user(req.user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    if user.get("kyc_status") == kyc_service.KYC_VERIFIED:
        raise HTTPException(400, "User is already KYC verified")

    try:
        session = kyc_service.create_verification_session(req.user_id)
        if session.get("status") == "error":
            raise HTTPException(500, session.get("message", "Verification failed"))
        return {"ok": True, "session": session}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/status/{user_id}")
def get_kyc_status(user_id: str):
    """Get the KYC verification status for a user."""
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return kyc_service.get_kyc_status(user_id)


@router.post("/veriff-webhook")
async def veriff_webhook(request: Request):
    """
    Webhook endpoint for Veriff verification decisions.
    Veriff sends POST with JSON payload when verification is processed.
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")

    result = kyc_service.process_webhook(payload)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Webhook processing failed"))

    return {"ok": True}


@router.get("/pending")
def list_pending():
    """List users pending KYC verification (admin)."""
    return kyc_service.list_pending_verifications()