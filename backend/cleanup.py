"""
Task 6 — rapidfuzz Cleanup (Owner: Member 3 / User)
Take each raw name from Task 5 and normalize it — strip stray
punctuation/whitespace, and fuzzy-match against known aliases
(e.g. historical names like "Bombay" → "Mumbai").
"""

from rapidfuzz import fuzz, process
from db import get_supabase


def clean_name(raw_name: str) -> str:
    """Clean place name and match against aliases."""
    stripped = ''.join(c for c in raw_name if c.isalnum() or c.isspace()).strip()
    
    alias = _match_alias(stripped)
    if alias:
        return alias.title()
    
    return stripped.title()


def _match_alias(name: str) -> str | None:
    """
    Fuzzy match against geonames_alternate_names.
    Joins via geoname_id to geonames_places for canonical name.
    ✅ FIXED: Uses geoname_id to join to geonames_places for canonical name.
    """
    try:
        supabase = get_supabase()

        # ✅ Query geonames_alternate_names with geoname_id
        result = supabase.table("geonames_alternate_names") \
            .select("alternate_name, geoname_id") \
            .ilike("alternate_name", f"%{name}%") \
            .limit(20) \
            .execute()

        aliases = result.data

        if not aliases:
            return None

        # Fuzzy match
        matches = process.extract(
            name,
            [a["alternate_name"] for a in aliases],
            scorer=fuzz.ratio,
            limit=1
        )

        if matches and matches[0][1] >= 85:
            matched_name = matches[0][0]

            # Find the geoname_id for this match
            geoname_id = None
            for a in aliases:
                if a["alternate_name"] == matched_name:
                    geoname_id = a["geoname_id"]
                    break

            if geoname_id:
                # ✅ Get canonical name from geonames_places
                place = supabase.table("geonames_places") \
                    .select("name") \
                    .eq("geoname_id", geoname_id) \
                    .single() \
                    .execute()

                if place.data:
                    return place.data["name"]

        return None
    except Exception as e:
        print(f"Alias match error: {e}")
        return None


# Test
if __name__ == "__main__":
    print(clean_name("Bombay"))   # Should print "Mumbai" (if data exists)
    print(clean_name("Thane"))    # Should print "Thane"