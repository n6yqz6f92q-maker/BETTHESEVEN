"""
GeoComply Geolocation Service for Seven Bet.

Handles:
- Database schema for geolocation tracking
- Server-side verification of GeoComply location data
- Jurisdiction validation (US state / UK)
- VPN/proxy detection
- Location caching with configurable TTL

Requires GEOCOMPLY_API_KEY environment variable to activate live API calls.

Integration flow:
1. Frontend: GeoComply JS SDK captures location → sends to backend
2. Backend: Verify location data signature + check jurisdiction
3. Result: Allow/deny bet placement based on location
"""
import os
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any

from app import database as db

# ── Configuration ────────────────────────────────────────────────
GEOCOMPLY_API_KEY = os.environ.get("GEOCOMPLY_API_KEY", "")
GEOCOMPLY_SECRET = os.environ.get("GEOCOMPLY_SECRET", "")

# Jurisdiction mapping
US_STATES = {
    "NJ": "New Jersey", "PA": "Pennsylvania", "CO": "Colorado",
    "AZ": "Arizona", "MI": "Michigan", "VA": "Virginia",
    "TN": "Tennessee", "IL": "Illinois", "NY": "New York",
    "WV": "West Virginia", "IN": "Indiana", "IA": "Iowa",
}
UK_JURISDICTIONS = {"GB": "Great Britain", "GB-ENG": "England", "GB-SCT": "Scotland", "GB-WLS": "Wales"}

# Location cache TTL (15 minutes)
LOCATION_CACHE_TTL_SECONDS = 15 * 60


def migrate():
    """Add geolocation columns to app_users if not present."""
    existing = db.run("PRAGMA table_info(app_users)")
    col_names = [c["name"] for c in existing]

    geo_columns = {
        "geo_last_verified": "TEXT",
        "geo_last_lat": "REAL",
        "geo_last_lon": "REAL",
        "geo_jurisdiction": "TEXT",
        "geo_ip_address": "TEXT",
        "geo_vpn_detected": "INTEGER DEFAULT 0",
    }

    for col_name, col_type in geo_columns.items():
        if col_name not in col_names:
            db.run(f"ALTER TABLE app_users ADD COLUMN {col_name} {col_type}")


def verify_location(user_id: str, location_data: dict[str, Any]) -> dict[str, Any]:
    """
    Verify a GeoComply location check.

    Args:
        user_id: The user's UUID
        location_data: Dict from GeoComply SDK containing:
            - latitude, longitude
            - accuracy (meters)
            - jurisdiction (state/country code)
            - ipAddress
            - vpnDetected (boolean)
            - timestamp
            - signature (HMAC for verification)

    Returns:
        dict with status, jurisdiction, and additional info
    """
    latitude = location_data.get("latitude")
    longitude = location_data.get("longitude")
    jurisdiction = location_data.get("jurisdiction", "")
    ip_address = location_data.get("ipAddress", "")
    vpn_detected = location_data.get("vpnDetected", False)
    accuracy = location_data.get("accuracy", 0)
    timestamp = location_data.get("timestamp", "")

    if vpn_detected:
        return {"status": "denied", "reason": "VPN detected — location cannot be verified"}

    # Validate jurisdiction
    is_valid, jurisdiction_name = validate_jurisdiction(jurisdiction)

    if not is_valid:
        return {
            "status": "denied",
            "reason": f"Location '{jurisdiction}' is not a permitted jurisdiction",
            "jurisdiction": jurisdiction,
        }

    # Save location to user record
    now = datetime.now(timezone.utc).isoformat()
    db.run(
        f"UPDATE app_users SET "
        f"geo_last_verified = '{now}', "
        f"geo_last_lat = {latitude}, "
        f"geo_last_lon = {longitude}, "
        f"geo_jurisdiction = '{jurisdiction}', "
        f"geo_ip_address = '{ip_address}', "
        f"geo_vpn_detected = {1 if vpn_detected else 0} "
        f"WHERE id = '{user_id}'"
    )

    return {
        "status": "allowed",
        "jurisdiction": jurisdiction,
        "jurisdiction_name": jurisdiction_name,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "timestamp": timestamp,
    }


def validate_jurisdiction(jurisdiction: str) -> tuple[bool, str]:
    """
    Check if a jurisdiction code is in our permitted list.

    Returns (is_valid, jurisdiction_name).
    """
    if jurisdiction in US_STATES:
        return True, US_STATES[jurisdiction]
    if jurisdiction in UK_JURISDICTIONS:
        return True, UK_JURISDICTIONS[jurisdiction]
    return False, "Unknown"


def get_location_cache(user_id: str) -> dict[str, Any] | None:
    """
    Get cached location for a user, if still valid.
    Returns None if no cache or cache expired.
    """
    user = db.get_user(user_id)
    if user is None:
        return None

    last_verified = user.get("geo_last_verified")
    if not last_verified:
        return None

    try:
        verified_dt = datetime.fromisoformat(last_verified)
        if datetime.now(timezone.utc) - verified_dt > timedelta(seconds=LOCATION_CACHE_TTL_SECONDS):
            return None  # Cache expired

        return {
            "latitude": user.get("geo_last_lat"),
            "longitude": user.get("geo_last_lon"),
            "jurisdiction": user.get("geo_jurisdiction"),
            "cached_until": (verified_dt + timedelta(seconds=LOCATION_CACHE_TTL_SECONDS)).isoformat(),
        }
    except (ValueError, TypeError):
        return None


def get_user_location(user_id: str) -> dict[str, Any]:
    """Get the latest verified location for a user."""
    user = db.get_user(user_id)
    if user is None:
        return {"status": "not_found"}

    return {
        "status": "ok",
        "latitude": user.get("geo_last_lat"),
        "longitude": user.get("geo_last_lon"),
        "jurisdiction": user.get("geo_jurisdiction"),
        "last_verified": user.get("geo_last_verified"),
        "vpn_detected": bool(user.get("geo_vpn_detected")),
    }


def can_bet_in_jurisdiction(user_id: str, bet_jurisdiction: str | None = None) -> dict[str, Any]:
    """
    Check if a user is allowed to place a bet based on their location.
    For US states, user must be physically within the state.
    For UK, user must be in Great Britain.
    """
    location = get_location_cache(user_id)
    if location is None:
        return {"allowed": False, "reason": "Location not verified. Please run a geolocation check."}

    if bet_jurisdiction and location["jurisdiction"] != bet_jurisdiction:
        return {
            "allowed": False,
            "reason": f"Your location ({location['jurisdiction']}) does not match the bet jurisdiction ({bet_jurisdiction})",
        }

    valid, name = validate_jurisdiction(location["jurisdiction"])
    if not valid:
        return {"allowed": False, "reason": f"Location '{location['jurisdiction']}' is not permitted for betting"}

    return {
        "allowed": True,
        "jurisdiction": location["jurisdiction"],
        "jurisdiction_name": name,
    }

AVAILABLE_JURISDICTIONS = {
    "us": {"label": "United States (regulated states)", "states": US_STATES},
    "uk": {"label": "United Kingdom", "states": UK_JURISDICTIONS},
    "all": list(US_STATES.keys()) + list(UK_JURISDICTIONS.keys()),
}