"""
Bet service — orchestrates user-facing bet operations.
"""
from app import database as db
from app.services import escrow_service


def create_bet(username: str, title: str, stake: float, max_participants: int = 2):
    """Create a bet. The user must exist and have sufficient balance."""
    user = db.get_user_by_username(username)
    if user is None:
        raise ValueError(f"User '{username}' not found. Register first.")
    if stake <= 0:
        raise ValueError("Stake must be positive")
    if max_participants < 2:
        raise ValueError("A bet needs at least 2 participants")

    # 1. Create the bet first (gives us a bet ID)
    bet = db.create_bet(title, user["id"], stake, max_participants)

    # 2. Deduct stake from creator
    escrow_service.deduct_stake(user["id"], bet["id"], stake)

    # 3. Record creator as a participant
    db.join_bet(bet["id"], user["id"])

    return db.get_bet(bet["id"])


def join_bet(bet_id: str, username: str):
    """Join a bet as a participant."""
    user = db.get_user_by_username(username)
    if user is None:
        raise ValueError(f"User '{username}' not found")
    return escrow_service.accept_bet(bet_id, user["id"])


def settle_bet(bet_id: str, winner_username: str):
    """Settle a bet and distribute the pot."""
    winner = db.get_user_by_username(winner_username)
    if winner is None:
        raise ValueError(f"User '{winner_username}' not found")
    return escrow_service.settle_bet(bet_id, winner["id"])


def cancel_bet(bet_id: str):
    """Cancel a bet and refund all participants."""
    return escrow_service.cancel_bet(bet_id)