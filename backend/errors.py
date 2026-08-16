"""
Task 13 — Error Handling (Owner: Member 4)

Helpers that produce the exact response shapes defined in contract.md
Section 5 for the two edge cases that matter for the demo:

  5.2  No place names found at all → empty extracted[] + message
  5.3  One name fails to resolve while others succeed → "failed" entry

These are building blocks — called by Member 3's Task 10 (cache/storage)
and User's Task 12 (response assembly) to construct their responses.
This module does NOT own the HTTP response itself; it produces the
correctly-shaped dicts that get assembled into the final JSON.

Important: failed entries are never written to resolved_places or
raw_name_aliases — every failure reruns the full pipeline fresh next time
(see backend_build.md Known Gotchas).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# contract.md 5.2 — No place names found in valid text
# ---------------------------------------------------------------------------

def build_no_places_response(original_text: str) -> dict:
    """Short-circuit response when spaCy extraction returns zero location
    entities. This skips cleanup, candidate generation, disambiguation,
    and caching entirely — there's nothing to process.

    Returns the exact shape from contract.md Section 5.2:
        {
            "original_text": "...",
            "extracted": [],
            "message": "No locations found in the provided text."
        }

    HTTP status is 200 — this is not an error, it's a valid outcome.
    """
    return {
        "original_text": original_text,
        "extracted": [],
        "message": "No locations found in the provided text.",
    }


# ---------------------------------------------------------------------------
# contract.md 5.3 — Partial failure (one name fails, others may succeed)
# ---------------------------------------------------------------------------

# Default reason strings — India-scope-aware and informative, as required
# by member4_tasks.md Task 13. These should make the scoping clear to a
# judge who deliberately tests a non-Indian place name, not read like a bug.

REASON_NO_MATCH = (
    "No local match found; Nominatim fallback (India-scoped) "
    "also returned no results."
)

REASON_TIMEOUT = (
    "No local match found; Nominatim fallback (India-scoped) "
    "request timed out."
)


def build_failed_entry(raw_name: str, reason: str | None = None) -> dict:
    """Construct a single "failed" extracted item for a name that could
    not be resolved by either local GeoNames or Nominatim fallback.

    Returns the exact shape from contract.md Section 5.3:
        {
            "raw": "Springfield",
            "canonical": null,
            "lat": null,
            "long": null,
            "confidence": 0.0,
            "reason": "No local match found; Nominatim fallback ...",
            "source": null,
            "status": "failed"
        }

    Args:
        raw_name: The exact text span spaCy extracted (before cleanup).
        reason:   Optional override for the reason string. If not provided,
                  defaults to REASON_NO_MATCH which explains India-only
                  scoping. Use REASON_TIMEOUT if the Nominatim call
                  specifically timed out.
    """
    return {
        "raw": raw_name,
        "canonical": None,
        "lat": None,
        "long": None,
        "confidence": 0.0,
        "reason": reason if reason is not None else REASON_NO_MATCH,
        "source": None,
        "status": "failed",
    }
