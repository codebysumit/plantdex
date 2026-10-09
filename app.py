"""
PlantDex - Open-Source Botanical Pokédex
Flask Application Factory & Route Handlers
Optimized for Render (CPU-only, 512 MB RAM, ephemeral vs persistent storage)
"""
import os
import sys
import logging
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory, abort, g
)

from config import Config
from database import (
    get_db, close_db, init_db, get_next_unknown_number,
    find_matching_plant, create_custom_plant, search_plant_names
)
from auth import (
    register_user, authenticate_user, login_required,
    generate_csrf_token, validate_csrf_token,
    check_rate_limit, verify_user_owns_capture
)
from image_utils import process_user_photo
from model_engine import (
    initialize_model, classify_image, evaluate_confidence,
    get_model_status, get_labels
)
from wiki_service import lookup_and_cache_plant_details, fetch_plant_details_live
from sync_worker import trigger_sync_in_background, enqueue_capture_sync
from gemini_helper import double_check_with_gemini
from cli import cli_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("plantdex")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints & teardown
    app.register_blueprint(cli_bp)
    app.teardown_appcontext(close_db)

    # Context processors
    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": generate_csrf_token,
            "current_user": session.get("username"),
            "current_user_id": session.get("user_id"),
            "has_gemini": bool(Config.GEMINI_API_KEY),
        }

    # Initialize DB and TFLite model on startup
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            logger.warning(f"Database init notice: {e}")

        try:
            initialize_model()
        except Exception as e:
            logger.warning(f"Model init notice: {e}")

        # Trigger initial sync for any pending items
        try:
            trigger_sync_in_background(batch_size=5)
        except Exception:
            pass

    # -------------------------------------------------------------
    # Static & Upload Routes
    # -------------------------------------------------------------
    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        response = send_from_directory(Config.UPLOADS_DIR, filename)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.route("/sw.js")
    def serve_service_worker():
        response = send_from_directory(Path(__file__).parent / "static", "sw.js")
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.route("/manifest.json")
    def serve_manifest():
        return send_from_directory(Path(__file__).parent / "static", "manifest.json")

    @app.route("/healthz")
    def health_check():
        """Render health check route and memory inspection."""
        mem_mb = 0
        if sys.platform != "win32":
            import resource
            mem_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)

        status = {
            "status": "healthy",
            "model": get_model_status(),
            "storage_path": Config.DATA_DIR,
            "memory_usage_mb": mem_mb,
            "total_plants_known": len(get_labels()),
        }
        return jsonify(status), 200

    # -------------------------------------------------------------
    # Authentication Routes
    # -------------------------------------------------------------
    @app.route("/register", methods=["GET", "POST"])
    def auth_register():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            validate_csrf_token()
            if not check_rate_limit("register", limit=10):
                abort(429, description="Too many registration attempts. Please wait a minute.")

            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user_id, err = register_user(username, password)
            if err:
                flash(err, "error")
                return render_template("register.html", username=username)

            session.clear()
            session["user_id"] = user_id
            session["username"] = username.strip()
            flash(f"Welcome to PlantDex, {username}! Your botanical journey starts now.", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def auth_login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            validate_csrf_token()
            if not check_rate_limit("login", limit=Config.RATE_LIMIT_LOGIN_MAX):
                abort(429, description="Too many login attempts. Please wait a minute.")

            username = request.form.get("username", "")
            password = request.form.get("password", "")
            user, err = authenticate_user(username, password)
            if err:
                flash(err, "error")
                return render_template("login.html", username=username)

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")

            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout", methods=["GET", "POST"])
    def auth_logout():
        session.clear()
        flash("You have been signed out.", "info")
        return redirect(url_for("landing_page"))

    # -------------------------------------------------------------
    # Landing & Public Pages
    # -------------------------------------------------------------
    @app.route("/")
    def landing_page():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/credits")
    def credits_page():
        return render_template("credits.html")

    # -------------------------------------------------------------
    # Dashboard (PlantDex Collection)
    # -------------------------------------------------------------
    @app.route("/dex")
    @login_required
    def dashboard():
        # Trigger background sync worker on dashboard visit
        trigger_sync_in_background(batch_size=3)

        user_id = session["user_id"]
        db = get_db()

        # Stats calculation
        total_model_plants = db.execute("SELECT COUNT(*) FROM plants WHERE is_custom = 0").fetchone()[0] or 2101
        
        # Official caught count (only non-custom plants count towards completion %)
        official_caught = db.execute("""
            SELECT COUNT(DISTINCT c.plant_id)
            FROM captures c
            JOIN plants p ON c.plant_id = p.id
            WHERE c.user_id = ? AND p.is_custom = 0
              AND c.status IN ('identified_by_model', 'named_by_user', 'complete')
        """, (user_id,)).fetchone()[0] or 0

        completion_pct = round((official_caught / total_model_plants) * 100, 1) if total_model_plants > 0 else 0

        total_captures = db.execute(
            "SELECT COUNT(*) FROM captures WHERE user_id = ?", (user_id,)
        ).fetchone()[0] or 0

        # Query Filters
        search_query = request.args.get("q", "").strip()
        status_filter = request.args.get("filter", "all")
        sort_by = request.args.get("sort", "newest")
        page = max(1, int(request.args.get("page", 1)))
        per_page = 18
        offset = (page - 1) * per_page

        base_sql = """
            SELECT c.id as capture_id, c.status, c.name_source, c.confidence,
                   c.user_photo_path, c.custom_plant_name, c.created_at,
                   p.id as plant_id, p.dex_num, p.scientific_name, p.common_name,
                   p.reference_image, p.local_thumbnail, p.is_custom
            FROM captures c
            LEFT JOIN plants p ON c.plant_id = p.id
            WHERE c.user_id = ?
        """
        params = [user_id]

        if search_query:
            base_sql += """
                AND (p.scientific_name LIKE ? OR p.common_name LIKE ? OR c.custom_plant_name LIKE ?)
            """
            q_like = f"%{search_query}%"
            params.extend([q_like, q_like, q_like])

        if status_filter == "identified":
            base_sql += " AND c.status = 'identified_by_model'"
        elif status_filter == "named":
            base_sql += " AND c.status = 'named_by_user'"
        elif status_filter == "unknown":
            base_sql += " AND c.status = 'unknown'"
        elif status_filter == "pending":
            base_sql += " AND c.status IN ('details_pending', 'no_details_found')"

        if sort_by == "dex":
            base_sql += " ORDER BY (p.dex_num IS NULL), p.dex_num ASC, c.created_at DESC"
        elif sort_by == "name":
            base_sql += " ORDER BY COALESCE(p.common_name, p.scientific_name, c.custom_plant_name) ASC"
        else:  # newest
            base_sql += " ORDER BY c.created_at DESC"

        # Count total filtered items
        count_sql = f"SELECT COUNT(*) FROM ({base_sql})"
        total_items = db.execute(count_sql, params).fetchone()[0] or 0
        total_pages = max(1, (total_items + per_page - 1) // per_page)

        # Paginated results
        base_sql += f" LIMIT {per_page} OFFSET {offset}"
        captures_rows = db.execute(base_sql, params).fetchall()

        # Silhouette teaser cards (undiscovered Dex entries to encourage exploration)
        silhouettes = db.execute("""
            SELECT dex_num, scientific_name
            FROM plants
            WHERE is_custom = 0 
              AND id NOT IN (SELECT DISTINCT plant_id FROM captures WHERE user_id = ? AND plant_id IS NOT NULL)
            ORDER BY dex_num ASC
            LIMIT 6
        """, (user_id,)).fetchall()

        # Recent catches banner
        recent_catches = db.execute("""
            SELECT c.id, c.user_photo_path, c.created_at,
                   COALESCE(p.common_name, p.scientific_name, c.custom_plant_name) as display_name,
                   COALESCE(p.local_thumbnail, p.reference_image) as ref_img
            FROM captures c
            LEFT JOIN plants p ON c.plant_id = p.id
            WHERE c.user_id = ?
            ORDER BY c.created_at DESC LIMIT 5
        """, (user_id,)).fetchall()

        return render_template(
            "dashboard.html",
            captures=captures_rows,
            official_caught=official_caught,
            total_model_plants=total_model_plants,
            completion_pct=completion_pct,
            total_captures=total_captures,
            silhouettes=silhouettes,
            recent_catches=recent_catches,
            page=page,
            total_pages=total_pages,
            search_query=search_query,
            status_filter=status_filter,
            sort_by=sort_by
        )

    # -------------------------------------------------------------
    # Plant Capture & Inference Pipeline
    # -------------------------------------------------------------
    @app.route("/capture")
    @login_required
    def capture_page():
        return render_template("capture.html")

    @app.route("/capture/scan", methods=["POST"])
    @login_required
    def capture_scan():
        validate_csrf_token()
        if not check_rate_limit("scan", limit=Config.RATE_LIMIT_SCAN_MAX):
            abort(429, description="Scan rate limit reached. Please wait a moment.")

        if "photo" not in request.files:
            flash("No photo was provided. Please take or upload a plant photo.", "error")
            return redirect(url_for("capture_page"))

        file = request.files["photo"]
        if file.filename == "":
            flash("No photo selected.", "error")
            return redirect(url_for("capture_page"))

        try:
            # 1. Image verification, orientation fix, EXIF stripping, 512px WebP save
            relative_filename = process_user_photo(file)
            full_photo_path = Path(Config.UPLOADS_DIR) / relative_filename

            # 2. Multi-crop TFLite classification
            predictions = classify_image(full_photo_path, top_k=3)
            best_label, best_conf = predictions[0]
            tier = evaluate_confidence(best_conf)

            user_id = session["user_id"]
            db = get_db()
            cur = db.cursor()

            # Store predictions JSON for choices or double-check
            notes_payload = f"AI: {best_label} ({best_conf:.1%})"

            if tier == "CAUGHT":
                # >= 50% Confidence: Official Catch!
                matched_plant, is_match = find_matching_plant(db, best_label)
                plant_id = matched_plant["id"] if matched_plant else None

                # Details lookup
                details, det_source = lookup_and_cache_plant_details(best_label, db_conn=db)
                if details:
                    plant_id = details["id"]

                cur.execute("""
                    INSERT INTO captures (
                        user_id, plant_id, status, name_source, details_source,
                        confidence, user_photo_path, notes
                    ) VALUES (?, ?, 'identified_by_model', 'model', ?, ?, ?, ?)
                """, (
                    user_id, plant_id, det_source, best_conf, relative_filename, notes_payload
                ))
                db.commit()
                capture_id = cur.lastrowid
                flash(f"GOTCHA! You caught {best_label} ({best_conf:.0%})!", "success")
                return redirect(url_for("plant_detail", capture_id=capture_id, caught="1"))

            elif tier == "MAYBE":
                # 25% - 50% Confidence: Present Top 3 Choices
                cur.execute("""
                    INSERT INTO captures (
                        user_id, plant_id, status, name_source, details_source,
                        confidence, user_photo_path, notes
                    ) VALUES (?, NULL, 'details_pending', 'none', 'none', ?, ?, ?)
                """, (user_id, best_conf, relative_filename, notes_payload))
                db.commit()
                capture_id = cur.lastrowid

                # Store candidate options in session
                session[f"candidates_{capture_id}"] = [
                    {"name": name, "confidence": conf} for name, conf in predictions
                ]
                return redirect(url_for("maybe_choices", capture_id=capture_id))

            else:
                # < 25% Confidence: NOT SURE -> Trigger Unknown / User Names Flow
                cur.execute("""
                    INSERT INTO captures (
                        user_id, plant_id, status, name_source, details_source,
                        confidence, user_photo_path, notes
                    ) VALUES (?, NULL, 'details_pending', 'none', 'none', ?, ?, ?)
                """, (user_id, best_conf, relative_filename, notes_payload))
                db.commit()
                capture_id = cur.lastrowid
                return redirect(url_for("identify_unknown", capture_id=capture_id))

        except ValueError as ve:
            flash(str(ve), "error")
            return redirect(url_for("capture_page"))
        except Exception as e:
            logger.error(f"Scan pipeline failed: {e}", exc_info=True)
            flash("An unexpected error occurred during plant identification.", "error")
            return redirect(url_for("capture_page"))

    # -------------------------------------------------------------
    # Confidence Tier Handling: MAYBE Choices Flow
    # -------------------------------------------------------------
    @app.route("/capture/choices/<int:capture_id>")
    @login_required
    def maybe_choices(capture_id):
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        candidates = session.get(f"candidates_{capture_id}", [])

        # Enrich candidate options with common names and reference thumbnails
        db = get_db()
        enriched = []
        for cand in candidates:
            row = db.execute("""
                SELECT common_name, reference_image, local_thumbnail, short_desc
                FROM plants WHERE scientific_name = ? COLLATE NOCASE
            """, (cand["name"],)).fetchone()
            enriched.append({
                "scientific_name": cand["name"],
                "confidence": cand["confidence"],
                "common_name": row["common_name"] if row else "",
                "thumbnail": (row["local_thumbnail"] or row["reference_image"]) if row else "",
                "short_desc": row["short_desc"] if row else "",
            })

        return render_template("maybe_choices.html", capture=capture, candidates=enriched)

    @app.route("/capture/choose/<int:capture_id>", methods=["POST"])
    @login_required
    def make_choice(capture_id):
        validate_csrf_token()
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        chosen_name = request.form.get("chosen_name", "").strip()
        action = request.form.get("action", "select")

        db = get_db()
        cur = db.cursor()

        if action == "reject":
            # User rejects all top 3 guesses -> Proceed to Unknown Plants flow
            return redirect(url_for("identify_unknown", capture_id=capture_id))

        if action == "retake":
            # Discard capture and retake
            cur.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
            db.commit()
            flash("Photo discarded. Take another photo with good lighting and one leaf in frame.", "info")
            return redirect(url_for("capture_page"))

        # User selected an official candidate
        if chosen_name:
            matched, _ = find_matching_plant(db, chosen_name)
            details, det_src = lookup_and_cache_plant_details(chosen_name, db_conn=db)
            plant_id = (details["id"] if details else (matched["id"] if matched else None))

            cur.execute("""
                UPDATE captures 
                SET plant_id = ?, status = 'identified_by_model', name_source = 'model',
                    details_source = ?
                WHERE id = ?
            """, (plant_id, det_src, capture_id))
            db.commit()

            # Clean session
            session.pop(f"candidates_{capture_id}", None)
            flash(f"Confirmed! {chosen_name} added to your PlantDex.", "success")
            return redirect(url_for("plant_detail", capture_id=capture_id, caught="1"))

        return redirect(url_for("maybe_choices", capture_id=capture_id))

    # -------------------------------------------------------------
    # Unknown Plants & User Naming Flow
    # -------------------------------------------------------------
    @app.route("/capture/unknown/<int:capture_id>")
    @login_required
    def identify_unknown(capture_id):
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        return render_template("identify_unknown.html", capture=capture)

    @app.route("/capture/name/<int:capture_id>", methods=["POST"])
    @login_required
    def save_plant_name(capture_id):
        validate_csrf_token()
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        knows_name = request.form.get("knows_name", "no")
        typed_name = request.form.get("plant_name", "").strip()[:80]

        db = get_db()
        cur = db.cursor()
        user_id = session["user_id"]

        if knows_name == "no" or not typed_name:
            # Save as Unknown 1, Unknown 2, etc. (monotonic counter per user)
            unknown_num = get_next_unknown_number(db, user_id)
            unknown_label = f"Unknown {unknown_num}"

            cur.execute("""
                UPDATE captures 
                SET custom_plant_name = ?, status = 'unknown', name_source = 'none',
                    details_source = 'none'
                WHERE id = ?
            """, (unknown_label, capture_id))
            db.commit()
            flash(f"Saved as {unknown_label}. You can name it anytime from your Dex!", "info")
            return redirect(url_for("plant_detail", capture_id=capture_id))

        # User supplied a name: Check if it matches model label or known common name
        matched_plant, is_match = find_matching_plant(db, typed_name)

        if is_match and matched_plant:
            # Official match! Link to official Dex entry
            cur.execute("""
                UPDATE captures 
                SET plant_id = ?, custom_plant_name = NULL, status = 'named_by_user',
                    name_source = 'user', details_source = 'local'
                WHERE id = ?
            """, (matched_plant["id"], capture_id))
            db.commit()
            flash(f"Matched with official Dex entry: {matched_plant['scientific_name']}!", "success")
            return redirect(url_for("plant_detail", capture_id=capture_id))

        # No direct local match: Query Wikipedia
        wiki_data = fetch_plant_details_live(typed_name)
        if wiki_data and wiki_data.get("full_desc"):
            # Show "Is this your plant?" confirmation
            session[f"pending_wiki_{capture_id}"] = {
                "name": typed_name,
                "wiki": wiki_data
            }
            return redirect(url_for("confirm_wikipedia", capture_id=capture_id))

        # Wikipedia returned nothing or offline: create custom entry with pending details
        custom_id = create_custom_plant(db, typed_name)
        cur.execute("""
            UPDATE captures 
            SET plant_id = ?, custom_plant_name = ?, status = 'details_pending',
                name_source = 'user', details_source = 'none'
            WHERE id = ?
        """, (custom_id, typed_name, capture_id))
        db.commit()

        # Enqueue in sync queue for automatic retrieval when server is online
        enqueue_capture_sync(db, typed_name, capture_id)

        flash(f"Saved '{typed_name}'. Botanical details will load when online.", "info")
        return redirect(url_for("plant_detail", capture_id=capture_id))

    @app.route("/capture/confirm-wiki/<int:capture_id>", methods=["GET", "POST"])
    @login_required
    def confirm_wikipedia(capture_id):
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        wiki_payload = session.get(f"pending_wiki_{capture_id}")

        if not wiki_payload:
            return redirect(url_for("plant_detail", capture_id=capture_id))

        if request.method == "POST":
            validate_csrf_token()
            user_agreed = request.form.get("confirm", "no") == "yes"
            db = get_db()
            cur = db.cursor()

            typed_name = wiki_payload["name"]
            wiki_info = wiki_payload["wiki"]

            if user_agreed:
                # Save with Wikipedia details
                custom_id = create_custom_plant(db, typed_name, details={
                    "common_name": wiki_info.get("title", typed_name),
                    "short_desc": wiki_info.get("short_desc", ""),
                    "full_desc": wiki_info.get("full_desc", ""),
                    "reference_image": wiki_info.get("reference_image", ""),
                    "source_url": wiki_info.get("source_url", ""),
                    "text_license": wiki_info.get("text_license", "CC BY-SA 4.0")
                })
                cur.execute("""
                    UPDATE captures 
                    SET plant_id = ?, custom_plant_name = ?, status = 'complete',
                        name_source = 'user', details_source = 'wikipedia'
                    WHERE id = ?
                """, (custom_id, typed_name, capture_id))
            else:
                # Keep custom name without Wikipedia details
                custom_id = create_custom_plant(db, typed_name)
                cur.execute("""
                    UPDATE captures 
                    SET plant_id = ?, custom_plant_name = ?, status = 'named_by_user',
                        name_source = 'user', details_source = 'none'
                    WHERE id = ?
                """, (custom_id, typed_name, capture_id))

            db.commit()
            session.pop(f"pending_wiki_{capture_id}", None)
            flash(f"Botanical record updated for {typed_name}!", "success")
            return redirect(url_for("plant_detail", capture_id=capture_id))

        return render_template(
            "confirm_wiki.html",
            capture=capture,
            wiki=wiki_payload["wiki"],
            typed_name=wiki_payload["name"]
        )

    # -------------------------------------------------------------
    # Plant Detail View & Actions
    # -------------------------------------------------------------
    @app.route("/dex/<int:capture_id>")
    @login_required
    def plant_detail(capture_id):
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        db = get_db()

        plant = None
        if capture["plant_id"]:
            plant = db.execute("SELECT * FROM plants WHERE id = ?", (capture["plant_id"],)).fetchone()

        is_new_catch = request.args.get("caught") == "1"

        return render_template(
            "detail.html",
            capture=capture,
            plant=plant,
            is_new_catch=is_new_catch
        )

    @app.route("/dex/<int:capture_id>/rename", methods=["POST"])
    @login_required
    def rename_plant(capture_id):
        validate_csrf_token()
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        new_name = request.form.get("new_name", "").strip()[:80]
        if not new_name:
            flash("Plant name cannot be empty.", "error")
            return redirect(url_for("plant_detail", capture_id=capture_id))

        # Re-run match / lookup flow
        db = get_db()
        cur = db.cursor()
        matched, is_match = find_matching_plant(db, new_name)

        if is_match and matched:
            cur.execute("""
                UPDATE captures 
                SET plant_id = ?, custom_plant_name = NULL, status = 'named_by_user',
                    name_source = 'user', details_source = 'local'
                WHERE id = ?
            """, (matched["id"], capture_id))
            db.commit()
            flash(f"Matched with Dex entry: {matched['scientific_name']}", "success")
            return redirect(url_for("plant_detail", capture_id=capture_id))

        # Check Wikipedia
        wiki_data = fetch_plant_details_live(new_name)
        if wiki_data and wiki_data.get("full_desc"):
            session[f"pending_wiki_{capture_id}"] = {"name": new_name, "wiki": wiki_data}
            return redirect(url_for("confirm_wikipedia", capture_id=capture_id))

        custom_id = create_custom_plant(db, new_name)
        cur.execute("""
            UPDATE captures 
            SET plant_id = ?, custom_plant_name = ?, status = 'details_pending',
                name_source = 'user', details_source = 'none'
            WHERE id = ?
        """, (custom_id, new_name, capture_id))
        db.commit()
        enqueue_capture_sync(db, new_name, capture_id)

        flash(f"Renamed to {new_name}. Details will sync when available.", "info")
        return redirect(url_for("plant_detail", capture_id=capture_id))

    @app.route("/dex/<int:capture_id>/retry-sync", methods=["POST"])
    @login_required
    def retry_sync(capture_id):
        validate_csrf_token()
        capture = verify_user_owns_capture(capture_id, session["user_id"])
        plant_name = capture["custom_plant_name"]

        db = get_db()
        if not plant_name and capture["plant_id"]:
            p = db.execute("SELECT scientific_name FROM plants WHERE id = ?", (capture["plant_id"],)).fetchone()
            if p:
                plant_name = p["scientific_name"]

        if plant_name:
            details, src = lookup_and_cache_plant_details(plant_name, db_conn=db)
            if details and details.get("full_desc"):
                cur = db.cursor()
                cur.execute("""
                    UPDATE captures SET status = 'complete', details_source = 'wikipedia', plant_id = ?
                    WHERE id = ?
                """, (details["id"], capture_id))
                db.commit()
                flash("Botanical details loaded and saved!", "success")
            else:
                flash("Still unable to fetch details from Wikipedia. Server may be offline.", "warning")

        return redirect(url_for("plant_detail", capture_id=capture_id))

    @app.route("/dex/<int:capture_id>/gemini-check", methods=["POST"])
    @login_required
    def gemini_double_check(capture_id):
        validate_csrf_token()
        capture = verify_user_owns_capture(capture_id, session["user_id"])

        photo_path = Path(Config.UPLOADS_DIR) / capture["user_photo_path"]
        result = double_check_with_gemini(photo_path)
        return jsonify(result)

    @app.route("/dex/<int:capture_id>/delete", methods=["POST"])
    @login_required
    def delete_capture(capture_id):
        validate_csrf_token()
        verify_user_owns_capture(capture_id, session["user_id"])
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
        db.commit()
        flash("Specimen removed from your Dex.", "info")
        return redirect(url_for("dashboard"))

    # -------------------------------------------------------------
    # Plant Name Autocomplete API
    # -------------------------------------------------------------
    @app.route("/api/plants/search")
    @login_required
    def api_plant_search():
        query = request.args.get("q", "")
        db = get_db()
        results = search_plant_names(db, query, limit=8)
        return jsonify(results)

    # -------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template("500.html", error_title="400 - Bad Request", error_msg=str(e.description or e)), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template("500.html", error_title="403 - Access Denied", error_msg=str(e.description or e)), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def entity_too_large(e):
        return render_template("500.html", error_title="413 - Photo Too Large", error_msg="Uploaded photo exceeds 8 MB limit."), 413

    @app.errorhandler(429)
    def rate_limit_error(e):
        return render_template("429.html", message=str(e.description or e)), 429

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        return render_template("500.html", error_title="500 - Server Error", error_msg="Something went wrong."), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
