from django.conf import settings
from django.core.cache import cache


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def should_skip_rate_limit(request):
    path = request.path
    return path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL)


def record_request_limit(namespace, identifier, limit, window_seconds):
    cache_key = f"ratelimit:{namespace}:{identifier}"
    added = cache.add(cache_key, 1, timeout=window_seconds)
    if added:
        return False, 1

    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window_seconds)
        count = 1
    return count > limit, count
