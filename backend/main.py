"""
main.py — Task 4 (Owner: Hrithik, taken over from Member 3's original split
since it converges with Task 12/response assembly and Task 14/testing —
all three need the same end-to-end view of the pipeline).

Implements POST /resolve exactly per backend_build.md v2's pipeline
diagram and contract.md's response shape.

Per-name flow (see backend_build.md Section 2):
  1. Fast-path check (raw_name_fast_path) -> hit: use directly, skip
     everything else for this name.
  2. Miss -> cleanup (rapidfuzz) -> cleaned_name.
  3. Second-chance check (resolved_places by cleaned_name) -> hit: reuse,
     write only a new alias row.
  4. Miss -> full pipeline: local GeoNames lookup -> Nominatim fallback
     (if local empty) -> disambiguation -> write BOTH resolved_places and
     raw_name_aliases rows on success; write nothing on failure.

Order is preserved via resolution_request_items.position_in_text, not
processing order, per changes.md v2 — response_assembly.py enforces this.

PATCHED (Hrithik, 16 Aug): _resolve_one_name now returns
resolved_place_id / raw_name_alias_id alongside the contract-shaped result
so db.py's create_request_items can log real, valid rows instead of always
receiving None (see cache.py's rewrite for the corresponding fix on the
write side).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from extraction import extract_places
from cleanup import clean_name, get_alias
from geonames_lookup import lookup_local
from disambiguation import disambiguate, Candidate, ResolvedPlace
from cache import get_cached, get_cached_by_cleaned, store_resolved, store_alias_only
from db import create_request, create_request_items
from response_assembly import assemble_response, assemble_empty_response
from errors import (
    build_failed_entry,
    no_local_and_no_nominatim_reason,
    nominatim_unavailable_reason,
    extraction_empty_message,
)

# ---------------------------------------------------------------------------
# Optional Nominatim import — Task 8 is Member 4's. During parallel dev this
# module may not exist yet, or may still be mid-build. Rather than block
# main.py (and everyone testing against it) on that, we degrade gracefully:
# if the import fails, every name that would have gone to Nominatim just
# fails cleanly with an honest "not available in this build" reason instead
# of crashing /resolve. Swap to the real fallback the moment Task 8 lands —
# no other code here needs to change.
# ---------------------------------------------------------------------------
try:
    from nominatim_fallback import lookup_nominatim
    NOMINATIM_AVAILABLE = True
except ImportError:
    NOMINATIM_AVAILABLE = False

    def lookup_nominatim(cleaned_name: str) -> list[dict]:
        """Stub used only when nominatim_fallback.py isn't present yet."""
        return []


app = FastAPI(title="PS-09 Place-Name Resolver")

# CORS: frontend runs on a different origin (Vite dev server / Vercel).
# Open for MVP/demo scope — tighten to specific origins post-hackathon if
# this ever needs to run somewhere less controlled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResolveRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# Candidate normalization helpers
# ---------------------------------------------------------------------------

def _to_candidates(raw_candidates: list[dict]) -> list[Candidate]:
    """Normalize geonames_lookup.py / nominatim_fallback.py output into
    disambiguation.py's Candidate dataclass. Both sources are expected to
    already share the same dict shape (name/lat/long/population/admin1/
    admin2/source) per backend_build.md Task 8's contract with Task 9."""
    return [
        Candidate(
            name=c["name"],
            lat=c["lat"],
            long=c["long"],
            population=c.get("population", 0),
            admin1=c.get("admin1"),
            admin2=c.get("admin2"),
            source=c.get("source", "local_geonames"),
        )
        for c in raw_candidates
    ]


def _resolution_result_to_dict(result) -> dict:
    """Convert disambiguation.py's ResolutionResult dataclass into the
    plain dict shape response_assembly.py / cache.py expect."""
    return {
        "canonical": result.canonical,
        "lat": result.lat,
        "long": result.long,
        "confidence": result.confidence,
        "reason": result.reason,
        "source": result.source,
        "status": result.status,
    }


# ---------------------------------------------------------------------------
# Per-name pipeline
# ---------------------------------------------------------------------------

