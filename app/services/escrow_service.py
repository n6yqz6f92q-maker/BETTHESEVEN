"""
Escrow and rake logic for Seven Bet.

All monetary operations — stake deduction, payout distribution,
rake collection — are handled here with precision logging.

Supports dynamic rake rates based on user's Gold Upgrade status.
Free users pay 7%. Premium Gold+ users get reduced rates (5%, 4%, 3%).
"""
from decimal import Decimal
from app import database as db
from app.services.founders_pass import get_effective_rake


RAKE_RATE = 0.07  # Default 7% commission for free users


def get_user_rake_rate(user_id: str) -> float:
    """Get the effective rake rate for a user based on their Gold status."""
    rate = get_effective_rake(user_id)
    return float(rate)


def deduct_stake(user_id: str, bet_id: str, amount: float):
    """Deduct stake from user's balance and record transaction."""
    user = db.get_user(user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if user["balance"] < amount:
        raise ValueError(
            f"Insufficient balance. User '{user['username']}' has "
            f"${user['balance']:.2f} but needs ${amount:.2f}"
        )
    db.update_balance(user_id, -amount)
    db.add_transaction(bet_id, user_id, -amount, "stake")


def refund_stake(user_id: str, bet_id: str, amount: float):
    """Refund stake back to user (for cancellations)."""
    db.update_balance(user_id, amount)
    db.add_transaction(bet_id, user_id, amount, "stake_refund")


def settle_bet(bet_id: str, winner_id: str):
    """
    Settle a bet:
    1. Calculate total pot = sum of all stakes
    2. Calculate rake based on winner's Gold status (7% default, 5/4/3% for Premium+)
    3. Winner gets pot - rake
    4. Platform gets rake
    5. Record all transactions
    """
    bet = db.get_bet(bet_id)
    if bet is None:
        raise ValueError(f"Bet {bet_id} not found")
    if bet["status"] != "accepted":
        raise ValueError(f"Bet must be in 'accepted' status, got '{bet['status']}'")

    participants = db.get_participants(bet_id)
    num_participants = len(participants)
    if num_participants < 2:
        raise ValueError(f"Need at least 2 participants to settle")

    # Get effective rake rate based on winner's Gold Upgrade status
    winner_rake = get_user_rake_rate(winner_id)
    
    # Total pot = stake * number of participants
    total_pot = bet["stake"] * num_participants
    rake = total_pot * winner_rake
    winner_payout = total_pot - rake

    # Verify winner is actually a participant
    winner_ids = [p["id"] for p in participants]
    if winner_id not in winner_ids:
        raise ValueError(f"Winner {winner_id} is not a participant in this bet")

    # Credit winner
    db.update_balance(winner_id, winner_payout)
    db.add_transaction(bet_id, winner_id, winner_payout, "payout")

    # Credit platform rake
    db.update_balance("platform", rake)
    db.add_transaction(bet_id, "platform", rake, "rake")

    # Update bet status
    db.update_bet_status(bet_id, "settled", winner_id)

    return {
        "total_pot": total_pot,
        "rake": round(rake, 2),
        "winner_payout": round(winner_payout, 2),
        "winner_id": winner_id,
        "rake_rate": round(winner_rake, 4),
        "num_participants": num_participants,
    }


def cancel_bet(bet_id: str):
    """Cancel a bet and refund all participants."""
    bet = db.get_bet(bet_id)
    if bet is None:
        raise ValueError(f"Bet {bet_id} not found")
    if bet["status"] not in ("open", "accepted"):
        raise ValueError(f"Cannot cancel bet in '{bet['status']}' status")

    participants = db.get_participants(bet_id)
    for p in participants:
        db.update_balance(p["id"], bet["stake"])
        db.add_transaction(bet_id, p["id"], bet["stake"], "stake_refund")

    db.update_bet_status(bet_id, "cancelled")


def accept_bet(bet_id: str, user_id: str):
    """
    Accept/join an open bet:
    1. Verify bet is open
    2. Verify user is not already a participant
    3. Check max participants
    4. Deduct stake from user
    5. Add as participant
    6. If max participants reached, mark bet as 'accepted'
    """
    bet = db.get_bet(bet_id)
    if bet is None:
        raise ValueError(f"Bet {bet_id} not found")
    if bet["status"] != "open":
        raise ValueError(f"Bet is not open (status: {bet['status']})")
    if user_id == bet["creator_id"]:
        raise ValueError("Cannot join your own bet — you're already the creator")

    participants = db.get_participants(bet_id)
    if user_id in [p["id"] for p in participants]:
        raise ValueError("You are already a participant in this bet")

    current_count = len(participants)
    if current_count >= bet["max_participants"]:
        raise ValueError("Bet already has maximum number of participants")

    # Deduct stake
    deduct_stake(user_id, bet_id, bet["stake"])

    # Join
    db.join_bet(bet_id, user_id)

    # If max participants reached, mark as accepted
    new_count = current_count + 1
    if new_count >= bet["max_participants"]:
        db.update_bet_status(bet_id, "accepted")

    return db.get_participants(bet_id)
