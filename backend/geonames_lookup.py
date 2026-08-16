from db import get_supabase

def lookup_local(cleaned_name: str) -> list[dict]:
    """Query geonames_places for candidates matching the cleaned name.

    Uses an exact, case-insensitive match (not a substring search) — a
    substring match on "Thane" would also pull in "Thanesar", "Thanjavur"-
    adjacent entries, etc., handing disambiguation.py (Task 9) noisy
    candidates its scoring wasn't designed to filter (it disambiguates
    between genuine same-named places, not near-spellings — that's
    cleanup.py/rapidfuzz's job, upstream of this call).

    Column names per schema.sql: admin1_code / admin2_code, not
    admin1 / admin2.
    """
    try:
        supabase = get_supabase()

        result = supabase.table("geonames_places") \
            .select("*") \
            .ilike("name", cleaned_name) \
            .execute()

        candidates = []
        for row in result.data:
            candidates.append({
                "name": row.get("name"),
                "lat": row.get("latitude"),
                "long": row.get("longitude"),
                "population": row.get("population", 0) or 0,
                "admin1": row.get("admin1_code"),
                "admin2": row.get("admin2_code"),
                "source": "local_geonames",
            })

        return candidates

    except Exception as e:
        print(f"GeoNames lookup error: {e}")
        return []


# Test
if __name__ == "__main__":
    print(lookup_local("Thane"))  # Should return candidates (if data exists)