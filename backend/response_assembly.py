"""
response_assembly.py — Task 12 (Owner: Hrithik)

Purpose: pure assembly. Takes per-name results already produced by the
pipeline (fast-path hits, reused-cleaned_name hits, freshly disambiguated
results, or failures) plus their original-text positions, and produces the
exact JSON shape contract.md defines. No resolution logic lives here —
if something needs to be *decided*, it belongs in disambiguation.py or
cache.py, not here.

Critical per changes.md v2: order must come from
resolution_request_items.position_in_text, NOT the order results finished
processing in. A fast-path hit can resolve "instantly" while an earlier
name in the same sentence is still waiting on a live Nominatim call — so
naive append-as-you-go ordering would silently scramble the response.
"""

from __future__ import annotations
from typing import Optional


def build_extracted_item(raw_name: str, result: dict) -> dict:
    """
    Build one item of the `extracted[]` array from a raw name + its
    resolution result (however it was produced — fast path, reused
    cleaned_name, fresh disambiguation, or a failure from errors.py).

    `result` is expected to already be contract-shaped for the fields it
    knows about (canonical/lat/long/confidence/reason/source/status) —
    this function's only job is to attach `raw` and guarantee every
    required key is present, defensively, in case an upstream module
    forgets one.
    """
    return {
        "raw": raw_name,
        "canonical": result.get("canonical"),
        "lat": result.get("lat"),
        "long": result.get("long"),
        "confidence": result.get("confidence", 0.0),
        "reason": result.get("reason", ""),
        "source": result.get("source"),
        "status": result.get("status", "failed"),
    }


def assemble_response(
    original_text: str,
    positioned_results: list[dict],
    message: Optional[str] = None,
) -> dict:
    """
    Final assembly step.

    positioned_results: list of dicts, each shaped like:
        {
            "raw_name": str,
            "position_in_text": int,   # from resolution_request_items
            "result": dict,            # the resolution result for this name
        }
    Does not need to arrive pre-sorted — this function sorts by
    position_in_text itself, since that's the whole point of tracking it
    (processing order != text order, per changes.md v2).

    message: top-level `message` field. None in the normal success case;
    set explicitly by main.py for the short-circuit "no locations found"
    case (contract.md Section 5.2) — this function doesn't infer that on
    its own, since an empty positioned_results list could also just mean
    "nothing to assemble yet" during testing, not necessarily the 5.2 case.
    """
    ordered = sorted(positioned_results, key=lambda r: r["position_in_text"])

    extracted = [
        build_extracted_item(r["raw_name"], r["result"])
        for r in ordered
    ]

    return {
        "original_text": original_text,
        "extracted": extracted,
        "message": message,
    }


def assemble_empty_response(original_text: str, message: str) -> dict:
    """
    Convenience wrapper for contract.md Section 5.2 — zero place names
    found by spaCy. main.py should call this directly from the
    short-circuit branch rather than routing an empty list through
    assemble_response, to keep the "nothing extracted" case explicit and
    intentional rather than incidental.
    """
    return {
        "original_text": original_text,
        "extracted": [],
        "message": message,
    }
