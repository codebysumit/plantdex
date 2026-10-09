"""
Authentication, Security & Access Control for PlantDex
Features:
- Werkzeug password hashing (never plaintext)
- Session protection and @login_required decorator
- Built-in lightweight CSRF protection (zero heavy external deps)
- Sliding-window in-memory Rate Limiting for auth & uploads
- Strict User Isolation enforcement
"""
import secrets
import time
from collections import defaultdict
from functools import wraps
from flask import session, request, redirect, url_for, flash, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from config import Config

# In-memory sliding window rate limiter: { (action, ip): [timestamp, timestamp, ...] }
_rate_limits = defaultdict(list)


def check_rate_limit(action, limit, window_seconds=60):
    """
    Returns True if allowed, False if exceeded.
    Uses client remote address and action key.
    """
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "127.0.0.1"
    ip = ip.split(",")[0].strip()
    now = time.time()
    key = (action, ip)

    # Prune old timestamps
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window_seconds]

    if len(_rate_limits[key]) >= limit:
        return False

    _rate_limits[key].append(now)
    return True


def generate_csrf_token():
    """Generates or retrieves CSRF token stored in user session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf_token():
    """Validates submitted CSRF token matches session."""
    token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
    session_token = session.get("_csrf_token")
    if not token or not session_token or not secrets.compare_digest(token, session_token):
        abort(400, description="Invalid or missing CSRF security token.")


def login_required(view):
    """Decorator ensuring route is accessed only by logged-in users."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please sign in to access your PlantDex collection.", "info")
            return redirect(url_for("auth_login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def verify_user_owns_capture(capture_id, user_id):
    """
    Enforces user isolation: checks that capture belongs to the specified user.
    Returns capture dict if authorized, aborts 403 or 404 otherwise.
    """
    db = get_db()
    capture = db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
    if not capture:
        abort(404, description="Capture not found.")
    if capture["user_id"] != user_id:
        abort(403, description="Access denied. You do not own this capture.")
    return dict(capture)


def register_user(username, password):
    """
    Creates a new user account.
    Returns (user_id, error_message).
    """
    username = username.strip() if username else ""
    if not username or len(username) < 3 or len(username) > 30:
        return None, "Username must be between 3 and 30 characters."
    if not password or len(password) < 6:
        return None, "Password must be at least 6 characters long."

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if existing:
        return None, "That username is already taken. Please choose another."

    pwd_hash = generate_password_hash(password)
    cur = db.cursor()
    cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pwd_hash))
    db.commit()
    return cur.lastrowid, None


def authenticate_user(username, password):
    """
    Verifies user credentials.
    Returns (user_dict, error_message).
    """
    username = username.strip() if username else ""
    if not username or not password:
        return None, "Please provide both username and password."

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return None, "Invalid username or password."

    return dict(user), None
