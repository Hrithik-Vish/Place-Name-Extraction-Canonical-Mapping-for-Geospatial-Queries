"""
errors.py — Shared failure-entry builder (Task 13 scope, written by Hrithik
as a shared helper so Task 8/Task 9 call sites can't drift from contract.md).

Purpose: every place in the pipeline that can produce a failed resolution
(Nominatim fallback coming back empty/timing out, disambiguation finding
zero candidates at all) should build its "failed" entry through this
module, not by hand-rolling a dict. That's what guarantees the shape never
drifts from contract.md Section 5.3, regardless of which module produced
the failure.

Per contract.md:
    "status": "failed" entries always have canonical/lat/long/source == null,
    confidence == 0.0, and a `reason` string that is always present and
    honest about what was tried.

Per member4_tasks.md Task 13 + member4_tasks.md Known Gotchas:
    Nominatim is India-scoped (`countrycodes=in`). A non-Indian name (e.g.
    "Springfield") is EXPECTED to fail — the reason string should say so
    explicitly, so it reads as a deliberate product boundary if a judge
    tests it, not a bug.
"""

from __future__ import annotations
from typing import Optional


def build_failed_entry(raw_name: str, reason: str) -> dict:
    """
    Construct a single contract-shaped failed entry for one raw name.

    Use this from:
      - nominatim_fallback.py, when Nominatim also returns nothing / times out
      - disambiguation.py, when candidates list is empty (Task 7 + Task 8
        both came back empty)

    Does NOT include `raw` — response_assembly.py attaches `raw` (and
    resolves position ordering) when it builds the final extracted[] item,
    so this stays reusable regardless of where in the pipeline it's called.
    """
    return {
        "canonical": None,
        "lat": None,
        "long": None,
        "confidence": 0.0,
        "reason": reason,
        "source": None,
        "status": "failed",
    }


def no_local_and_no_nominatim_reason() -> str:
    """
    Standard reason string for the common case: no GeoNames match, and the
    India-scoped Nominatim fallback also found nothing. Centralized so the
    "India-scoped" language stays consistent across call sites — this is
    the exact case a judge testing "Springfield" will trigger, and the
    wording needs to read as a stated boundary, not an error.
    """
    return (
        "No local gazetteer match found; India-scoped Nominatim fallback "
        "also returned no results."
    )


def nominatim_timeout_reason() -> str:
    """Reason string for when Nominatim was reached but didn't respond in
    time. Distinguished from a clean 'no results' response since it's a
    different failure mode (network/latency, not 'this isn't a known
    Indian place')."""
    return (
        "No local gazetteer match found; India-scoped Nominatim fallback "
        "request timed out."
    )


def nominatim_unavailable_reason() -> str:
    """Reason string for when nominatim_fallback.py itself isn't wired up
    yet (import failure) — lets main.py degrade gracefully during parallel
    development instead of crashing the whole /resolve call. Should not
    appear in the final demo build once Task 8 is complete."""
    return (
        "No local gazetteer match found; Nominatim fallback is not yet "
        "available in this build."
    )


def extraction_empty_message() -> str:
    """Top-level `message` field for contract.md Section 5.2 — zero place
    names found by spaCy. This is NOT a per-entry reason, it's the
    top-level response `message`."""
    return "No locations found in the provided text."
