"""Name-based matching between followers and kudoers.

Strava's /activities/{id}/kudos endpoint returns kudoers as
(firstname="Joshua", lastname="D.") — first name in full, last name as a
single-letter initial. The followers/following exports give us full names
("Joshua Dupont"). We match on (firstname_lower, last_initial_lower) after
unicode normalisation and accent stripping.
"""

import unicodedata


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _first_letter(s: str) -> str:
    """First letter that is ASCII alphanumeric, or '' if none."""
    for c in s:
        if c.isascii() and c.isalnum():
            return c
    return ""


def normalize_kudoer(firstname: str | None, lastname: str | None) -> tuple[str, str]:
    """Strava kudoer (firstname full, lastname initial) → (first_lower, initial_lower)."""
    f = _strip_accents((firstname or "").strip().lower())
    l = _strip_accents((lastname or "").strip().lower())
    return (f, _first_letter(l))


def normalize_follower(name: str) -> tuple[str, str]:
    """Full name 'Joshua Dupont' → ('joshua', 'd')."""
    parts = name.strip().split(maxsplit=1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    f = _strip_accents(first.lower())
    l = _strip_accents(last.lower())
    return (f, _first_letter(l))
