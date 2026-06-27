"""User API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app import database as db

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str
    email: str | None = None


@router.post("")
def create_user(req: CreateUserRequest):
    username = req.username.strip()
    if not username:
        raise HTTPException(400, "Username is required")
    existing = db.get_user_by_username(username)
    if existing:
        raise HTTPException(409, f"User '{username}' already exists")
    user = db.create_user(username, req.email)
    return {"ok": True, "user": user}


@router.get("")
def list_users():
    """List all registered users."""
    return db.list_users()


@router.get("/{user_id}")
def get_user(user_id: str):
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/{user_id}/bets")
def get_user_bets(user_id: str):
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    bets = db.get_user_bets(user_id)
    return bets


@router.get("/{user_id}/transactions")
def get_user_transactions(user_id: str):
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    txs = db.get_user_transactions(user_id)
    return txs