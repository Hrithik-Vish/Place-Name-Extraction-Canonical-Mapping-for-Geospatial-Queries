"""
Task 7 — Local GeoNames Candidate Lookup (Owner: Member 3 / User)
Query geonames_places for matches against the cleaned name.
Can return multiple candidates — disambiguation sorts them out.
"""

from db import get_supabase


def lookup_local(cleaned_name: str) -> list[dict]:
    """
    Query geonames_places for candidates.
    ✅ FIXED: Uses admin1_code/admin2_code to match schema.sql.
    Returns list of candidate dicts.
    """
    try:
        supabase = get_supabase()

        # Search for matches (case-insensitive)
        result = supabase.table("geonames_places") \
            .select("*") \
            .ilike("name", f"%{cleaned_name}%") \
            .execute()

        candidates = []
        for row in result.data:
            candidates.append({
                "name": row.get("name"),
                "lat": row.get("latitude"),          # ✅ Matches schema
                "long": row.get("longitude"),        # ✅ Matches schema
                "population": row.get("population", 0),
                "admin1": row.get("admin1_code"),    # ✅ Matches schema
                "admin2": row.get("admin2_code"),    # ✅ Matches schema
                "source": "local_geonames"
            })

        return candidates

    except Exception as e:
        print(f"GeoNames lookup error: {e}")
        return []


# Test
if __name__ == "__main__":
    print(lookup_local("Thane"))
    print(lookup_local("XYZ"))