def _resolve_one_name(
    raw_name: str,
    original_text: str,
    resolved_so_far: list[ResolvedPlace],
) -> dict:
    """
    Runs the full per-name flow for a single raw_name and returns a
    contract-shaped result dict, PLUS two internal-only keys
    (resolved_place_id, raw_name_alias_id) that response_assembly.py's
    build_extracted_item() ignores (it only reads the contract fields) but
    main.py uses for resolution_request_items logging. Also appends to
    resolved_so_far when the name resolves, so later names in the same
    request get proximity signal from it.
    """

    # --- Stage 1: fast-path check ---------------------------------------
    fast_hit = get_cached(raw_name)
    if fast_hit is not None:
        result = {
            "canonical": fast_hit["canonical"],
            "lat": fast_hit["lat"],
            "long": fast_hit["long"],
            "confidence": fast_hit["confidence"],
            "reason": fast_hit["reason"],
            "source": fast_hit["source"],
            "status": "resolved" if fast_hit["canonical"] else "failed",
            "resolved_place_id": fast_hit.get("resolved_place_id"),
            # Fast-path hit reuses the EXISTING alias row (this raw_name
            # was already cached) — nothing new was written, but we still
            # want create_request_items to log against the existing alias
            # if we can identify it. get_cached() doesn't currently return
            # the alias row's own id (only resolved_place_id), so this is
            # intentionally left unset here; the position is still
            # correctly reflected in the response itself via
            # response_assembly's ordering, which does not depend on this
            # table (see db.py's create_request_items docstring).
            "raw_name_alias_id": None,
        }
        if result["status"] == "resolved":
            resolved_so_far.append(
                ResolvedPlace(name=result["canonical"], lat=result["lat"], long=result["long"])
            )
        return result

    # --- Stage 2: cleanup (rapidfuzz + alias match) ----------------------
    cleaned_name = clean_name(raw_name)

    # --- Stage 3: second-chance check by cleaned_name --------------------
    reuse_hit = get_cached_by_cleaned(cleaned_name)
    if reuse_hit is not None:
        result = {
            "canonical": reuse_hit["canonical"],
            "lat": reuse_hit["lat"],
            "long": reuse_hit["long"],
            "confidence": reuse_hit["confidence"],
            "reason": reuse_hit["reason"],
            "source": reuse_hit["source"],
            "status": "resolved" if reuse_hit["canonical"] else "failed",
            "resolved_place_id": reuse_hit.get("resolved_place_id"),
            "raw_name_alias_id": None,
        }
        if result["status"] == "resolved":
            write = store_alias_only(raw_name, cleaned_name, reuse_hit["resolved_place_id"])
            if write:
                result["raw_name_alias_id"] = write.get("raw_name_alias_id")
            resolved_so_far.append(
                ResolvedPlace(name=result["canonical"], lat=result["lat"], long=result["long"])
            )
        return result

    # --- Stage 4: full pipeline — local lookup, then alias fallback, then Nominatim
    local_candidates = lookup_local(cleaned_name)

    if not local_candidates:
        # Direct name had no match — try the alias table as a fallback,
        # not as the default path (see cleanup.py's get_alias docstring).
        alias_name = get_alias(cleaned_name)
        if alias_name and alias_name != cleaned_name:
            local_candidates = lookup_local(alias_name)

    if local_candidates:
        candidates = _to_candidates(local_candidates)
    elif NOMINATIM_AVAILABLE:
        nominatim_candidates = lookup_nominatim(cleaned_name)
        candidates = _to_candidates(nominatim_candidates)
    else:
        # Nominatim module not wired up yet — degrade to a clean failure
        # rather than crashing the request. See import block at top.
        failed = build_failed_entry(raw_name, nominatim_unavailable_reason())
        failed["resolved_place_id"] = None
        failed["raw_name_alias_id"] = None
        return failed

    disamb_result = disambiguate(
        cleaned_name=cleaned_name,
        candidates=candidates,
        resolved_so_far=resolved_so_far,
        original_text=original_text,
    )
    result = _resolution_result_to_dict(disamb_result)
    result["resolved_place_id"] = None
    result["raw_name_alias_id"] = None

    if result["status"] == "resolved":
        write = store_resolved(raw_name, cleaned_name, result)
        if write:
            result["resolved_place_id"] = write.get("resolved_place_id")
            result["raw_name_alias_id"] = write.get("raw_name_alias_id")
        resolved_so_far.append(
            ResolvedPlace(name=result["canonical"], lat=result["lat"], long=result["long"])
        )
    # Failed results are never written to cache (schema.sql Section 3 /
    # changes.md — deliberate MVP scope, always retries fresh next time).

    return result


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/resolve")
def resolve(payload: ResolveRequest):
    text = payload.text

    # Defensive only — frontend guarantees non-empty per contract.md 5.1.
    # Not a case we design around, just don't crash on it.
    if not text or not text.strip():
        return assemble_empty_response(text or "", extraction_empty_message())

    # --- spaCy extraction -------------------------------------------------
    raw_names = extract_places(text)

    # --- Short-circuit: zero place names found (contract.md 5.2) ----------
    if not raw_names:
        return assemble_empty_response(text, extraction_empty_message())

    # --- Create resolution_requests row for position tracking -------------
    request_id = create_request(text)

    resolved_so_far: list[ResolvedPlace] = []
    positioned_results = []
    items_for_logging = []

    for position, raw_name in enumerate(raw_names):
        result = _resolve_one_name(raw_name, text, resolved_so_far)

        positioned_results.append({
            "raw_name": raw_name,
            "position_in_text": position,
            "result": result,
        })

        items_for_logging.append({
            "raw_name": raw_name,
            "position": position,
            "resolved_place_id": result.get("resolved_place_id"),
            "raw_name_alias_id": result.get("raw_name_alias_id"),
        })

    # --- Log resolution_request_items (best-effort; doesn't block response) -
    if request_id:
        create_request_items(request_id, items_for_logging)

    return assemble_response(text, positioned_results, message=None)


@app.get("/health")
def health():
    """Not part of contract.md — convenience endpoint for confirming the
    server is up during setup/demo rehearsal."""
    return {"status": "ok", "nominatim_available": NOMINATIM_AVAILABLE}