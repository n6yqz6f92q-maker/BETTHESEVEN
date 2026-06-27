"""
Gold Upgrade — Service Layer for Seven Bet (Open Access).

Handles:
- Database schema for Gold Upgrade passes
- Stripe payment links (redirect-based)
- Pass activation on payment confirmation
- Effective rake rate calculation based on user's Gold tier
- ROI calculator
"""
import os
import uuid, asyncio
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from datetime import datetime, timezone
from typing import Any

from app import database as db

# ── Gold Upgrade Tier Definitions ───────────────────────────────
# Free users get 7% rake by default (no pass needed).
# Gold Upgrade purchasers receive reduced commission rates on Premium+.
TIERS = {
    "entry": {
        "name": "Entry Gold",
        "price_gbp": Decimal("49.00"),
        "max_supply": 1000,
        "commission_discount": Decimal("0.07"),
        "staking_multiplier": 1.0,
        "beta_priority": 4,
        "stripe_price_id": "price_1TmQsiRbpiz4krgRJHewfqiV",
        "stripe_payment_link": "https://buy.stripe.com/cNi8wRdsZ2AwgZseh3cQU0f",
        "is_concierge": False,
    },
    "standard": {
        "name": "Standard Gold",
        "price_gbp": Decimal("199.00"),
        "max_supply": 350,
        "commission_discount": Decimal("0.07"),
        "staking_multiplier": 1.0,
        "beta_priority": 3,
        "stripe_price_id": "price_1Tl4w1Rbpiz4krgR40cw46V4",
        "stripe_payment_link": "https://buy.stripe.com/bJe28t9cJa2Y5gK2ylcQU05",
        "is_concierge": False,
    },
    "premium": {
        "name": "Premium Gold",
        "price_gbp": Decimal("999.00"),
        "max_supply": 125,
        "commission_discount": Decimal("0.05"),
        "staking_multiplier": 2.0,
        "beta_priority": 2,
        "stripe_price_id": "price_1Tl4w3Rbpiz4krgRTE4gzHHN",
        "stripe_payment_link": "https://buy.stripe.com/14A9AVex3fni5gKa0NcQU06",
        "is_concierge": False,
    },
    "founding_patron": {
        "name": "Founding Patron",
        "price_gbp": Decimal("4999.00"),
        "max_supply": 18,
        "commission_discount": Decimal("0.04"),
        "staking_multiplier": 5.0,
        "beta_priority": 1,
        "stripe_price_id": "price_1Tl4w5Rbpiz4krgRD8RjKiFy",
        "stripe_payment_link": "https://buy.stripe.com/dRm3cx74B7UQ38Ceh3cQU07",
        "is_concierge": False,
    },
    "the_seven": {
        "name": "The Seven",
        "price_gbp": Decimal("17777.00"),
        "max_supply": 7,
        "commission_discount": Decimal("0.03"),
        "staking_multiplier": 10.0,
        "beta_priority": 0,
        "stripe_price_id": "price_1Tl4w8Rbpiz4krgRvbAecoxh",
        "stripe_payment_link": "https://buy.stripe.com/7sY8wR4Wtb725gK0qdcQU08",
        "is_concierge": True,
        "concierge_email": "concierge@sevenbet.com",
    },
}

DEFAULT_RAKE = Decimal("0.07")
VALID_TIERS = "('" + "','".join(TIERS.keys()) + "')"


def migrate():
    """Create Gold Upgrade tables and seed sequences. Idempotent."""
    db.run(f"""
        CREATE TABLE IF NOT EXISTS app_founder_passes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            founder_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','used','refunded','cancelled')),
            purchase_price REAL NOT NULL,
            commission_discount REAL NOT NULL,
            staking_multiplier REAL NOT NULL DEFAULT 1.0,
            beta_priority INTEGER NOT NULL,
            stripe_session_id TEXT,
            purchased_at TEXT NOT NULL,
            activated_at TEXT,
            redeemed_roadmap_votes INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES app_users(id)
        )
    """)
    db.run("""
        CREATE TABLE IF NOT EXISTS app_founder_sequence (
            tier TEXT PRIMARY KEY,
            next_number INTEGER NOT NULL DEFAULT 1,
            max_supply INTEGER NOT NULL
        )
    """)
    for tier_key, tier_data in TIERS.items():
        existing = db.run(
            f"SELECT next_number FROM app_founder_sequence WHERE tier = '{tier_key}'"
        )
        if not existing:
            db.run(
                f"INSERT INTO app_founder_sequence (tier, next_number, max_supply) "
                f"VALUES ('{tier_key}', 1, {tier_data['max_supply']})"
            )
        else:
            db.run(
                f"UPDATE app_founder_sequence SET max_supply = {tier_data['max_supply']} "
                f"WHERE tier = '{tier_key}'"
            )


