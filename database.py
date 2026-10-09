"""
SQLite Database Layer for PlantDex
Handles thread-safe database connections, migrations, WAL mode for high concurrency,
and data access methods.
"""
import sqlite3
import json
import logging
from pathlib import Path
from config import Config

try:
    from flask import g
except ImportError:
    class _MockContext:
        pass
    g = _MockContext()

logger = logging.getLogger("plantdex.database")


def get_db():
    """Returns a SQLite connection for the current request/thread."""
    db = getattr(g, "db", None)
    if db is None:
        db_path = Config.DB_PATH
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(
            db_path,
            timeout=20.0
        )
        db.row_factory = sqlite3.Row
        # Optimize SQLite for concurrency on small CPU instances
        db.execute("PRAGMA foreign_keys = ON;")
        try:
            db.execute("PRAGMA journal_mode = WAL;")
            db.execute("PRAGMA synchronous = NORMAL;")
        except sqlite3.OperationalError:
            pass  # Some read-only or in-memory mount points may not allow WAL
        setattr(g, "db", db)
    return db


def close_db(e=None):
    """Closes database connection at the end of request."""
    db = getattr(g, "db", None)
    if db is not None:
        db.close()
        if hasattr(g, "db"):
            delattr(g, "db")


def get_direct_connection(db_path=None):
    """Direct standalone connection for CLI scripts, background workers, and tests."""
    target_path = db_path or Config.DB_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        target_path,
        timeout=20.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.OperationalError:
        pass
    return conn


