from db import get_supabase
from datetime import datetime


def get_cached(raw_name: str) -> dict | None:
    """Fast-path cache check"""
    try:
        supabase = get_supabase()
        
        result = supabase.table("raw_name_fast_path") \
            .select("*") \
            .eq("raw_name", raw_name) \
            .execute()
        
        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                "cleaned_name": row.get("cleaned_name"),
                "canonical": row.get("canonical_name"),
                "lat": row.get("latitude"),      # ✅ Matches schema
                "long": row.get("longitude"),    # ✅ Matches schema
                "confidence": row.get("confidence", 0.0),
                "reason": row.get("reason", "Cache hit"),
                "source": row.get("source", "cached"),
                "resolved_place_id": row.get("resolved_place_id")
            }
        return None
    except Exception as e:
        print(f"Cache error: {e}")
        return None


def get_cached_by_cleaned(cleaned_name: str) -> dict | None:
    """Second-chance cache check"""
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
                "lat": row.get("latitude"),      # ✅ Matches schema
                "long": row.get("longitude"),    # ✅ Matches schema
                "confidence": row.get("confidence", 0.0),
                "reason": "Reused from existing",
                "source": row.get("source", "cached"),
                "resolved_place_id": row.get("id")
            }
        return None
    except Exception as e:
        print(f"Cleaned cache error: {e}")
        return None


def store_resolved(raw_name: str, cleaned_name: str, resolved: dict) -> bool:
    """Store new resolution in cache"""
    try:
        supabase = get_supabase()
        
        # Insert into resolved_places - ✅ Matches schema
        resolved_data = {
            "cleaned_name": cleaned_name,
            "canonical_name": resolved.get("canonical"),
            "latitude": resolved.get("lat"),      # ✅ Matches schema
            "longitude": resolved.get("long"),    # ✅ Matches schema
            "confidence": resolved.get("confidence", 0.0),
            "reason": resolved.get("reason", "Fresh resolution"),
            "source": resolved.get("source", "geonames"),
            "candidate_count": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("resolved_places").insert(resolved_data).execute()
        
        if not result.data or len(result.data) == 0:
            return False
        
        resolved_id = result.data[0]["id"]
        
        # Insert into raw_name_aliases - ✅ Matches schema (no cleaned_name)
        alias_data = {
            "raw_name": raw_name,
            "resolved_place_id": resolved_id,
            "hit_count": 1,
            "first_seen_at": datetime.utcnow().isoformat(),
            "last_seen_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("raw_name_aliases").insert(alias_data).execute()
        
        return True
    except Exception as e:
        print(f"Store cache error: {e}")
        return False


def store_alias_only(raw_name: str, cleaned_name: str, resolved_place_id: str) -> bool:
    """Store only alias (when cleaned_name already exists)"""
    try:
        supabase = get_supabase()
        
        # ✅ Matches schema (no cleaned_name)
        alias_data = {
            "raw_name": raw_name,
            "resolved_place_id": resolved_place_id,
            "hit_count": 1,
            "first_seen_at": datetime.utcnow().isoformat(),
            "last_seen_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("raw_name_aliases").insert(alias_data).execute()
        return bool(result.data and len(result.data) > 0)
    except Exception as e:
        print(f"Store alias error: {e}")
        return False