def get_availability() -> dict[str, Any]:
    """Return remaining Gold Upgrade count per tier."""
    result = {}
    for tier_key, tier_data in TIERS.items():
        rows = db.run(
            f"SELECT COUNT(*) as cnt FROM app_founder_passes "
            f"WHERE tier = '{tier_key}' AND status IN ('active', 'used')"
        )
        sold = rows[0]["cnt"] if rows else 0
        result[tier_key] = {
            "name": tier_data["name"],
            "price_gbp": float(tier_data["price_gbp"]),
            "total": tier_data["max_supply"],
            "sold": sold,
            "remaining": tier_data["max_supply"] - sold,
            "commission_discount": float(tier_data["commission_discount"]),
            "staking_multiplier": tier_data["staking_multiplier"],
            "beta_priority": tier_data["beta_priority"],
            "is_concierge": tier_data.get("is_concierge", False),
            "stripe_payment_link": tier_data.get("stripe_payment_link", ""),
            "stripe_price_id": tier_data.get("stripe_price_id", ""),
        }
    return result


def get_purchase_info(tier: str) -> dict[str, Any]:
    """Get purchase info for a Gold Upgrade tier."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    tier_data = TIERS[tier]
    availability = get_availability()
    if availability[tier]["remaining"] <= 0:
        raise ValueError(f"Sorry, the {tier_data['name']} tier is sold out!")
    info = {
        "tier": tier,
        "name": tier_data["name"],
        "price_gbp": float(tier_data["price_gbp"]),
        "is_concierge": tier_data.get("is_concierge", False),
        "remaining": availability[tier]["remaining"],
    }
    if tier_data.get("is_concierge"):
        info["concierge_email"] = tier_data["concierge_email"]
        info["message"] = (
            f"The {tier_data['name']} tier (£{float(tier_data['price_gbp']):,.0f}) "
            f"is by application only. Please email {tier_data['concierge_email']} "
            f"with your name and betting background."
        )
    else:
        info["stripe_payment_link"] = tier_data["stripe_payment_link"]
        info["stripe_price_id"] = tier_data["stripe_price_id"]
    return info


def get_my_pass(user_id: str) -> dict[str, Any] | None:
    """Return the current user's active Gold Upgrade pass."""
    rows = db.run(
        f"SELECT * FROM app_founder_passes "
        f"WHERE user_id = '{user_id}' AND status IN ('active', 'used') "
        f"ORDER BY purchased_at DESC LIMIT 1"
    )
    if rows:
        return rows[0]
    return None


def get_pass_by_username(username: str) -> dict[str, Any] | None:
    """Look up a pass by username."""
    user = db.get_user_by_username(username)
    if user is None:
        return None
    return get_my_pass(user["id"])


def get_hall_of_fame() -> list[dict[str, Any]]:
    """Public listing of all Gold members."""
    return db.run(
        f"SELECT p.founder_number, p.tier, p.purchased_at, "
        f"u.username "
        f"FROM app_founder_passes p "
        f"JOIN app_users u ON u.id = p.user_id "
        f"WHERE p.status IN ('active', 'used') "
        f"ORDER BY p.founder_number ASC"
    )


def get_effective_rake(user_id: str) -> Decimal:
    """
    Get the effective rake rate for a user.

    Free users (no pass): 7%
    Entry/Standard Gold: 7% (badge only, same rate)
    Premium Gold: 5%
    Founding Patron: 4%
    The Seven: 3%
    """
    my_pass = get_my_pass(user_id)
    if my_pass is None:
        return DEFAULT_RAKE

    tier = my_pass["tier"]
    if tier not in TIERS:
        return DEFAULT_RAKE

    tier_discount = TIERS[tier]["commission_discount"]
    # Only apply discount if it's lower than default
    if tier_discount < DEFAULT_RAKE:
        return tier_discount
    return DEFAULT_RAKE


