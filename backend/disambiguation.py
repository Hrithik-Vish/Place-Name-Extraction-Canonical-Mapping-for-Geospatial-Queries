"""
Task 9 — Disambiguation Logic (Owner: Hrithik)

Runs only on a genuine double cache-miss: raw_name_fast_path missed AND
cleaned_name missed in resolved_places (see changes.md v2). Everything that
hits either cache level bypasses this module entirely — so when this DOES
run, it's producing the answer an analyst will actually read and audit.

Target user (locked): analysts/operators at a situational-awareness desk
(news/OSINT, gov disaster-management ops cells) pasting incident reports —
NOT citizens, NOT a generic public-safety app. This shapes the weighting:

- Incident reports naturally cluster place names ("flooding in Thane,
  spreading to Kalyan, evacuation near Bhiwandi") -> proximity to
  co-resolved names in the SAME request is strong, common evidence here,
  not a rare fallback signal.
- Wire/situation-report copy tends to state explicit geographic context
  ("...in Raigad district", "...Maharashtra officials said...") -> region
  hints are more reliable for this input shape than for generic text.
- Population is a PRIOR (what's statistically likely with zero evidence),
  not evidence about THIS specific mention. A genuinely low-population
  place (e.g. the actual flooded village) must be able to beat a
  high-population same-named place when proximity/region evidence
  supports it. Population only fully drives the decision when nothing
  else is available, and that case is explicitly flagged with capped
  confidence rather than presented as a confident answer.

Current scope note: the system processes one contiguous request text as a
single unit (chunking-before-spaCy is future-scope, not built). So
"resolved_so_far" is a complete picture of co-mentioned places for this
request, not a partial window. If chunking is added later, proximity
scoring's context shrinks per chunk — reason strings must stay accurate to
what the algorithm actually saw, not what a reader might assume.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """One candidate place for a cleaned_name, from GeoNames (Task 7) or
    Nominatim (Task 8, India-scoped per v2). Both sources are normalized
    into this same shape before reaching this module."""
    name: str                      # canonical/display name
    lat: float
    long: float
    population: int                # 0 if unknown (e.g. raw Nominatim hits)
    admin1: Optional[str] = None   # state name/text, if available
    admin2: Optional[str] = None   # district name/text, if available
    source: str = "local_geonames"  # "local_geonames" | "nominatim_fallback"


@dataclass
class ResolvedPlace:
    """An already-resolved place earlier in THIS request, used for
    proximity scoring. Comes from resolution_request_items processed so
    far in the current call, not from cache."""
    name: str
    lat: float
    long: float


@dataclass
class ResolutionResult:
    status: str                    # "resolved" | "failed"
    canonical: Optional[str]
    lat: Optional[float]
    long: Optional[float]
    confidence: float              # 0.0 - 1.0
    source: Optional[str]
    reason: str


# ---------------------------------------------------------------------------
# Distance helper (haversine — mirrors what Task 9 would otherwise ask
# PostGIS's ST_Distance for; kept local so this module is testable without
# a live DB connection per backend_build.md Section 4's parallel-dev note)
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Individual signal scorers — each returns 0.0-1.0
# ---------------------------------------------------------------------------

def _population_score(candidate: Candidate, all_candidates: list[Candidate]) -> float:
    """Log-scaled, normalized against the max in this candidate set.
    Log scale deliberately softens large gaps: a village of 5,000 vs a
    city of 500,000 is a ~2x gap in log-space, not 100x."""
    pops = [math.log(c.population + 1) for c in all_candidates]
    max_pop = max(pops) if pops else 0.0
    if max_pop == 0:
        return 0.0
    return math.log(candidate.population + 1) / max_pop


def _proximity_score(candidate: Candidate, resolved_so_far: list[ResolvedPlace]) -> tuple[float, Optional[str], float]:
    """Returns (score, nearest_place_name, distance_km). Score 0 if no
    other resolved places yet in this request (common on the FIRST place
    name of a report — not an error, just no evidence available yet)."""
    if not resolved_so_far:
        return 0.0, None, 0.0
    nearest = min(
        resolved_so_far,
        key=lambda r: _haversine_km(candidate.lat, candidate.long, r.lat, r.long),
    )
    dist = _haversine_km(candidate.lat, candidate.long, nearest.lat, nearest.long)
    # Inverse distance, capped at 100km — closer than that fully scores,
    # beyond it decays to 0. Tuned for intra-district/state incident
    # clustering typical of news/OSINT reports, not cross-country spans.
    score = max(0.0, 1 - min(dist / 100.0, 1.0))
    return score, nearest.name, dist


def _region_hint_score(candidate: Candidate, original_text: str) -> tuple[float, Optional[str]]:
    """Binary-ish match: does the candidate's admin1/admin2 text appear
    in the original text? Wire/situation reports state this explicitly
    far more often than casual text, so this signal is comparatively
    strong and reliable for the analyst-facing use case."""
    text_lower = original_text.lower()
    if candidate.admin2 and candidate.admin2.lower() in text_lower:
        return 1.0, candidate.admin2
    if candidate.admin1 and candidate.admin1.lower() in text_lower:
        return 0.7, candidate.admin1
    return 0.0, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def disambiguate(
    cleaned_name: str,
    candidates: list[Candidate],
    resolved_so_far: list[ResolvedPlace],
    original_text: str,
) -> ResolutionResult:

    # No candidates at all -> failed entry per contract.md 5.3
    if not candidates:
        return ResolutionResult(
            status="failed",
            canonical=None, lat=None, long=None,
            confidence=0.0, source=None,
            reason=(
                "No local gazetteer match; India-scoped Nominatim fallback "
                "also returned no results."
            ),
        )

    # Only one candidate -> nothing to disambiguate
    if len(candidates) == 1:
        c = candidates[0]
        return ResolutionResult(
            status="resolved",
            canonical=c.name, lat=c.lat, long=c.long,
            confidence=0.9, source=c.source,
            reason="Only match found in local gazetteer; no disambiguation needed.",
        )

    # Score every candidate on all three signals
    scored = []
    for c in candidates:
        pop_s = _population_score(c, candidates)
        prox_s, nearest_name, dist_km = _proximity_score(c, resolved_so_far)
        region_s, region_name = _region_hint_score(c, original_text)
        scored.append({
            "candidate": c,
            "pop": pop_s,
            "prox": prox_s,
            "prox_place": nearest_name,
            "prox_dist": dist_km,
            "region": region_s,
            "region_name": region_name,
        })

    # Weighting: evidence (proximity/region) outranks the population prior
    # by default for this analyst/incident-report use case. Population only
    # fully drives the pick when there's truly no other evidence — and
    # critically, a population-only guess must NOT be able to outscore a
    # candidate backed by real evidence just because it happens to be the
    # biggest place in this particular candidate set. Raw population score
    # is capped at POP_ONLY_CEILING when it's the sole signal, so an
    # evidence-backed low-population candidate (e.g. the actual flooded
    # village near an already-resolved neighbor) can still win.
    POP_ONLY_CEILING = 0.5  # must stay below the lowest realistic
                             # region/proximity composite for a genuine
                             # evidence-backed candidate, so evidence
                             # always beats a population-only guess.
    for s in scored:
        if s["region"] > 0:
            s["composite"] = 0.7 * s["region"] + 0.2 * s["prox"] + 0.1 * s["pop"]
            s["driven_by"] = "region"
        elif s["prox"] > 0:
            s["composite"] = 0.6 * s["prox"] + 0.3 * s["pop"] + 0.1 * s["region"]
            s["driven_by"] = "proximity"
        else:
            s["composite"] = min(s["pop"], POP_ONLY_CEILING)
            s["driven_by"] = "population_only"

    scored.sort(key=lambda s: s["composite"], reverse=True)
    best = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None

    confidence = best["composite"]

    # Ambiguity penalty: top two candidates close together = genuine
    # uncertainty, don't overstate confidence
    if runner_up and (best["composite"] - runner_up["composite"]) < 0.05:
        confidence = max(0.0, confidence - 0.1)

    # Population-only picks are guesses in the absence of textual
    # evidence — cap confidence and say so plainly. This matters most for
    # this audience: an analyst needs to know when to double-check by hand
    # rather than trust the pin.
    if best["driven_by"] == "population_only":
        confidence = min(confidence, 0.6)

    reason = _build_reason(best, runner_up, len(candidates))

    c = best["candidate"]
    return ResolutionResult(
        status="resolved",
        canonical=c.name, lat=c.lat, long=c.long,
        confidence=round(confidence, 3), source=c.source,
        reason=reason,
    )


def _build_reason(best: dict, runner_up: Optional[dict], n_candidates: int) -> str:
    """Analyst-facing reason strings — specific, auditable, and honest
    about which signal drove the pick. This is the field the demo
    click-to-reveal interaction uses, and for this audience it needs to
    read like something an ops analyst would trust and verify, not a
    casual explanation."""
    c = best["candidate"]

    if best["driven_by"] == "region":
        return (
            f"Selected over {n_candidates - 1} other candidate(s) based on "
            f"regional context ('{best['region_name']}') mentioned in the text."
        )

    if best["driven_by"] == "proximity":
        dist = round(best["prox_dist"], 1)
        base = (
            f"Selected over {n_candidates - 1} other candidate(s) based on "
            f"proximity to co-mentioned '{best['prox_place']}' "
            f"({dist} km away)"
        )
        if best["pop"] >= 0.5:
            return base + "; population also supports this match."
        return base + "."

    # population_only
    return (
        "Selected based on population only; no other place names or "
        "regional context were available in this text to confirm this "
        "specific location — treat with lower confidence and verify if "
        "precision matters."
    )
