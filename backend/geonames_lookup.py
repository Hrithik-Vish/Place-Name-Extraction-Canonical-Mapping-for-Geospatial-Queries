from db import get_supabase

def lookup_local(cleaned_name: str) -> list[dict]:
    """Query geonames_places for candidates."""
    try:
        supabase = get_supabase()
        
        # Exact match on ascii_name (case-insensitive) — NOT a substring/contains
        # search. ascii_name is diacritic-normalized, so "Thane" matches both
        # "Thane" and "Thāne" rows without also pulling in "Thanela",
        # "Thanepada", "Thanesar" etc. that a %wildcard% search would.
        result = supabase.table("geonames_places") \
            .select("*") \
            .ilike("ascii_name", cleaned_name) \
            .order("population", desc=True) \
            .execute()
        
        candidates = []
        for row in result.data:
            candidates.append({
                "name": row.get("name"),
                "lat": row.get("latitude"),
                "long": row.get("longitude"),
                "population": row.get("population", 0),
                # schema.sql defines these as admin1_code / admin2_code,
                # not admin1 / admin2 — using the wrong key silently
                # returned None every time, disabling region-hint
                # scoring in disambiguation.py without any error.
                "admin1": row.get("admin1_code"),
                "admin2": row.get("admin2_code"),
                "source": "local_geonames"
            })
        
        return candidates
        
    except Exception as e:
        print(f"GeoNames lookup error: {e}")
        return []


# Test
if __name__ == "__main__":
    print(lookup_local("Thane"))  # Should return candidates (if data exists)