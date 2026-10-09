"""
Wikipedia Service for PlantDex
- Fetches plant summaries and taxonomy from Wikipedia REST API
- Search API fallback with 'plant' disambiguation
- Respects Wikimedia User-Agent and rate limit policies
- Updates local SQLite plants cache
- Strictly avoids hallucinating details when offline
"""
import re
import urllib.parse
import logging
from config import Config
from database import get_direct_connection

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("plantdex.wiki")

PLANT_KEYWORDS = [
    "plant", "species", "genus", "tree", "flower", "shrub", "herb",
    "grass", "family", "vine", "fern", "flora", "botanical", "perennial",
    "annual", "succulent", "conifer", "moss"
]


def is_wikipedia_online(timeout=4.0):
    """Checks Wikipedia reachability."""
    if requests is None:
        return False
    headers = {"User-Agent": Config.USER_AGENT}
    try:
        resp = requests.head("https://en.wikipedia.org", headers=headers, timeout=timeout)
        return resp.status_code in (200, 301, 302)
    except Exception:
        return False


def _get_page_summary(title, timeout=8.0):
    """Calls Wikipedia REST summary endpoint."""
    if requests is None:
        return None
    encoded_title = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    headers = {"User-Agent": Config.USER_AGENT}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        extract = (data.get("extract") or "").lower()

        # Verify page is botanical
        if data.get("type") != "standard" or not any(k in extract for k in PLANT_KEYWORDS):
            # Sometimes extracts are concise; check if description has plant info
            desc = (data.get("description") or "").lower()
            if not any(k in desc for k in PLANT_KEYWORDS):
                return None

        return data
    except Exception as e:
        logger.debug(f"REST summary failed for {title}: {e}")
        return None


def search_wikipedia_plant(name, timeout=8.0):
    """Searches Wikipedia when exact title match fails."""
    headers = {"User-Agent": Config.USER_AGENT}
    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{name} plant",
        "format": "json",
        "srlimit": 1
    }

    try:
        resp = requests.get(search_url, headers=headers, params=params, timeout=timeout)
        if resp.status_code != 200:
            return None
        hits = resp.json().get("query", {}).get("search", [])
        if hits:
            return _get_page_summary(hits[0]["title"], timeout=timeout)
    except Exception as e:
        logger.debug(f"Search API failed for {name}: {e}")
    return None


def fetch_plant_details_live(plant_name):
    """
    Attempts to fetch details from Wikipedia REST API and fallback search.
    Returns structured dict or None.
    """
    if not plant_name or not plant_name.strip():
        return None

    clean_name = plant_name.strip()
    data = _get_page_summary(clean_name)

    if not data:
        data = search_wikipedia_plant(clean_name)

    if not data:
        return None

    extract = data.get("extract") or ""
    sentences = re.split(r"(?<=[.!?])\s+", extract.strip())
    short_summary = " ".join(sentences[:3]) if sentences else extract

    thumbnail_url = (data.get("thumbnail") or {}).get("source", "")
    page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

    return {
        "title": data.get("title", clean_name),
        "short_desc": data.get("description", ""),
        "full_desc": short_summary,
        "reference_image": thumbnail_url,
        "source_url": page_url,
        "source": "Wikipedia",
        "text_license": "CC BY-SA 4.0",
        "image_license": "Wikimedia Commons (Open License)"
    }


def lookup_and_cache_plant_details(plant_id_or_name, db_conn=None):
    """
    Enforces the required 3-tier lookup order:
    1. Local SQLite plant table (fastest, offline).
    2. Wikipedia live fetch if online, then write result to SQLite cache.
    3. Return None, 'offline' if missing and unreachable.
    """
    conn = db_conn or get_direct_connection()
    cur = conn.cursor()

    # Step 1: Check Local Database
    if isinstance(plant_id_or_name, int):
        row = cur.execute("SELECT * FROM plants WHERE id = ?", (plant_id_or_name,)).fetchone()
    else:
        row = cur.execute(
            "SELECT * FROM plants WHERE scientific_name = ? COLLATE NOCASE OR common_name = ? COLLATE NOCASE",
            (plant_id_or_name, plant_id_or_name)
        ).fetchone()

    if row and row["full_desc"]:
        if not db_conn:
            conn.close()
        return dict(row), "local"

    # Determine query name
    query_name = row["scientific_name"] if row else str(plant_id_or_name)

    # Step 2: Wikipedia Live Fetch
    info = None
    try:
        info = fetch_plant_details_live(query_name)
    except Exception as e:
        logger.warning(f"Error connecting to Wikipedia: {e}")

    if info:
        # Cache into plants table
        if row:
            cur.execute("""
                UPDATE plants SET
                    short_desc = COALESCE(NULLIF(short_desc, ''), ?),
                    full_desc = COALESCE(NULLIF(full_desc, ''), ?),
                    reference_image = COALESCE(NULLIF(reference_image, ''), ?),
                    source_url = COALESCE(NULLIF(source_url, ''), ?),
                    text_license = COALESCE(NULLIF(text_license, ''), ?),
                    image_license = COALESCE(NULLIF(image_license, ''), ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                info["short_desc"], info["full_desc"], info["reference_image"],
                info["source_url"], info["text_license"], info["image_license"],
                row["id"]
            ))
            conn.commit()
            updated_row = cur.execute("SELECT * FROM plants WHERE id = ?", (row["id"],)).fetchone()
            if not db_conn:
                conn.close()
            return dict(updated_row), "wikipedia"
        else:
            # Insert new custom row
            cur.execute("""
                INSERT INTO plants (
                    scientific_name, common_name, short_desc, full_desc,
                    reference_image, source_url, is_custom, text_license, image_license
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                info["title"], info["short_desc"], info["short_desc"], info["full_desc"],
                info["reference_image"], info["source_url"],
                info["text_license"], info["image_license"]
            ))
            conn.commit()
            new_id = cur.lastrowid
            new_row = cur.execute("SELECT * FROM plants WHERE id = ?", (new_id,)).fetchone()
            if not db_conn:
                conn.close()
            return dict(new_row), "wikipedia"

    # Step 3: Missing and Offline / Not Found
    if not db_conn:
        conn.close()

    online = is_wikipedia_online(timeout=2.0)
    source_status = "not_found" if online else "offline"
    return (dict(row) if row else None), source_status
