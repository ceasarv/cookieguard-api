"""
CookieGuard Plan Configuration

Central configuration for all plan tiers and their limits/features.
"""

PLAN_TIERS = ("free", "pro", "agency")

PLAN_LIMITS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "stripe_lookup_key": None,  # No Stripe for free tier
        "domains": 1,
        "pageviews_per_month": 1000,
        "pageviews_grace_percent": 0.15,  # 15% grace = 1,150 total
        "auto_scan": None,  # manual only
        "banner_customization": "basic",
        "remove_branding": False,
        "email_reports": False,
        "csv_export": False,
        "cookie_categorization": False,
        "audit_logs": False,
        "team_members": 0,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 12,
        "stripe_lookup_key": "cg_pro_monthly",
        "domains": 3,
        "pageviews_per_month": 10000,
        "pageviews_grace_percent": 0.15,  # 15% grace = 11,500 total
        "auto_scan": "monthly",
        "banner_customization": "full",
        "remove_branding": True,
        "email_reports": True,
        "csv_export": True,
        "cookie_categorization": True,
        "audit_logs": False,
        "team_members": 0,
    },
    "agency": {
        "name": "Agency",
        "price_monthly": 30,
        "stripe_lookup_key": "cg_agency_monthly",
        "domains": 10,
        "pageviews_per_month": 50000,
        "pageviews_grace_percent": 0.15,  # 15% grace = 57,500 total
        "auto_scan": "weekly",
        "banner_customization": "full",
        "remove_branding": True,
        "email_reports": True,
        "csv_export": True,
        "cookie_categorization": True,
        "audit_logs": True,
        "team_members": 3,
    },
}

# Map Stripe lookup keys to plan tiers
STRIPE_LOOKUP_TO_TIER = {
    config["stripe_lookup_key"]: tier
    for tier, config in PLAN_LIMITS.items()
    if config["stripe_lookup_key"]
}


def get_plan_config(plan_tier: str) -> dict:
    """Get full configuration for a plan tier."""
    return PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["free"])


def get_plan_limit(plan_tier: str, feature: str):
    """Get a specific limit for a plan tier."""
    return get_plan_config(plan_tier).get(feature)


def get_effective_pageview_limit(plan_tier: str) -> int:
    """Get pageview limit including 15% grace period."""
    plan = get_plan_config(plan_tier)
    base = plan["pageviews_per_month"]
    grace = plan["pageviews_grace_percent"]
    return int(base * (1 + grace))


def get_tier_from_lookup_key(lookup_key: str) -> str:
    """Get plan tier from Stripe lookup key. Returns 'free' if not found."""
    return STRIPE_LOOKUP_TO_TIER.get(lookup_key, "free")


def has_feature(plan_tier: str, feature: str) -> bool:
    """Check if a plan tier has a specific feature enabled."""
    value = get_plan_limit(plan_tier, feature)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if value is None:
        return False
    return bool(value)
