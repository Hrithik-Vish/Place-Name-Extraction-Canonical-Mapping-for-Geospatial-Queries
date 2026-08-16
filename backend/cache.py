"""
Task 10 — Cache Check + Storage Write (Owner: Member 3, patched by Hrithik)

Single source of truth for all reads/writes against `resolved_places` and
`raw_name_aliases`. db.py no longer independently creates or updates alias
rows (it previously did, via a second, inconsistent implementation using
wrong column names and a non-existent supabase.raw() call) — every alias
write happens here, once, so there is exactly one code path per changes.md
v2's two-level cache design.

Column names below are taken directly from schema.sql — this was the
dominant bug class in earlier drafts (lat/long instead of latitude/
longitude, a cleaned_name column on raw_name_aliases that doesn't exist,
a last_used_at column on resolved_places that doesn't exist). Every
query/insert here has been checked against schema.sql field-by-field.
"""

from db import get_supabase
from datetime import datetime, timezone


def get_cached(raw_name: str) -> dict | None:
    """Fast-path cache check — queries the raw_name_fast_path view.

    View columns (per schema.sql Section 6): raw_name, hit_count,
    resolved_place_id, cleaned_name, canonical_name, latitude, longitude,
    confidence, reason, source. No `lat`/`long` — those are geonames_places'
    naming, not this view's.
    """
    try:
        supabase = get_supabase()

        result = supabase.table("raw_name_fast_path") \
            .select("*") \
            .eq("raw_name", raw_name) \
            .execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            _bump_alias_hit(raw_name)
            return {
                "cleaned_name": row.get("cleaned_name"),
                "canonical": row.get("canonical_name"),
                "lat": row.get("latitude"),
                "long": row.get("longitude"),
                "confidence": row.get("confidence", 0.0),
                "reason": row.get("reason", ""),
                "source": row.get("source"),
                "resolved_place_id": row.get("resolved_place_id"),
            }
        return None
    except Exception as e:
        print(f"Cache error (fast path): {e}")
        return None


def get_cached_by_cleaned(cleaned_name: str) -> dict | None:
    """Second-chance cache check — does this cleaned_name already exist in
    resolved_places? Queries resolved_places directly (not the fast-path
    view), since there is no raw_name_aliases row for this raw_name yet —
    that's exactly why we're in this branch."""
    try:
        supabase = get_supabase()

        result = supabase.table("resolved_places") \
            .select("*") \
            .eq("cleaned_name", cleaned_name) \
            .execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "canonical": row.get("canonical_name"),
                "lat": row.get("latitude"),
                "long": row.get("longitude"),
                "confidence": float(row.get("confidence", 0.0)),
                "reason": row.get("reason", ""),
                "source": row.get("source"),
                "resolved_place_id": row.get("id"),
            }
        return None
    except Exception as e:
        print(f"Cache error (cleaned_name reuse): {e}")
        return None


def store_resolved(raw_name: str, cleaned_name: str, resolved: dict) -> dict | None:
    """Fresh resolution — write a NEW resolved_places row, then a NEW
    raw_name_aliases row pointing to it, in that order (alias FK requires
    the resolved_places row to exist first). Only called on success —
    failed results are never written here (see errors.py / changes.md).

    Returns {"resolved_place_id": ..., "raw_name_alias_id": ...} on
    success, or None on failure, so main.py/db.py can log the write
    without re-querying.
    """
    try:
        supabase = get_supabase()

        resolved_data = {
            "cleaned_name": cleaned_name,
            "canonical_name": resolved.get("canonical"),
            "latitude": resolved.get("lat"),
            "longitude": resolved.get("long"),
            "confidence": resolved.get("confidence", 0.0),
            "reason": resolved.get("reason", ""),
            "source": resolved.get("source", "local_geonames"),
        }

        result = supabase.table("resolved_places").insert(resolved_data).execute()

        if not result.data or len(result.data) == 0:
            print(f"Store cache error: insert into resolved_places returned no data for '{cleaned_name}'")
            return None

        resolved_place_id = result.data[0]["id"]

        alias_id = _insert_alias(raw_name, resolved_place_id)
        if alias_id is None:
            # resolved_places row exists but alias write failed — not
            # fatal (ON DELETE CASCADE means an orphan resolved_places row
            # is harmless, just wasteful), but the fast path won't work for
            # this raw_name next time. Log and move on rather than fail
            # the whole /resolve call over a logging-adjacent write.
            print(f"Warning: resolved_places row {resolved_place_id} created but alias write failed for '{raw_name}'")

        return {
            "resolved_place_id": resolved_place_id,
            "raw_name_alias_id": alias_id,
        }
    except Exception as e:
        print(f"Store cache error: {e}")
        return None


