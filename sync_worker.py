"""
Background Sync Worker for PlantDex
Processes offline / details_pending captures when server is online.
- Thread-safe concurrency lock
- Small batches (never blocks HTTP request)
- Exponential backoff with maximum 5 retries
- Updates SQLite cache so all users benefit from fetched details
"""
import time
import logging
import threading
from datetime import datetime, timedelta
from database import get_direct_connection
from wiki_service import lookup_and_cache_plant_details, is_wikipedia_online

logger = logging.getLogger("plantdex.sync")

_sync_lock = threading.Lock()
MAX_RETRIES = 5


def enqueue_capture_sync(conn, plant_name, capture_id):
    """Adds a capture to the sync queue for future background resolution."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sync_queue (plant_name, capture_id, attempts, next_retry)
        VALUES (?, ?, 0, CURRENT_TIMESTAMP)
    """, (plant_name, capture_id))
    conn.commit()
    logger.info(f"Enqueued sync for capture {capture_id} ({plant_name})")


def process_sync_queue(batch_size=5):
    """
    Processes up to batch_size pending items in sync_queue.
    Thread-safe; returns number of items successfully synced.
    """
    if not _sync_lock.acquire(blocking=False):
        logger.debug("Sync worker already running; skipping duplicate cycle.")
        return 0

    synced_count = 0
    try:
        # Quick online check before attempting HTTP requests
        if not is_wikipedia_online(timeout=3.0):
            logger.debug("Server is offline; postponing sync queue processing.")
            return 0

        conn = get_direct_connection()
        cur = conn.cursor()

        # Fetch pending items ready for retry
        rows = cur.execute("""
            SELECT q.id as queue_id, q.plant_name, q.capture_id, q.attempts,
                   c.plant_id, c.user_id, c.status
            FROM sync_queue q
            JOIN captures c ON q.capture_id = c.id
            WHERE q.attempts < ? AND q.next_retry <= CURRENT_TIMESTAMP
            ORDER BY q.next_retry ASC
            LIMIT ?
        """, (MAX_RETRIES, batch_size)).fetchall()

        for item in rows:
            q_id = item["queue_id"]
            p_name = item["plant_name"]
            c_id = item["capture_id"]
            attempts = item["attempts"] + 1

            logger.info(f"Syncing pending details for {p_name} (Attempt {attempts}/{MAX_RETRIES})")
            details, source = lookup_and_cache_plant_details(p_name, db_conn=conn)

            if details and details.get("full_desc"):
                # Success! Update capture status to complete
                cur.execute("""
                    UPDATE captures 
                    SET status = 'complete', details_source = 'wikipedia', plant_id = ?
                    WHERE id = ?
                """, (details["id"], c_id))

                # Delete from queue
                cur.execute("DELETE FROM sync_queue WHERE id = ?", (q_id,))
                conn.commit()
                synced_count += 1
                logger.info(f"Successfully resolved details for capture {c_id} ({p_name})")
            else:
                # Failure or not found
                if attempts >= MAX_RETRIES:
                    # Mark as no_details_found so user can edit or retry manually
                    cur.execute("""
                        UPDATE captures SET status = 'no_details_found' WHERE id = ?
                    """, (c_id,))
                    cur.execute("DELETE FROM sync_queue WHERE id = ?", (q_id,))
                    conn.commit()
                    logger.warning(f"Exceeded max retries for capture {c_id}. Marked as no_details_found.")
                else:
                    # Exponential backoff: 2^(attempts) * 30 seconds
                    backoff_seconds = (2 ** attempts) * 30
                    next_retry_time = datetime.now() + timedelta(seconds=backoff_seconds)
                    cur.execute("""
                        UPDATE sync_queue 
                        SET attempts = ?, last_attempt = CURRENT_TIMESTAMP, 
                            last_error = ?, next_retry = ?
                        WHERE id = ?
                    """, (attempts, f"Details lookup returned {source}", next_retry_time, q_id))
                    conn.commit()

        conn.close()
    except Exception as e:
        logger.error(f"Error in sync worker: {e}", exc_info=True)
    finally:
        _sync_lock.release()

    return synced_count


def trigger_sync_in_background(batch_size=5):
    """Launches non-blocking background sync thread."""
    thread = threading.Thread(
        target=process_sync_queue,
        args=(batch_size,),
        daemon=True,
        name="PlantDexSyncWorker"
    )
    thread.start()
