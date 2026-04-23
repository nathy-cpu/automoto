import random
import time
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone


CHALLENGE_MARKERS = (
    "cf-challenge",
    "__cf_chl_",
    "challenge-form",
    "g-recaptcha",
    "hcaptcha",
    "captcha-delivery",
    "verify you are human",
    "security check",
    "unusual traffic",
    "/sorry/index",
)
BLOCK_STATUS_CODES = {403, 429, 503}
FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 60 * 60


def classify_anti_bot_response(status_code=None, html_content="", card_count=0):
    content = (html_content or "").lower()
    matched_markers = [marker for marker in CHALLENGE_MARKERS if marker in content]

    if card_count > 0 and status_code not in BLOCK_STATUS_CODES:
        return {
            "blocked": False,
            "reason": "",
            "matched_markers": matched_markers,
        }

    blocked = status_code in BLOCK_STATUS_CODES or bool(matched_markers)
    if not blocked:
        return {"blocked": False, "reason": "", "matched_markers": []}

    reasons = []
    if status_code in BLOCK_STATUS_CODES:
        reasons.append(f"status={status_code}")
    if matched_markers and card_count == 0:
        reasons.append("markers=" + ",".join(matched_markers[:3]))
    elif matched_markers and status_code in BLOCK_STATUS_CODES:
        reasons.append("markers=" + ",".join(matched_markers[:3]))

    return {
        "blocked": True,
        "reason": "; ".join(reasons) or "challenge_detected",
        "matched_markers": matched_markers,
    }


def compute_selector_coverage(cards, selectors):
    total_cards = len(cards)
    coverage = {}
    for field, selector in selectors.items():
        hits = 0
        if selector:
            hits = sum(1 for card in cards if card.select_one(selector))
        coverage[field] = {"hits": hits, "total": total_cards}
    return coverage


def summarize_selector_coverage(coverage):
    parts = []
    for field, counts in coverage.items():
        total = counts.get("total", 0)
        hits = counts.get("hits", 0)
        pct = int((hits / total) * 100) if total else 0
        parts.append(f"{field}={hits}/{total}({pct}%)")
    return " ".join(parts)


def record_block_event(website_id, threshold=FAILURE_THRESHOLD, cooldown_seconds=COOLDOWN_SECONDS):
    failure_key = _failure_key(website_id)
    cooldown_key = _cooldown_key(website_id)
    failures = int(cache.get(failure_key, 0)) + 1
    cache.set(failure_key, failures, timeout=cooldown_seconds)

    cooldown_until = None
    if failures >= threshold:
        cooldown_until = timezone.now() + timedelta(seconds=cooldown_seconds)
        cache.set(cooldown_key, cooldown_until.isoformat(), timeout=cooldown_seconds)

    return {"failures": failures, "cooldown_until": cooldown_until}


def clear_block_state(website_id):
    cache.delete(_failure_key(website_id))
    cache.delete(_cooldown_key(website_id))


def get_cooldown_remaining(website_id):
    raw_value = cache.get(_cooldown_key(website_id))
    if not raw_value:
        return 0

    cooldown_until = timezone.datetime.fromisoformat(raw_value)
    remaining = int((cooldown_until - timezone.now()).total_seconds())
    if remaining <= 0:
        clear_block_state(website_id)
        return 0
    return remaining


def jitter_sleep(min_seconds, max_seconds):
    time.sleep(random.uniform(min_seconds, max_seconds))


def _failure_key(website_id):
    return f"scraper_antibot_failures_{website_id}"


def _cooldown_key(website_id):
    return f"scraper_antibot_cooldown_{website_id}"
