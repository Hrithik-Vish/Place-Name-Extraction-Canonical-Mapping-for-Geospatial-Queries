"""
Database connection and request tracking for PS-09.
Provides Supabase client and helper functions for:
- Connection management
- Request tracking (resolution_requests)
- Request items (resolution_request_items)
- Alias management (raw_name_aliases)
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Get credentials from .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

# Check if credentials exist
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_URL or SUPABASE_SECRET_KEY missing in .env file!")

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ====== CONNECTION FUNCTIONS ======

def get_supabase() -> Client:
    """Return Supabase client for other modules"""
    return supabase


def test_connection() -> bool:
    """Test if Supabase connection works"""
    try:
        result = supabase.table("geonames_places").select("*").limit(1).execute()
        print("✅ Supabase connection successful!")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False


# ====== REQUEST TRACKING FUNCTIONS ======

def create_request(text: str) -> str:
    """
    Create a new resolution_requests row.
    Let Supabase auto-generate the ID (bigint/serial).
    Returns the request_id as string.
    """
    try:
        data = {
            "original_text": text,
            "created_at": datetime.utcnow().isoformat()
        }
        result = supabase.table("resolution_requests").insert(data).execute()

        if result.data and len(result.data) > 0:
            return str(result.data[0]["id"])
        return None
    except Exception as e:
        print(f"Error creating request: {e}")
        return None


def create_request_items(request_id: str, results: list[dict]) -> None:
    """
    Insert each result into resolution_request_items.
    Uses raw_name_alias_id foreign key to raw_name_aliases.
    """
    try:
        items = []
        for r in results:
            # Get or create alias
            alias_id = _get_or_create_alias(
                raw_name=r.get("raw_name"),
                resolved_place_id=r.get("resolved_place_id")
            )

            if alias_id:
                items.append({
                    "request_id": request_id,
                    "raw_name_alias_id": alias_id,  # ✅ Matches schema
                    "position_in_text": r.get("position", 0),
                })

        if items:
            supabase.table("resolution_request_items").insert(items).execute()
            print(f"✅ Created {len(items)} request items")
    except Exception as e:
        print(f"Error creating request items: {e}")


# ====== ALIAS MANAGEMENT FUNCTIONS ======

def _get_or_create_alias(raw_name: str, resolved_place_id: str) -> str | None:
    """
    Get existing alias or create a new one.
    ✅ FIXED: supabase.raw() replaced with Python increment.
    ✅ FIXED: removed cleaned_name from alias insert.
    """
    try:
        # Only create alias if resolved_place_id exists
        if not resolved_place_id:
            print(f"⚠️ Skipping alias for '{raw_name}' (no resolved_place_id)")
            return None

        # Check if alias exists
        result = supabase.table("raw_name_aliases") \
            .select("id, hit_count") \
            .eq("raw_name", raw_name) \
            .execute()

        if result.data and len(result.data) > 0:
            current = result.data[0]
            # ✅ FIXED: increment in Python, not with supabase.raw()
            new_count = current.get("hit_count", 0) + 1
            supabase.table("raw_name_aliases") \
                .update({
                    "hit_count": new_count,
                    "last_seen_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", current["id"]) \
                .execute()
            return str(current["id"])

        # Create new alias - ✅ Matches schema (no cleaned_name)
        alias_data = {
            "raw_name": raw_name,
            "resolved_place_id": resolved_place_id,
            "hit_count": 1,
            "first_seen_at": datetime.utcnow().isoformat(),
            "last_seen_at": datetime.utcnow().isoformat()
        }
        result = supabase.table("raw_name_aliases").insert(alias_data).execute()

        if result.data and len(result.data) > 0:
            return str(result.data[0]["id"])
        return None
    except Exception as e:
        print(f"Error creating alias: {e}")
        return None


# ====== TEST ======

if __name__ == "__main__":
    test_connection()