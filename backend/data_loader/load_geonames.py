"""
Task 3 — CSV / Data Loading (Owner: Member 4)

Downloads GeoNames India data and loads it into the Supabase database.

Files loaded:
  - IN.zip  → geonames_places
  - alternateNamesV2.zip → geonames_alternate_names (filtered to India geoname_ids)

GeoNames files are TAB-separated, NOT comma-separated.
Column order comes from the documented GeoNames layout, not guesswork.

Usage:
    python -m backend.data_loader.load_geonames

Requires environment variables:
    SUPABASE_URL          — e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY  — service-role key (NOT the anon key)
"""

from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEONAMES_IN_URL = "https://download.geonames.org/export/dump/IN.zip"
GEONAMES_ALT_NAMES_URL = "https://download.geonames.org/export/dump/alternateNamesV2.zip"

DATA_DIR = Path(__file__).parent / "data"

BATCH_SIZE = 1000  # rows per upsert call — keeps request bodies under Supabase limits

# GeoNames IN.txt documented column layout (19 fields, tab-separated):
# https://download.geonames.org/export/dump/readme.txt
IN_COLUMNS = [
    "geonameid",        # 0  integer id
    "name",             # 1  name of geographical point
    "asciiname",        # 2  name in plain ascii characters
    "alternatenames",   # 3  comma-separated alternates (ignored — we use the dedicated file)
    "latitude",         # 4  latitude in decimal degrees
    "longitude",        # 5  longitude in decimal degrees
    "feature_class",    # 6  single character classification
    "feature_code",     # 7  code for feature type
    "country_code",     # 8  ISO-3166 2-letter country code
    "cc2",              # 9  alternate country codes (ignored)
    "admin1_code",      # 10 fipscode / ISO code for first admin division
    "admin2_code",      # 11 code for second admin division
    "admin3_code",      # 12 code for third admin division (ignored)
    "admin4_code",      # 13 code for fourth admin division (ignored)
    "population",       # 14 bigint
    "elevation",        # 15 in meters (can be empty)
    "dem",              # 16 digital elevation model (ignored)
    "timezone",         # 17 iana timezone id
    "modification_date",# 18 date of last modification (yyyy-MM-dd)
]

