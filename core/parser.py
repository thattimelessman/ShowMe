# ─────────────────────────────────────────
#  ShowMe — core/parser.py
#  Extracts the target from a transcript.
#  "show me google chrome" → "google chrome"
#  "hey show me vs code please" → "vs code"
# ─────────────────────────────────────────

import re
import logging
from config import TRIGGER_PHRASE

log = logging.getLogger("showme.parser")

# words to strip from the end of a command (noise words)
NOISE_WORDS = {"please", "now", "open", "up", "the", "app", "application"}


def extract_target(transcript: str) -> str | None:
    """
    Given a full transcript string, finds the trigger phrase
    and returns whatever comes after it, cleaned up.

    Returns None if trigger phrase not found.

    Examples:
        "show me chrome"             → "chrome"
        "show me need for speed"     → "need for speed"
        "hey show me vs code please" → "vs code"
        "what is the weather"        → None
    """
    text = transcript.lower().strip()

    # find trigger phrase position
    idx = text.find(TRIGGER_PHRASE)
    if idx == -1:
        return None

    # grab everything after "show me"
    after = text[idx + len(TRIGGER_PHRASE):].strip()

    if not after:
        return None

    # remove trailing noise words
    words = after.split()
    while words and words[-1] in NOISE_WORDS:
        words.pop()

    # remove leading noise words
    while words and words[0] in NOISE_WORDS:
        words.pop(0)

    target = " ".join(words).strip()

    if not target:
        return None

    log.debug(f"Parsed target: '{transcript}' → '{target}'")
    return target
