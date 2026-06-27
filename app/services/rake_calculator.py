"""
Rake Calculator — precision escrow math for Seven Bet.

Uses Python's Decimal type for all monetary calculations to eliminate
floating-point rounding errors. All amounts are stored and manipulated
as Decimal with 2 decimal places (cents/pence precision).

RAKE RATE: 7% (0.07) of total pot on settlement.

Usage:
    from app.services.rake_calculator import RakeCalculator

    calc = RakeCalculator()
    result = calc.settle_pot(stake=10.00, num_participants=2)
    # Returns: {'total_pot': Decimal('20.00'), 'rake': Decimal('1.40'),
    #           'winner_payout': Decimal('18.60')}
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import NamedTuple


# ── Constants ─────────────────────────────────────────────────────
RAKE_RATE = Decimal("0.07")
TWO_PLACES = Decimal("0.01")


class SettlementResult(NamedTuple):
    """Result of a pot settlement calculation."""
    total_pot: Decimal      # Sum of all stakes
    rake: Decimal           # 7% commission deducted
    winner_payout: Decimal   # Amount paid to winner (pot - rake)
    rake_rate: Decimal       # The rate applied (for transparency)
    num_participants: int


class RakeCalculator:
    """
    Handles all monetary calculations for Seven Bet's escrow system.

    All operations use Decimal arithmetic with ROUND_HALF_UP rounding
    to 2 decimal places (standard financial rounding).

    The 7% rake is deducted from the total pot before the winner
    receives their payout.
    """

    def __init__(self, rake_rate: Decimal | None = None):
        """
        Initialize with optional custom rake rate.

        Args:
            rake_rate: Decimal between 0 and 1 (default: 0.07 for 7%)
        """
        if rake_rate is None:
            rake_rate = RAKE_RATE
        if not Decimal("0") < rake_rate < Decimal("1"):
            raise ValueError(f"Rake rate must be between 0 and 1, got {rake_rate}")
        self.rake_rate = rake_rate

    @staticmethod
    def to_decimal(amount: float | str | Decimal) -> Decimal:
        """Safely convert a value to Decimal with 2 decimal places."""
        if isinstance(amount, Decimal):
            return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        try:
            return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"Cannot convert {amount!r} to Decimal: {e}")

    def calculate_pot(self, stake: Decimal, num_participants: int) -> Decimal:
        """
        Calculate total pot from stake and participant count.

        Args:
            stake: Amount staked per participant (as Decimal, float, or str)
            num_participants: Number of participants (min 2)

        Returns:
            Decimal: total_pot = stake × num_participants
        """
        stake_dec = self.to_decimal(stake)
        if stake_dec <= Decimal("0"):
            raise ValueError(f"Stake must be positive, got {stake_dec}")
        if num_participants < 2:
            raise ValueError(
                f"Need at least 2 participants, got {num_participants}"
            )
        return (stake_dec * Decimal(num_participants)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

    def calculate_rake(self, total_pot: Decimal) -> Decimal:
        """
        Calculate commission (rake) on a pot.

        Rake = total_pot × rake_rate, rounded to 2 decimal places.

        Args:
            total_pot: Total amount in the pot

        Returns:
            Decimal: rake amount
        """
        total = self.to_decimal(total_pot)
        if total < Decimal("0"):
            raise ValueError(f"Total pot cannot be negative, got {total}")
        return (total * self.rake_rate).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

    def calculate_winner_payout(self, total_pot: Decimal, rake: Decimal) -> Decimal:
        """
        Calculate winner's payout after rake deduction.

        winner_payout = total_pot - rake

        Args:
            total_pot: Total amount in the pot
            rake: Commission amount to deduct

        Returns:
            Decimal: amount paid to winner
        """
        return self.to_decimal(total_pot - rake)

    def settle_pot(
        self,
        stake: float | str | Decimal,
        num_participants: int,
    ) -> SettlementResult:
        """
        Complete pot settlement calculation in one call.

        Args:
            stake: Amount staked per participant
            num_participants: Number of participants (min 2)

        Returns:
            SettlementResult with total_pot, rake, winner_payout, rake_rate

        Example:
            >>> calc = RakeCalculator()
            >>> result = calc.settle_pot(10.00, 2)
            >>> result.total_pot
            Decimal('20.00')
            >>> result.rake
            Decimal('1.40')
            >>> result.winner_payout
            Decimal('18.60')
        """
        total_pot = self.calculate_pot(
            self.to_decimal(stake), num_participants
        )
        rake = self.calculate_rake(total_pot)
        winner_payout = self.calculate_winner_payout(total_pot, rake)
        return SettlementResult(
            total_pot=total_pot,
            rake=rake,
            winner_payout=winner_payout,
            rake_rate=self.rake_rate,
            num_participants=num_participants,
        )

    def split_stake_refund(
        self, stake: float | str | Decimal, num_participants: int
    ) -> list[Decimal]:
        """
        Calculate equal share refund when cancelling a bet.

        Ensures total refunded amounts exactly equal the total pot
        with no rounding discrepancies.

        Args:
            stake: Original stake per participant
            num_participants: Number of participants

        Returns:
            list[Decimal]: Refund amount per participant (all equal)
        """
        stake_dec = self.to_decimal(stake)
        # Simple case: everyone gets their stake back
        return [stake_dec] * num_participants

    def validate_balances(
        self,
        balances: list[Decimal],
        required_stake: Decimal,
    ) -> list[bool]:
        """
        Check which users have sufficient balance for a given stake.

        Args:
            balances: List of user balances
            required_stake: Minimum balance needed

        Returns:
            list[bool]: True if balance >= required_stake for each user
        """
        stake_dec = self.to_decimal(required_stake)
        return [b >= stake_dec for b in (self.to_decimal(b) for b in balances)]


# ── Convenience Functions ─────────────────────────────────────────

def calculate_rake_on_pot(total_pot: float) -> tuple[float, float, float]:
    """
    Quick convenience function for simple rake calculations.

    Args:
        total_pot: Total amount wagered (as float)

    Returns:
        (total_pot, rake, winner_payout) as floats

    Example:
        >>> total, rake, payout = calculate_rake_on_pot(20.00)
        >>> total
        20.0
        >>> rake
        1.4
        >>> payout
        18.6
    """
    calc = RakeCalculator()
    # Infer stake as total_pot / 2 (assumes 2 participants)
    stake = Decimal(str(total_pot)) / Decimal("2")
    result = calc.settle_pot(stake, 2)
    return (
        float(result.total_pot),
        float(result.rake),
        float(result.winner_payout),
    )


def calculate_rake(stake: float, num_participants: int = 2) -> dict:
    """
    Quick convenience function returning a dict.

    Args:
        stake: Amount per participant
        num_participants: Number of participants (default 2)

    Returns:
        dict with total_pot, rake, winner_payout, rake_rate
    """
    calc = RakeCalculator()
    result = calc.settle_pot(stake, num_participants)
    return {
        "total_pot": float(result.total_pot),
        "rake": float(result.rake),
        "winner_payout": float(result.winner_payout),
        "rake_rate": float(result.rake_rate),
        "num_participants": result.num_participants,
    }