# alternateNamesV2.txt documented column layout (10 fields, tab-separated):
ALT_COLUMNS = [
    "alternateNameId",  # 0  unique id for this alternate name
    "geonameid",        # 1  geonameid referring to geonames_places
    "isolanguage",      # 2  iso 639 language code or link/abbr/etc
    "alternate_name",   # 3  the alternate name itself
    "isPreferredName",  # 4  '1' if preferred in that language
    "isShortName",      # 5  '1' if short name
    "isColloquial",     # 6  '1' if colloquial
    "isHistoric",       # 7  '1' if historic
    "from",             # 8  validity start date (ignored — not in our schema)
    "to",               # 9  validity end date (ignored — not in our schema)
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_file(url: str, dest: Path) -> Path:
    """Download a file with progress reporting. Skips if already exists.
    Supports resuming interrupted downloads with Range requests."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if download is already fully complete by doing a HEAD request to get total length
    try:
        head_resp = requests.head(url, timeout=30)
        head_resp.raise_for_status()
        total_expected = int(head_resp.headers.get("content-length", 0))
    except Exception as e:
        print(f"  Warning: could not retrieve head info for {url}: {e}")
        total_expected = 0

    if dest.exists():
        if total_expected and dest.stat().st_size == total_expected:
            print(f"  [skip] {dest.name} already fully downloaded ({dest.stat().st_size // 1024 // 1024}MB).")
            return dest
        elif not total_expected:
            print(f"  [skip] {dest.name} already downloaded (unknown total length).")
            return dest

    max_retries = 10
    retry_delay = 5

    for attempt in range(1, max_retries + 1):
        try:
            downloaded = dest.stat().st_size if dest.exists() else 0
            headers = {}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"
                print(f"  Resuming {dest.name} from byte {downloaded} (attempt {attempt}/{max_retries}) ...")
                mode = "ab"
            else:
                print(f"  Downloading {url} (attempt {attempt}/{max_retries}) ...")
                mode = "wb"

            resp = requests.get(url, headers=headers, stream=True, timeout=60)
            
            # If the server doesn't support Range requests, it might return 200 instead of 206.
            # In that case, we start over.
            if downloaded > 0 and resp.status_code == 200:
                print("  Server ignored Range request. Restarting download...")
                downloaded = 0
                mode = "wb"
            elif resp.status_code not in (200, 206):
                resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0)) + downloaded

            with open(dest, mode) as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            print(f"\r  {dest.name}: {pct}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)", end="", flush=True)
            print()
            
            # Verify file size matches expected size
            if total_expected and dest.stat().st_size < total_expected:
                raise requests.exceptions.ChunkedEncodingError("File size is smaller than expected content-length header.")
            
            return dest

        except (requests.RequestException, requests.exceptions.ChunkedEncodingError) as e:
            print(f"\n  Connection issue during download: {e}")
            if attempt < max_retries:
                import time
                print(f"  Waiting {retry_delay}s before retrying...")
                time.sleep(retry_delay)
            else:
                raise e

    raise Exception(f"Failed to download {url} after {max_retries} attempts.")



def _parse_bool_field(val: str) -> bool:
    """GeoNames uses '1' for true, empty or '0' for false."""
    return val.strip() == "1"


def _safe_int(val: str, default: int = 0) -> int:
    """Parse integer from GeoNames field, returning default if empty."""
    val = val.strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _safe_float(val: str) -> float | None:
    """Parse float from GeoNames field, returning None if empty."""
    val = val.strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _execute_batch_with_retry(supabase_table, batch, on_conflict_col, max_retries=5):
    """Executes a Supabase upsert batch with exponential backoff retries."""
    import time
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            supabase_table.upsert(batch, on_conflict=on_conflict_col).execute()
            return
        except Exception as e:
            print(f"\n  [WARN] Database batch write failed (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                print(f"  Waiting {delay}s before retrying...")
                time.sleep(delay)
                delay *= 2
            else:
                raise e


# ---------------------------------------------------------------------------
# Loading: geonames_places
# ---------------------------------------------------------------------------

def _load_places(supabase: Client, zip_path: Path) -> set[int]:
    """Parse IN.txt from the zip, insert into geonames_places, return set of
    geoname_ids for filtering alternate names."""

    print("\n--- Loading geonames_places ---")

    geoname_ids: set[int] = set()
    rows: list[dict] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        # IN.zip contains IN.txt (the main data file)
        txt_name = [n for n in zf.namelist() if n.endswith(".txt") and not n.startswith("readme")][0]
        print(f"  Parsing {txt_name} ...")

        with zf.open(txt_name) as f:
            reader = csv.reader(
                io.TextIOWrapper(f, encoding="utf-8"),
                delimiter="\t",
                quoting=csv.QUOTE_NONE,
            )
            for line_num, fields in enumerate(reader, 1):
                if len(fields) < 19:
                    continue  # skip malformed lines

                geoname_id = _safe_int(fields[0])
                if geoname_id == 0:
                    continue

                geoname_ids.add(geoname_id)

                elevation = _safe_int(fields[15], default=0)
                population = _safe_int(fields[14], default=0)
                mod_date = fields[18].strip() if fields[18].strip() else None

                row = {
                    "geoname_id": geoname_id,
                    "name": fields[1],
                    "ascii_name": fields[2] if fields[2].strip() else None,
                    "latitude": float(fields[4]),
                    "longitude": float(fields[5]),
                    "feature_class": fields[6].strip() if fields[6].strip() else None,
                    "feature_code": fields[7].strip() if fields[7].strip() else None,
                    "country_code": fields[8].strip() if fields[8].strip() else None,
                    "admin1_code": fields[10].strip() if fields[10].strip() else None,
                    "admin2_code": fields[11].strip() if fields[11].strip() else None,
                    "population": population,
                    "elevation": elevation if fields[15].strip() else None,
                    "timezone": fields[17].strip() if fields[17].strip() else None,
                    "modification_date": mod_date,
                }
                rows.append(row)

                if line_num % 50000 == 0:
                    print(f"  Parsed {line_num} lines ...", flush=True)

    print(f"  Total places parsed: {len(rows)}")

    # Batch upsert with retry logic
    total_inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        try:
            _execute_batch_with_retry(supabase.table("geonames_places"), batch, "geoname_id")
            total_inserted += len(batch)
            if total_inserted % 10000 == 0 or total_inserted == len(rows):
                print(f"  Inserted {total_inserted}/{len(rows)} places ...", flush=True)
        except Exception as e:
            print(f"\n  [FATAL ERROR] Batch starting at row {i} failed after all retries: {e}")
            print("  Aborting load.")
            raise e

    print(f"  Done — {total_inserted} places loaded.")
    return geoname_ids


# ---------------------------------------------------------------------------
# Loading: geonames_alternate_names
# ---------------------------------------------------------------------------

def _load_alternate_names(supabase: Client, zip_path: Path, india_geoname_ids: set[int]) -> None:
    """Parse alternateNamesV2.txt, keep only rows matching India geoname_ids,
    insert into geonames_alternate_names."""

    print("\n--- Loading geonames_alternate_names ---")

    rows: list[dict] = []
    kept = 0
    scanned = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        # alternateNamesV2.zip contains alternateNamesV2.txt and iso-languagecodes.txt
        # We explicitly search for 'alternateNamesV2.txt'
        txt_name = [n for n in zf.namelist() if n.endswith("alternateNamesV2.txt") or (n.endswith(".txt") and "alternateNames" in n)][0]
        print(f"  Parsing {txt_name} (filtering to India geoname_ids) ...")

        with zf.open(txt_name) as f:
            reader = csv.reader(
                io.TextIOWrapper(f, encoding="utf-8"),
                delimiter="\t",
                quoting=csv.QUOTE_NONE,
            )
            for fields in reader:
                scanned += 1
                if scanned % 500000 == 0:
                    print(f"  Scanned {scanned} lines, kept {kept} ...", flush=True)

                if len(fields) < 8:
                    continue

                geoname_id = _safe_int(fields[1])
                if geoname_id not in india_geoname_ids:
                    continue

                alt_name_id = _safe_int(fields[0])
                if alt_name_id == 0:
                    continue

                alternate_name = fields[3].strip()
                if not alternate_name:
                    continue

                kept += 1
                row = {
                    "alternate_name_id": alt_name_id,
                    "geoname_id": geoname_id,
                    "iso_language": fields[2].strip() if fields[2].strip() else None,
                    "alternate_name": alternate_name,
                    "is_preferred_name": _parse_bool_field(fields[4]),
                    "is_short_name": _parse_bool_field(fields[5]),
                    "is_colloquial": _parse_bool_field(fields[6]),
                    "is_historic": _parse_bool_field(fields[7]),
                }
                rows.append(row)

                # Flush in batches to avoid memory buildup on the large global file
                if len(rows) >= BATCH_SIZE:
                    try:
                        _execute_batch_with_retry(supabase.table("geonames_alternate_names"), rows, "alternate_name_id")
                    except Exception as e:
                        print(f"\n  [FATAL ERROR] Alt-names batch write failed after all retries: {e}")
                        raise e
                    rows.clear()

    # Flush remaining
    if rows:
        try:
            _execute_batch_with_retry(supabase.table("geonames_alternate_names"), rows, "alternate_name_id")
        except Exception as e:
            print(f"\n  [FATAL ERROR] Final alt-names batch write failed after all retries: {e}")
            raise e

    print(f"  Done — scanned {scanned} lines, loaded {kept} alternate names for India.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env")
        sys.exit(1)

    supabase: Client = create_client(supabase_url, supabase_key)

    # Step 1: Download files
    print("=== Step 1: Download GeoNames data ===")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    in_zip = _download_file(GEONAMES_IN_URL, DATA_DIR / "IN.zip")
    alt_zip = _download_file(GEONAMES_ALT_NAMES_URL, DATA_DIR / "alternateNamesV2.zip")

    # Step 2: Load places (must be first — alternate names FK references places)
    print("\n=== Step 2: Load geonames_places ===")
    india_ids = _load_places(supabase, in_zip)

    # Step 3: Load alternate names (filtered to India only)
    print("\n=== Step 3: Load geonames_alternate_names ===")
    _load_alternate_names(supabase, alt_zip, india_ids)

    print("\n=== All done! ===")
    print(f"India geoname_ids loaded: {len(india_ids)}")
    print("Verify with: SELECT * FROM geonames_places WHERE name = 'Thane';")


if __name__ == "__main__":
    main()