def activate_pass(tier: str, user_id: str, payment_ref: str = "") -> dict[str, Any]:
    """Activate a Gold Upgrade after payment is confirmed."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")

    tier_data = TIERS[tier]
    seq_rows = db.run(
        f"SELECT next_number, max_supply FROM app_founder_sequence WHERE tier = '{tier}'"
    )
    if not seq_rows:
        raise ValueError(f"No sequence for tier: {tier}")

    next_number = seq_rows[0]["next_number"]
    max_supply = seq_rows[0]["max_supply"]

    if next_number > max_supply:
        raise ValueError(f"Tier {tier} is sold out")

    now = datetime.now(timezone.utc).isoformat()
    pass_id = str(uuid.uuid4())

    db.run(
        f"INSERT INTO app_founder_passes "
        f"(id, user_id, tier, founder_number, status, purchase_price, "
        f"commission_discount, staking_multiplier, beta_priority, "
        f"stripe_session_id, purchased_at) "
        f"VALUES ("
        f"'{pass_id}', '{user_id}', '{tier}', {next_number}, 'active', "
        f"{float(tier_data['price_gbp'])}, {float(tier_data['commission_discount'])}, "
        f"{tier_data['staking_multiplier']}, {tier_data['beta_priority']}, "
        f"'{payment_ref}', '{now}'"
        f")"
    )
    try:
        from app.services import updates
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(updates.notify_scarcity_update(get_availability()))
            user = db.get_user(user_id)
            user_name = user.get("username", "A Founder") if user else "A Founder"
            loop.create_task(updates.notify_sale(tier, user_name))
    except Exception:
        pass

    db.run(
        f"UPDATE app_founder_sequence SET next_number = next_number + 1 "
        f"WHERE tier = '{tier}'"
    )

    return {
        "id": pass_id,
        "user_id": user_id,
        "tier": tier,
        "founder_number": next_number,
        "commission_discount": float(tier_data["commission_discount"]),
        "staking_multiplier": tier_data["staking_multiplier"],
        "purchased_at": now,
    }


def cancel_pass(pass_id: str, user_id: str) -> dict[str, Any]:
    """Cancel/refund a Gold Upgrade pass."""
    rows = db.run(
        f"SELECT * FROM app_founder_passes WHERE id = '{pass_id}' AND user_id = '{user_id}'"
    )
    if not rows:
        raise ValueError("Pass not found or doesn't belong to you")

    pass_data = rows[0]
    if pass_data["status"] != "active":
        raise ValueError(f"Pass is already {pass_data['status']}")

    db.run(f"UPDATE app_founder_passes SET status = 'refunded' WHERE id = '{pass_id}'")
    try:
        import asyncio
        from app.services import updates
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(updates.notify_scarcity_update(get_availability()))
    except Exception:
        pass
    return {"ok": True, "message": "Pass cancelled and refunded"}


def calculate_roi(monthly_volume: float) -> list[dict[str, Any]]:
    """Calculate ROI for all Gold tiers at a given monthly betting volume."""
    monthly = Decimal(str(monthly_volume))
    results = []

    for tier_key, tier_data in TIERS.items():
        if tier_key in ("entry", "standard"):
            results.append({
                "tier": tier_key,
                "name": tier_data["name"],
                "price": float(tier_data["price_gbp"]),
                "rate": float(tier_data["commission_discount"]),
                "savings_per_month": 0.0,
                "months_to_breakeven": None,
                "year_1_net": float(-tier_data["price_gbp"]),
                "year_1_roi_pct": -100.0,
            })
            continue

        standard_rate = Decimal("0.07")
        tier_rate = tier_data["commission_discount"]
        rate_diff = standard_rate - tier_rate
        monthly_savings = monthly * rate_diff
        price = tier_data["price_gbp"]

        if monthly_savings > 0:
            months_breakeven = (price / monthly_savings).quantize(Decimal("1"), rounding=ROUND_CEILING)
            year_1_savings = monthly_savings * 12
            year_1_net = year_1_savings - price
            year_1_roi = ((year_1_savings - price) / price * 100)
        else:
            months_breakeven = None
            year_1_net = -price
            year_1_roi = Decimal("-100")

        results.append({
            "tier": tier_key,
            "name": tier_data["name"],
            "price": float(price),
            "rate": float(tier_rate),
            "savings_per_month": float(monthly_savings.quantize(Decimal("0.01"))),
            "months_to_breakeven": int(months_breakeven) if months_breakeven else None,
            "year_1_net": float(year_1_net.quantize(Decimal("0.01"))),
            "year_1_roi_pct": float(year_1_roi.quantize(Decimal("0.1"))),
        })

    return results