def store_alias_only(raw_name: str, cleaned_name: str, resolved_place_id) -> dict | None:
    """cleaned_name reuse case — resolved_places row already exists, only
    write a new raw_name_aliases row pointing to it. `cleaned_name` param
    is accepted for call-site symmetry with store_resolved but is not
    written anywhere (raw_name_aliases has no cleaned_name column)."""
    alias_id = _insert_alias(raw_name, resolved_place_id)
    if alias_id is None:
        return None
    return {
        "resolved_place_id": resolved_place_id,
        "raw_name_alias_id": alias_id,
    }


# ---------------------------------------------------------------------------
# Internal helpers — the only two functions that touch raw_name_aliases
# ---------------------------------------------------------------------------

def _insert_alias(raw_name: str, resolved_place_id) -> str | None:
    """Insert a new raw_name_aliases row. Per schema.sql there's a UNIQUE
    index on raw_name, so this assumes get_cached() already confirmed no
    row exists for this exact raw_name (true on every call site — this is
    only reached after a fast-path miss). If a duplicate slips through
    (e.g. a race), the unique constraint will reject it and we fall back
    to fetching the existing row instead of crashing."""
    try:
        supabase = get_supabase()
        now = datetime.now(timezone.utc).isoformat()

        alias_data = {
            "raw_name": raw_name,
            "resolved_place_id": resolved_place_id,
            "hit_count": 1,
            "first_seen_at": now,
            "last_seen_at": now,
        }

        result = supabase.table("raw_name_aliases").insert(alias_data).execute()

        if result.data and len(result.data) > 0:
            return str(result.data[0]["id"])

        return None
    except Exception as e:
        # Likely a unique-constraint hit on raw_name (race condition) —
        # fetch the existing row rather than treating this as a failure.
        print(f"Alias insert error for '{raw_name}' (may already exist): {e}")
        try:
            supabase = get_supabase()
            existing = supabase.table("raw_name_aliases") \
                .select("id") \
                .eq("raw_name", raw_name) \
                .execute()
            if existing.data and len(existing.data) > 0:
                return str(existing.data[0]["id"])
        except Exception as e2:
            print(f"Alias fallback lookup also failed for '{raw_name}': {e2}")
        return None


def _bump_alias_hit(raw_name: str) -> None:
    """Increment hit_count and refresh last_seen_at on a fast-path hit.
    Best-effort only — read-then-write, not atomic, but hit_count is a
    display/debug stat, not something correctness depends on, so a rare
    lost increment under concurrent load is an acceptable MVP trade-off
    (schema.sql itself marks this column 'optional')."""
    try:
        supabase = get_supabase()
        existing = supabase.table("raw_name_aliases") \
            .select("id, hit_count") \
            .eq("raw_name", raw_name) \
            .execute()

        if existing.data and len(existing.data) > 0:
            row = existing.data[0]
            supabase.table("raw_name_aliases") \
                .update({
                    "hit_count": (row.get("hit_count") or 0) + 1,
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                }) \
                .eq("id", row["id"]) \
                .execute()
    except Exception as e:
        # Never let a hit-count bump failure affect the actual resolution.
        print(f"Non-fatal: could not bump hit_count for '{raw_name}': {e}")