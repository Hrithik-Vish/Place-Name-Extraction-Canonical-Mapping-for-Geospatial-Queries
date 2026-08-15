from db import get_supabase

def lookup_local(cleaned_name: str) -> list[dict]:
    """Query geonames_places for candidates."""
    try:
        supabase = get_supabase()
        
        # Search for matches
        result = supabase.table("geonames_places") \
            .select("*") \
            .ilike("name", f"%{cleaned_name}%") \
            .execute()
        
        candidates = []
        for row in result.data:
            candidates.append({
                "name": row.get("name"),
                "lat": row.get("latitude"),
                "long": row.get("longitude"),
                "population": row.get("population", 0),
                "admin1": row.get("admin1"),
                "admin2": row.get("admin2"),
                "source": "local_geonames"
            })
        
        return candidates
        
    except Exception as e:
        print(f"GeoNames lookup error: {e}")
        return []


# Test
if __name__ == "__main__":
    print(lookup_local("Thane"))  # Should return candidates (if data exists)