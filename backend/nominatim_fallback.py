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

Contract with main.py:
  main.py imports this module as:
      from nominatim_fallback import lookup_nominatim
  and expects lookup_nominatim(cleaned_name) -> list[dict], the SAME shape
  geonames_lookup.lookup_local() returns (name/lat/long/population/admin1/
  admin2/source) — both sources get normalized into disambiguation.py's
  Candidate dataclass by main.py's _to_candidates() helper. This module
  intentionally returns a plain dict list, not a Candidate, so it stays
  consistent with Task 7's output shape per backend_build.md Task 8's own
  description ("normalize whatever Nominatim returns into the same shape a
  local GeoNames candidate would have").

  Returns an empty list (not None) when nothing is found — lookup_local()
  also returns [] on no matches, so main.py's "if local_candidates:" /
  "elif NOMINATIM_AVAILABLE:" branching stays symmetric between the two
  sources without needing None-checks anywhere else.
"""

from __future__ import annotations

import time
from typing import Optional

import requests


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

def lookup_nominatim(cleaned_name: str) -> list[dict]:
    """Call Nominatim as a live backup for a name with zero local candidates.

    Args:
        cleaned_name: The post-cleanup name string (from Task 6).

    Returns:
        A list containing zero or one candidate dict, shaped like
        geonames_lookup.lookup_local()'s output:
            {
                "name": str,
                "lat": float,
                "long": float,
                "population": int,   # always 0 — Nominatim doesn't provide this
                "admin1": str | None,
                "admin2": str | None,
                "source": "nominatim_fallback",
            }

        Empty list [] if:
          - Nominatim returns no results (expected for non-Indian names,
            e.g. "Springfield" under India-only scoping)
          - The request times out
          - Any HTTP/network error occurs

        An empty list signals main.py to fall through to a "failed" entry
        via disambiguation.py (zero candidates from both Task 7 and Task 8).
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
                "limit": "1",          # best guess only, not a candidate list
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _last_call_time = time.time()

        resp.raise_for_status()
        results = resp.json()

        if not results:
            # No match found in India — expected for non-Indian names
            return []

        hit = results[0]

        # Use the short 'name' field if available, otherwise extract from
        # display_name (typically "Name, District, State, India").
        display_name = hit.get("display_name", cleaned_name)
        name = hit.get("name") or display_name.split(",")[0].strip()

        return [{
            "name": name,
            "lat": float(hit["lat"]),
            "long": float(hit["lon"]),
            "population": 0,  # Nominatim doesn't return population data
            "admin1": None,   # Could be parsed from display_name; not needed for MVP
            "admin2": None,
            "source": "nominatim_fallback",
        }]

    except requests.Timeout:
        # Timeout is treated the same as "no match found" — don't hang
        print(f"  [nominatim] Timeout for '{cleaned_name}' after {REQUEST_TIMEOUT_SECONDS}s")
        _last_call_time = time.time()
        return []

    except requests.RequestException as e:
        # Network errors, HTTP errors — log and return empty
        print(f"  [nominatim] Request failed for '{cleaned_name}': {e}")
        _last_call_time = time.time()
        return []

    except (KeyError, ValueError, IndexError) as e:
        # Malformed response — shouldn't happen but don't crash
        print(f"  [nominatim] Unexpected response format for '{cleaned_name}': {e}")
        _last_call_time = time.time()
        return []


# Test
if __name__ == "__main__":
    print(lookup_nominatim("Pune"))         # Should return a real candidate
    print(lookup_nominatim("Springfield"))  # Should return [] (India-only scoping)