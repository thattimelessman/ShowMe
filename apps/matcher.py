# ─────────────────────────────────────────
#  ShowMe — apps/matcher.py
#  Fuzzy matches a spoken app name against
#  the installed app dictionary.
# ─────────────────────────────────────────

import logging
from rapidfuzz import process, fuzz
from config import MATCH_THRESHOLD, CUSTOM_MAPPINGS

log = logging.getLogger("showme.matcher")


def _apply_custom(query: str) -> str:
    """
    Check custom alias mappings first.
    e.g. "vs code" → "code", "nfs" → "need for speed"
    Returns the mapped value or original query.
    """
    q = query.lower().strip()
    if q in CUSTOM_MAPPINGS:
        mapped = CUSTOM_MAPPINGS[q]
        log.debug(f"Custom mapping: '{q}' → '{mapped}'")
        return mapped
    return q


def find_app(query: str, app_dict: dict) -> tuple[str, str] | None:
    """
    Given a spoken query string and the full app dictionary,
    returns (app_name, app_path) for the best match,
    or None if no confident match found.

    Steps:
    1. Apply custom alias overrides
    2. Try exact match first (fastest)
    3. Fuzzy match using token_sort_ratio (handles word order)
    4. Return only if score >= MATCH_THRESHOLD
    """
    if not query or not app_dict:
        return None

    query = _apply_custom(query)

    # 1. Exact match
    if query in app_dict:
        log.info(f"Exact match: '{query}' → {app_dict[query]}")
        return (query, app_dict[query])

    # 2. Fuzzy match — token_sort_ratio handles
    #    "need for speed most wanted" vs "nfs most wanted 2012"
    result = process.extractOne(
        query,
        app_dict.keys(),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=MATCH_THRESHOLD
    )

    if result is None:
        log.warning(f"No match found for: '{query}'")
        return None

    matched_name, score, _ = result
    matched_path = app_dict[matched_name]
    log.info(f"Fuzzy match: '{query}' → '{matched_name}' (score={score}) → {matched_path}")
    return (matched_name, matched_path)
