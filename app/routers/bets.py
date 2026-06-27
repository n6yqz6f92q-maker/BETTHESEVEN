"""Bet API routes."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app import database as db
from app.services import bet_service

router = APIRouter(prefix="/api/bets", tags=["bets"])


class CreateBetRequest(BaseModel):
    username: str
    title: str
    stake: float = Field(gt=0)
    max_participants: int = Field(default=2, ge=2)


class JoinBetRequest(BaseModel):
    username: str


class SettleBetRequest(BaseModel):
    winner_username: str


@router.post("")
def create_bet(req: CreateBetRequest):
    try:
        bet = bet_service.create_bet(req.username, req.title, req.stake, req.max_participants)
        return {"ok": True, "bet": bet}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
def list_bets(status: str | None = Query(None)):
    return db.list_bets(status)


@router.get("/{bet_id}")
def get_bet(bet_id: str):
    bet = db.get_bet(bet_id)
    if bet is None:
        raise HTTPException(404, "Bet not found")
    participants = db.get_participants(bet_id)
    bet["participants"] = participants
    return bet


@router.post("/{bet_id}/join")
def join_bet(bet_id: str, req: JoinBetRequest):
    bet = db.get_bet(bet_id)
    if bet is None:
        raise HTTPException(404, "Bet not found")
    try:
        participants = bet_service.join_bet(bet_id, req.username)
        return {"ok": True, "participants": participants}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{bet_id}/settle")
def settle_bet(bet_id: str, req: SettleBetRequest):
    bet = db.get_bet(bet_id)
    if bet is None:
        raise HTTPException(404, "Bet not found")
    try:
        result = bet_service.settle_bet(bet_id, req.winner_username)
        return {"ok": True, "result": result}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{bet_id}/cancel")
def cancel_bet(bet_id: str):
    bet = db.get_bet(bet_id)
    if bet is None:
        raise HTTPException(404, "Bet not found")
    try:
        bet_service.cancel_bet(bet_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))