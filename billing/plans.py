"""
CookieGuard Plan Configuration

Central configuration for all plan tiers and their limits/features.
Limits can be overridden via environment variables.
"""
import os

PLAN_TIERS = ("free", "pro", "multi_site")

# Environment-configurable limits with sensible defaults
FREE_PAGEVIEWS = int(os.getenv("FREE_PAGEVIEWS", 250))
FREE_DOMAINS = int(os.getenv("FREE_DOMAINS", 1))
PRO_PAGEVIEWS = int(os.getenv("PRO_PAGEVIEWS", 10000))
PRO_DOMAINS = int(os.getenv("PRO_DOMAINS", 3))
MULTI_SITE_PAGEVIEWS = int(os.getenv("MULTI_SITE_PAGEVIEWS", 50000))
MULTI_SITE_DOMAINS = int(os.getenv("MULTI_SITE_DOMAINS", 10))
PAGEVIEW_GRACE_PERCENT = float(os.getenv("PAGEVIEW_GRACE_PERCENT", 15)) / 100  # Convert 15 -> 0.15

PLAN_LIMITS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "stripe_lookup_key": None,  # No Stripe for free tier
        "domains": FREE_DOMAINS,
        "pageviews_per_month": FREE_PAGEVIEWS,
        "pageviews_grace_percent": PAGEVIEW_GRACE_PERCENT,
        "auto_scan": None,  # manual only
        "banner_customization": "basic",
        "remove_branding": False,
        "email_reports": False,
        "csv_export": False,
        "cookie_categorization": "manual",  # Must classify cookies manually
        "auto_classification": False,  # Auto-classify from database
        "audit_logs": False,
        "team_members": 0,
        "priority_support": False,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 12,
        "stripe_lookup_key": "cg_pro_monthly",
        "domains": PRO_DOMAINS,
        "pageviews_per_month": PRO_PAGEVIEWS,
        "pageviews_grace_percent": PAGEVIEW_GRACE_PERCENT,
        "auto_scan": "weekly",
        "banner_customization": "full",
        "remove_branding": True,
        "email_reports": True,
        "csv_export": True,
        "cookie_categorization": "auto",  # Auto-classification from database
        "auto_classification": True,  # Auto-classify from database
        "audit_logs": False,
        "team_members": 0,
        "priority_support": False,
    },
    "multi_site": {
        "name": "Multi-Site",
        "price_monthly": 30,
        "stripe_lookup_key": "cg_multi_site_monthly",
        "domains": MULTI_SITE_DOMAINS,
        "pageviews_per_month": MULTI_SITE_PAGEVIEWS,
        "pageviews_grace_percent": PAGEVIEW_GRACE_PERCENT,
        "auto_scan": "daily",
        "banner_customization": "full",
        "remove_branding": True,
        "email_reports": True,
        "csv_export": True,
        "cookie_categorization": "auto",  # Auto-classification from database
        "auto_classification": True,  # Auto-classify from database
        "audit_logs": True,
        "team_members": 3,
        "priority_support": True,
    },
}

# Human-readable feature descriptions for the pricing page
FEATURE_DESCRIPTIONS = {
    "domains": {
        "name": "Domains",
        "description": "Number of websites you can monitor",
    },
    "pageviews_per_month": {
        "name": "Monthly Pageviews",
        "description": "Banner impressions tracked per month",
    },
    "auto_scan": {
        "name": "Auto Scanning",
        "description": "Automatic cookie scanning frequency",
        "values": {
            None: "Manual only",
            "weekly": "Weekly",
            "daily": "Daily",
        },
    },
    "banner_customization": {
        "name": "Banner Customization",
        "description": "Cookie banner styling options",
        "values": {
            "basic": "Basic colors & text",
            "full": "Full CSS control, themes, positions",
        },
    },
    "remove_branding": {
        "name": "Remove Branding",
        "description": "Hide 'Powered by CookieGuard' badge",
    },
    "email_reports": {
        "name": "Email Reports",
        "description": "Monthly compliance reports via email",
    },
    "csv_export": {
        "name": "CSV Export",
        "description": "Export cookie data and consent logs",
    },
    "cookie_categorization": {
        "name": "Cookie Categorization",
        "description": "How cookies are classified",
        "values": {
            "manual": "Manual classification required",
            "auto": "Auto-classified from database",
        },
    },
    "auto_classification": {
        "name": "Auto Classification",
        "description": "Automatically classify cookies from our database of 90+ known cookies",
    },
    "audit_logs": {
        "name": "Audit Logs",
        "description": "Detailed logs of all consent changes",
    },
    "team_members": {
        "name": "Team Members",
        "description": "Additional users on your account",
    },
    "priority_support": {
        "name": "Priority Support",
        "description": "Fast-track email support response",
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
