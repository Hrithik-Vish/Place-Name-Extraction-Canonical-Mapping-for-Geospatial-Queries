from rapidfuzz import fuzz, process
from db import get_supabase

def clean_name(raw_name: str) -> str:
    """Clean place name and match against aliases."""
    # Basic cleanup
    cleaned = ''.join(c for c in raw_name if c.isalnum() or c.isspace()).strip()
    
    # Fuzzy match against aliases
    alias = _match_alias(cleaned)
    if alias:
        return alias
    
    return cleaned


def _match_alias(name: str) -> str | None:
    """Fuzzy match against geonames_alternate_names."""
    try:
        supabase = get_supabase()
        
        # Get all alternate names
        result = supabase.table("geonames_alternate_names").select("*").execute()
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
            matched = matches[0][0]
            for a in aliases:
                if a["alternate_name"] == matched:
                    return a["canonical_name"]
        
        return None
    except Exception as e:
        print(f"Alias match error: {e}")
        return None


# Test
if __name__ == "__main__":
    print(clean_name("Bombay"))   # Should print "Mumbai" (if data exists)
    print(clean_name("Thane"))    # Should print "Thane"