def init_db(db_path=None, seed_path=None):
    """Initializes schema and seeds baseline botanical data."""
    conn = get_direct_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS plants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dex_num INTEGER UNIQUE,
        scientific_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        common_name TEXT COLLATE NOCASE,
        family TEXT,
        genus TEXT,
        short_desc TEXT,
        full_desc TEXT,
        reference_image TEXT,
        local_thumbnail TEXT,
        source_url TEXT,
        image_author TEXT,
        image_license TEXT,
        text_license TEXT,
        is_custom INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS captures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        plant_id INTEGER REFERENCES plants(id) ON DELETE SET NULL,
        custom_plant_name TEXT,
        status TEXT NOT NULL,
        name_source TEXT NOT NULL,
        details_source TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.0,
        user_photo_path TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS unknown_counters (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        last_number INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plant_name TEXT NOT NULL,
        capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
        attempts INTEGER DEFAULT 0,
        last_attempt TIMESTAMP,
        last_error TEXT,
        next_retry TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_captures_user_created ON captures(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_captures_plant ON captures(plant_id);
    CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
    CREATE INDEX IF NOT EXISTS idx_plants_dex ON plants(dex_num);
    CREATE INDEX IF NOT EXISTS idx_plants_scientific ON plants(scientific_name);
    CREATE INDEX IF NOT EXISTS idx_plants_common ON plants(common_name);
    CREATE INDEX IF NOT EXISTS idx_sync_queue_retry ON sync_queue(next_retry);
    """)
    conn.commit()

    # Load baseline model labels if table is empty
    count = cur.execute("SELECT COUNT(*) FROM plants WHERE is_custom = 0").fetchone()[0]
    if count == 0:
        seed_plants_from_files(conn, seed_path)

    conn.close()
    logger.info("Database schema initialized.")


def seed_plants_from_files(conn, seed_path=None):
    """Populates the plants table from labelmap and optional seed JSON."""
    cur = conn.cursor()
    labels_file = Path(Config.LABELS_PATH)
    seed_file = Path(seed_path or Config.SEED_DATA_PATH)

    seed_map = {}
    if seed_file.exists():
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                seed_list = json.load(f)
                for item in seed_list:
                    seed_map[item["scientific_name"].strip().lower()] = item
            logger.info(f"Loaded {len(seed_map)} seed records from {seed_file}")
        except Exception as e:
            logger.warning(f"Could not load seed JSON: {e}")

    if labels_file.exists():
        dex_counter = 1
        with open(labels_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[1:]:  # skip header
                parts = line.strip().split(",", 1)
                if len(parts) == 2:
                    label_id, label_name = parts[0].strip(), parts[1].strip()
                    if label_name.lower() == "background":
                        continue

                    sci_key = label_name.lower()
                    seed_info = seed_map.get(sci_key, {})

                    # Genus extraction fallback
                    genus = seed_info.get("genus") or (label_name.split()[0] if label_name else "")

                    cur.execute("""
                        INSERT OR IGNORE INTO plants (
                            dex_num, scientific_name, common_name, family, genus,
                            short_desc, full_desc, reference_image, local_thumbnail,
                            source_url, image_author, image_license, text_license, is_custom
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        dex_counter,
                        label_name,
                        seed_info.get("common_name", ""),
                        seed_info.get("family", ""),
                        genus,
                        seed_info.get("short_desc", ""),
                        seed_info.get("full_desc", ""),
                        seed_info.get("reference_image", ""),
                        seed_info.get("local_thumbnail", ""),
                        seed_info.get("source_url", ""),
                        seed_info.get("image_author", ""),
                        seed_info.get("image_license", "CC BY-SA 4.0"),
                        seed_info.get("text_license", "CC BY-SA 4.0"),
                    ))
                    dex_counter += 1
        conn.commit()
        logger.info(f"Seeded {dex_counter - 1} official plants into database.")


def get_next_unknown_number(conn, user_id):
    """
    Returns next sequential number for 'Unknown N'.
    Counts per user and never repeats, even if captures are deleted.
    """
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO unknown_counters (user_id, last_number)
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET last_number = last_number + 1
    """, (user_id,))
    conn.commit()

    row = cur.execute("SELECT last_number FROM unknown_counters WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else 1


def find_matching_plant(conn, name_query):
    """
    Checks if a user-supplied name matches a model label or common name in local DB.
    Returns (plant_dict or None, is_match)
    """
    if not name_query or not name_query.strip():
        return None, False

    clean_name = name_query.strip()
    cur = conn.cursor()

    # Exact scientific match
    row = cur.execute("""
        SELECT * FROM plants WHERE scientific_name = ? COLLATE NOCASE LIMIT 1
    """, (clean_name,)).fetchone()
    if row:
        return dict(row), True

    # Exact common name match
    row = cur.execute("""
        SELECT * FROM plants WHERE common_name = ? COLLATE NOCASE LIMIT 1
    """, (clean_name,)).fetchone()
    if row:
        return dict(row), True

    # Partial / substring match on common or scientific
    row = cur.execute("""
        SELECT * FROM plants 
        WHERE (scientific_name LIKE ? OR common_name LIKE ?) AND is_custom = 0
        ORDER BY dex_num ASC LIMIT 1
    """, (f"%{clean_name}%", f"%{clean_name}%")).fetchone()
    if row:
        return dict(row), True

    return None, False


def create_custom_plant(conn, name, details=None):
    """Creates a custom entry (no official Dex number, is_custom=1)."""
    cur = conn.cursor()
    details = details or {}
    clean_name = name.strip()

    # Check if custom plant already exists
    row = cur.execute("SELECT * FROM plants WHERE scientific_name = ? COLLATE NOCASE", (clean_name,)).fetchone()
    if row:
        return row["id"]

    cur.execute("""
        INSERT INTO plants (
            dex_num, scientific_name, common_name, family, genus,
            short_desc, full_desc, reference_image, local_thumbnail,
            source_url, image_author, image_license, text_license, is_custom
        ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        clean_name,
        details.get("common_name", clean_name),
        details.get("family", ""),
        details.get("genus", ""),
        details.get("short_desc", ""),
        details.get("full_desc", ""),
        details.get("reference_image", ""),
        details.get("local_thumbnail", ""),
        details.get("source_url", ""),
        details.get("image_author", ""),
        details.get("image_license", ""),
        details.get("text_license", "CC BY-SA 4.0"),
    ))
    conn.commit()
    return cur.lastrowid


def search_plant_names(conn, query, limit=8):
    """Returns autocomplete suggestions from the local plants table."""
    if not query or len(query.strip()) < 2:
        return []
    clean_q = f"%{query.strip()}%"
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT id, dex_num, scientific_name, common_name, is_custom
        FROM plants
        WHERE scientific_name LIKE ? OR common_name LIKE ?
        ORDER BY is_custom ASC, dex_num ASC, scientific_name ASC
        LIMIT ?
    """, (clean_q, clean_q, limit)).fetchall()
    return [dict(r) for r in rows]
