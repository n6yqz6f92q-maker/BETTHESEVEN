"""
Concierge CRM Service — The Seven VIP Onboarding & Manual Activation.

Handles:
- Database schema for concierge inquiries (app_concierge_inquiries)
- Manual pass activation for The Seven tier
- Inquiry capture (from mailto clicks or contact form)
- Activation audit logging
- Welcome email triggers (logging, actual send requires email service)

Flow:
1. Prospect clicks "Inquire" → inquiry captured in app_concierge_inquiries
2. Concierge reviews → calls admin endpoint to activate pass
3. System creates pass record + logs activation + records welcome email intent
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app import database as db
from app.services import founders_pass


def migrate():
    """Create concierge CRM tables."""
    db.run("""
        CREATE TABLE IF NOT EXISTS app_concierge_inquiries (
            id TEXT PRIMARY KEY,
            user_email TEXT NOT NULL,
            tier TEXT NOT NULL CHECK(tier IN ('the_seven', 'founding_patron')),
            status TEXT NOT NULL DEFAULT 'new'
                CHECK(status IN ('new','contacted','reviewing','approved','rejected','onboarded','cancelled')),
            applicant_name TEXT,
            notes TEXT,
            preferred_number INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            assigned_to TEXT
        )
    """)
    # Activation audit log
    db.run("""
        CREATE TABLE IF NOT EXISTS app_concierge_activations (
            id TEXT PRIMARY KEY,
            inquiry_id TEXT,
            user_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            founder_number INTEGER NOT NULL,
            activated_by TEXT NOT NULL DEFAULT 'concierge',
            activated_at TEXT NOT NULL,
            welcome_email_sent INTEGER DEFAULT 0,
            welcome_email_sent_at TEXT,
            notes TEXT,
            FOREIGN KEY (inquiry_id) REFERENCES app_concierge_inquiries(id),
            FOREIGN KEY (user_id) REFERENCES app_users(id)
        )
    """)


def capture_inquiry(
    email: str,
    tier: str = "the_seven",
    name: str = "",
    notes: str = "",
    preferred_number: int | None = None,
) -> dict[str, Any]:
    """
    Capture a concierge inquiry (from mailto click or contact form).
    
    Args:
        email: Prospect's email address
        tier: 'the_seven' or 'founding_patron'
        name: Applicant's name (optional)
        notes: Any initial notes from the prospect
        preferred_number: Desired founder number 1-7
        
    Returns:
        The inquiry record
    """
    inquiry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate tier
    if tier not in ("the_seven", "founding_patron"):
        raise ValueError(f"Concierge tier must be 'the_seven' or 'founding_patron', got '{tier}'")
    
    # Validate preferred number for The Seven
    if tier == "the_seven" and preferred_number is not None:
        if preferred_number < 1 or preferred_number > 7:
            raise ValueError(f"Founder number must be 1-7, got {preferred_number}")
        # Check if number is already taken
        existing = db.run(
            f"SELECT founder_number FROM app_founder_passes "
            f"WHERE tier = 'the_seven' AND founder_number = {preferred_number} "
            f"AND status IN ('active', 'used')"
        )
        if existing:
            raise ValueError(f"Founder number #{preferred_number} is already taken")
    
    notes_escaped = notes.replace("'", "''")
    
    db.run(
        f"INSERT INTO app_concierge_inquiries "
        f"(id, user_email, tier, status, applicant_name, notes, preferred_number, created_at, updated_at) "
        f"VALUES ('{inquiry_id}', '{email}', '{tier}', 'new', "
        f"{'NULL' if not name else f"'{name}'"}, "
        f"{'NULL' if not notes else f"'{notes_escaped}'"}, "
        f"{'NULL' if preferred_number is None else str(preferred_number)}, "
        f"'{now}', '{now}')"
    )
    
    return {
        "id": inquiry_id,
        "email": email,
        "tier": tier,
        "status": "new",
        "name": name or None,
        "preferred_number": preferred_number,
        "created_at": now,
    }


def manual_activate(
    user_id: str,
    tier: str,
    inquiry_id: str | None = None,
    activated_by: str = "concierge",
    notes: str = "",
) -> dict[str, Any]:
    """
    Manually activate a Founder's Pass for a user (concierge flow).
    
    This is the admin endpoint that:
    1. Creates the founder pass record
    2. Logs the activation in app_concierge_activations
    3. Updates the inquiry status to 'onboarded'
    4. Records welcome email intent
    
    Args:
        user_id: The user to activate the pass for
        tier: 'the_seven' or 'founding_patron'
        inquiry_id: Optional reference to the original inquiry
        activated_by: Who performed the activation
        notes: Any notes about this activation
        
    Returns:
        Dict with pass details and activation record
    """
    if tier not in founders_pass.TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    
    if tier not in ("the_seven", "founding_patron"):
        raise ValueError(f"Concierge activation only for 'the_seven' or 'founding_patron', got '{tier}'")
    
    # Check user exists
    user = db.get_user(user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    
    # Check user doesn't already have a pass
    existing_pass = founders_pass.get_my_pass(user_id)
    if existing_pass:
        raise ValueError(f"User already has a Founder's Pass (tier: {existing_pass['tier']})")
    
    # Check availability
    availability = founders_pass.get_availability()
    if availability[tier]["remaining"] <= 0:
        raise ValueError(f"Tier {tier} is sold out")
    
    # Activate the pass (creates the founder_passes record + increments sequence)
    pass_result = founders_pass.activate_pass(tier, user_id, payment_ref=f"concierge-{activated_by}")
    
    # Log activation
    activation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    notes_escaped = notes.replace("'", "''")
    
    db.run(
        f"INSERT INTO app_concierge_activations "
        f"(id, inquiry_id, user_id, tier, founder_number, activated_by, activated_at, notes) "
        f"VALUES ('{activation_id}', "
        f"{'NULL' if inquiry_id is None else f"'{inquiry_id}'"}, "
        f"'{user_id}', '{tier}', {pass_result['founder_number']}, "
        f"'{activated_by}', '{now}', "
        f"{'NULL' if not notes else f"'{notes_escaped}'"})"
    )
    
    # Update inquiry status if referenced
    if inquiry_id:
        db.run(
            f"UPDATE app_concierge_inquiries SET status = 'onboarded', updated_at = '{now}' "
            f"WHERE id = '{inquiry_id}'"
        )
    
    return {
        "ok": True,
        "pass": pass_result,
        "activation": {
            "id": activation_id,
            "activated_by": activated_by,
            "activated_at": now,
        },
        "welcome_email_pending": True,
    }


def list_inquiries(status: str | None = None) -> list[dict[str, Any]]:
    """List concierge inquiries, optionally filtered by status."""
    if status:
        return db.run(
            f"SELECT * FROM app_concierge_inquiries WHERE status = '{status}' ORDER BY created_at DESC"
        )
    return db.run("SELECT * FROM app_concierge_inquiries ORDER BY created_at DESC")


def update_inquiry_status(inquiry_id: str, status: str, notes: str = "") -> dict[str, Any]:
    """Update the status of a concierge inquiry."""
    valid_statuses = ("new", "contacted", "reviewing", "approved", "rejected", "onboarded", "cancelled")
    if status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of {valid_statuses}")
    
    now = datetime.now(timezone.utc).isoformat()
    update_sql = f"UPDATE app_concierge_inquiries SET status = '{status}', updated_at = '{now}'"
    
    if notes:
        notes_escaped = notes.replace("'", "''")
        update_sql += f", notes = '{notes_escaped}'"
    
    update_sql += f" WHERE id = '{inquiry_id}'"
    db.run(update_sql)
    
    return {"ok": True, "inquiry_id": inquiry_id, "status": status}


def list_activations(tier: str | None = None) -> list[dict[str, Any]]:
    """List all concierge activations."""
    if tier:
        return db.run(
            f"SELECT a.*, u.username FROM app_concierge_activations a "
            f"JOIN app_users u ON u.id = a.user_id "
            f"WHERE a.tier = '{tier}' ORDER BY a.activated_at DESC"
        )
    return db.run(
        f"SELECT a.*, u.username FROM app_concierge_activations a "
        f"JOIN app_users u ON u.id = a.user_id ORDER BY a.activated_at DESC"
    )


def mark_welcome_email_sent(activation_id: str) -> dict[str, Any]:
    """Mark that a welcome email has been sent for an activation."""
    now = datetime.now(timezone.utc).isoformat()
    db.run(
        f"UPDATE app_concierge_activations SET "
        f"welcome_email_sent = 1, welcome_email_sent_at = '{now}' "
        f"WHERE id = '{activation_id}'"
    )
    return {"ok": True, "activation_id": activation_id, "sent_at": now}