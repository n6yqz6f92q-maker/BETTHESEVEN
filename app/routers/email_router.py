"""Welcome Email API — Sends 'Welcome Founder' emails for activations."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import database as db
from app.services import email_service
from app.tools.email_sender import send_email, BUSINESS_INBOX

router = APIRouter(prefix="/api/admin/emails", tags=["admin-emails"])


@router.get("/pending")
def list_pending_emails():
    """List all activations with pending welcome emails."""
    return email_service.get_pending_emails()


@router.get("/preview/{activation_id}")
def preview_email(activation_id: str):
    """Preview the rendered welcome email for an activation."""
    preview = email_service.get_email_preview(activation_id)
    if preview is None:
        raise HTTPException(404, "Activation not found")
    return preview


@router.post("/send/{activation_id}")
def send_welcome(activation_id: str):
    """
    Send a welcome email for an activation.
    
    Prepares the email using the tier-appropriate template,
    sends it via the business inbox, and marks it as sent.
    """
    preview = email_service.get_email_preview(activation_id)
    if preview is None:
        raise HTTPException(404, "Activation not found")
    
    result = send_email(
        to=[preview["to"]],
        subject=preview["subject"],
        body=preview["body"],
    )
    
    if result.get("ok"):
        # Mark as sent in the database
        from app.services.concierge_service import mark_welcome_email_sent
        mark_welcome_email_sent(activation_id)
        return {
            "ok": True,
            "subject": preview["subject"],
            "to": preview["to"],
            "sent": True,
        }
    else:
        return {
            "ok": False,
            "error": result.get("error", "Failed to send email"),
        }


@router.post("/send-all")
def send_all_pending():
    """Send all pending welcome emails at once."""
    pending = email_service.get_pending_emails()
    results = []
    
    for activation in pending:
        preview = email_service.get_email_preview(activation["id"])
        if preview is None:
            continue
        
        result = send_email(
            to=[preview["to"]],
            subject=preview["subject"],
            body=preview["body"],
        )
        
        if result.get("ok"):
            from app.services.concierge_service import mark_welcome_email_sent
            mark_welcome_email_sent(activation["id"])
            results.append({
                "activation_id": activation["id"],
                "username": activation["username"],
                "status": "sent",
                "subject": preview["subject"],
            })
        else:
            results.append({
                "activation_id": activation["id"],
                "username": activation["username"],
                "status": "failed",
                "error": result.get("error"),
            })
    
    return {
        "ok": True,
        "total": len(pending),
        "sent": len([r for r in results if r["status"] == "sent"]),
        "results": results,
    }