import secrets

from django.core.cache import cache


CACHE_PREFIX = "validatesap-comparison"


def store_comparison_snapshot(tumbling_name, comparison_results) -> str:
    token = secrets.token_urlsafe(32)
    cache.set(
        f"{CACHE_PREFIX}:{token}",
        {"tumbling_name": tumbling_name, "comparison_results": comparison_results},
        timeout=60 * 60,
    )
    return token


def load_comparison_snapshot(token: str):
    if not token:
        return None
    return cache.get(f"{CACHE_PREFIX}:{token}")
