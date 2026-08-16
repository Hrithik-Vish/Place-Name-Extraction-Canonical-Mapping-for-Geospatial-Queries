"""
Task 8 — Nominatim Fallback (Owner: Member 4)

When Member 3's local GeoNames lookup (Task 7) returns zero candidates for a
cleaned name, this module calls Nominatim's /search endpoint as a live backup,
scoped to India only (countrycodes=in).

India-only scoping rationale (see member4_tasks.md v2):
  The system's entire resolution scope is India for v1 — the local GeoNames
  data is India-specific, and an unscoped Nominatim fallback risks a false-
  positive match against a same-named place in another country. Scoping
  Nominatim to India keeps the pipeline's geographic boundary consistent.

Returns a Candidate (from disambiguation.py) or None.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

# Import the Candidate dataclass from disambiguation — this is the normalized
# shape both local GeoNames (Task 7) and Nominatim results must share so
# Task 9 (disambiguation) can treat them identically.
from backend.disambiguation import Candidate


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

# Required by Nominatim's usage policy — requests without a descriptive
# User-Agent may be blocked.
USER_AGENT = "ps09-place-resolver/1.0"

# Short timeout — a fast, clean "failed" is better than a slow hang (per
# member4_tasks.md). 5 seconds is generous for a single geocoding lookup.
REQUEST_TIMEOUT_SECONDS = 5

# Nominatim rate limit: 1 request/second. Track the last call time globally
# to enforce this even across multiple calls in the same request.
_last_call_time: float = 0.0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def nominatim_fallback(cleaned_name: str) -> Optional[Candidate]:
    """Call Nominatim as a live backup for a name with zero local candidates.

    Args:
        cleaned_name: The post-cleanup name string (from Task 6).

    Returns:
        A Candidate with source="nominatim_fallback" if Nominatim finds a
        match in India, or None if:
          - Nominatim returns no results (expected for non-Indian names)
          - The request times out
          - Any HTTP/network error occurs

        Returning None signals Task 9/13 to construct a "failed" entry.
        This function never raises — all errors are caught and logged.
    """
    global _last_call_time

    # Rate limiting: wait if needed to respect 1 req/sec
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    try:
        resp = requests.get(
            NOMINATIM_SEARCH_URL,
            params={
                "q": cleaned_name,
                "format": "json",
                "countrycodes": "in",  # India-only — see module docstring
                "limit": "1",         # best guess only, not a candidate list
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _last_call_time = time.time()

        resp.raise_for_status()
        results = resp.json()

        if not results:
            # No match found in India — expected for non-Indian names
            return None

        hit = results[0]

        # Normalize into the same Candidate shape as local GeoNames results.
        # Use the short 'name' field if available, otherwise extract from
        # display_name (which is typically "Name, District, State, India").
        display_name = hit.get("display_name", cleaned_name)
        name = hit.get("name", display_name.split(",")[0].strip())

        return Candidate(
            name=name,
            lat=float(hit["lat"]),
            long=float(hit["lon"]),
            population=0,  # Nominatim doesn't return population data
            admin1=None,    # Could be parsed from display_name but not needed for MVP
            admin2=None,
            source="nominatim_fallback",
        )

    except requests.Timeout:
        # Timeout is treated the same as "no match found" — don't hang
        print(f"  [nominatim] Timeout for '{cleaned_name}' after {REQUEST_TIMEOUT_SECONDS}s")
        _last_call_time = time.time()
        return None

    except requests.RequestException as e:
        # Network errors, HTTP errors — log and return None
        print(f"  [nominatim] Request failed for '{cleaned_name}': {e}")
        _last_call_time = time.time()
        return None

    except (KeyError, ValueError, IndexError) as e:
        # Malformed response — shouldn't happen but don't crash
        print(f"  [nominatim] Unexpected response format for '{cleaned_name}': {e}")
        _last_call_time = time.time()
        return None
