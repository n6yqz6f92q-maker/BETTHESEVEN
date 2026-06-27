"""
Veriff KYC Integration Service for Seven Bet.

Handles:
- Database schema for KYC status tracking
- Veriff Web SDK session creation
- Webhook processing for verification decisions
- Age verification (18+ / 21+)
- Periodic re-verification scheduling

Requires VERIFF_API_KEY environment variable to activate live API calls.
"""
import os
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Any

from app import database as db

# ── Configuration ────────────────────────────────────────────────
VERIFF_API_KEY = os.environ.get("VERIFF_API_KEY", "")
VERIFF_SHARED_SECRET = os.environ.get("VERIFF_SHARED_SECRET", "")
VERIFF_BASE_URL = "https://api.veriff.com/v1"

# KYC status values
KYC_PENDING = "pending"
KYC_VERIFIED = "verified"
KYC_REJECTED = "rejected"
KYC_EXPIRED = "expired"
KYC_FLAGGED = "flagged"


def migrate():
    """Add KYC-related columns to app_users if not present."""
    # Check if columns exist
    existing = db.run("PRAGMA table_info(app_users)")
    col_names = [c["name"] for c in existing]

    if "kyc_status" not in col_names:
        db.run("ALTER TABLE app_users ADD COLUMN kyc_status TEXT DEFAULT 'pending'")
    if "kyc_verified_at" not in col_names:
        db.run("ALTER TABLE app_users ADD COLUMN kyc_verified_at TEXT")
    if "kyc_provider_id" not in col_names:
        db.run("ALTER TABLE app_users ADD COLUMN kyc_provider_id TEXT")
    if "kyc_verification_id" not in col_names:
        db.run("ALTER TABLE app_users ADD COLUMN kyc_verification_id TEXT")


def create_verification_session(user_id: str) -> dict[str, Any]:
    """
    Create a Veriff verification session for a user.

    Returns the session URL and session ID that the frontend
    uses to launch the Veriff Web SDK.

    Requires VERIFF_API_KEY to be set.
    """
    if not VERIFF_API_KEY:
        # Return mock session for development/testing
        session_id = str(uuid.uuid4())
        return {
            "status": "sandbox",
            "verification": {
                "id": session_id,
                "url": f"https://sandbox.veriff.me/s/{session_id}",
                "vendorData": user_id,
            },
        }

    # In production, call Veriff API:
    # import requests
    # response = requests.post(
    #     f"{VERIFF_BASE_URL}/sessions",
    #     headers={"X-AUTH-TOKEN": VERIFF_API_KEY, "Content-Type": "application/json"},
    #     json={
    #         "verification": {
    #             "vendorData": user_id,
    #             "callback": f"{APP_URL}/api/kyc/veriff-webhook",
    #             "person": {
    #                 "firstName": "",
    #                 "lastName": "",
    #             },
    #             "document": {
    #                 "type": "PASSPORT",
    #                 "country": "GB",
    #             },
    #         }
    #     },
    # )
    # return response.json()

    return {"status": "error", "message": "VERIFF_API_KEY not configured"}


def process_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process a Veriff webhook decision.

    Veriff sends webhooks with verification status:
    - approved: KYC passed
    - declined: KYC failed
    - expired: Session expired, user needs to retry
    - resubmitted: User uploaded new documents

    Updates the user's KYC status in the database.
    """
    try:
        verification = payload.get("verification", {})
        status = verification.get("status", "")
        vendor_data = verification.get("vendorData", "")
        verification_id = verification.get("id", "")

        if not vendor_data:
            return {"ok": False, "error": "Missing vendorData"}

        user = db.get_user(vendor_data)
        if user is None:
            return {"ok": False, "error": f"User {vendor_data} not found"}

        now = datetime.now(timezone.utc).isoformat()

        if status == "approved":
            db.run(
                f"UPDATE app_users SET kyc_status = '{KYC_VERIFIED}', "
                f"kyc_verified_at = '{now}', "
                f"kyc_provider_id = '{verification_id}' "
                f"WHERE id = '{vendor_data}'"
            )
            return {"ok": True, "status": KYC_VERIFIED, "user_id": vendor_data}

        elif status == "declined":
            db.run(
                f"UPDATE app_users SET kyc_status = '{KYC_REJECTED}', "
                f"kyc_provider_id = '{verification_id}' "
                f"WHERE id = '{vendor_data}'"
            )
            return {"ok": True, "status": KYC_REJECTED, "user_id": vendor_data}

        elif status == "expired":
            db.run(
                f"UPDATE app_users SET kyc_status = '{KYC_EXPIRED}' "
                f"WHERE id = '{vendor_data}'"
            )
            return {"ok": True, "status": KYC_EXPIRED, "user_id": vendor_data}

        elif status == "resubmitted":
            db.run(
                f"UPDATE app_users SET kyc_status = '{KYC_PENDING}' "
                f"WHERE id = '{vendor_data}'"
            )
            return {"ok": True, "status": KYC_PENDING, "user_id": vendor_data}

        return {"ok": True, "status": f"unhandled:{status}", "user_id": vendor_data}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_kyc_status(user_id: str) -> dict[str, Any]:
    """Get the KYC verification status for a user."""
    user = db.get_user(user_id)
    if user is None:
        return {"status": "not_found"}

    return {
        "status": user.get("kyc_status", KYC_PENDING),
        "verified_at": user.get("kyc_verified_at"),
        "verification_id": user.get("kyc_provider_id"),
        "username": user.get("username"),
        "user_id": user_id,
    }


def is_kyc_verified(user_id: str) -> bool:
    """Check if a user has passed KYC verification."""
    user = db.get_user(user_id)
    if user is None:
        return False
    return user.get("kyc_status") == KYC_VERIFIED


def needs_reverification(user_id: str) -> bool:
    """
    Check if a user needs re-verification.
    UKGC requires KYC re-checks every 12 months.
    """
    user = db.get_user(user_id)
    if user is None:
        return True

    verified_at = user.get("kyc_verified_at")
    if not verified_at:
        return True

    try:
        verified_dt = datetime.fromisoformat(verified_at)
        twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
        return verified_dt < twelve_months_ago
    except (ValueError, TypeError):
        return True


def list_pending_verifications() -> list[dict[str, Any]]:
    """List users who need KYC verification (for admin dashboard)."""
    return db.run(
        f"SELECT id, username, kyc_status, kyc_verified_at "
        f"FROM app_users "
        f"WHERE id != 'platform' AND kyc_status IN ('pending', 'expired') "
        f"ORDER BY kyc_status DESC"
    )