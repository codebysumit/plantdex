"""
PlantDex Configuration Module
Handles environment variables, storage paths for Render (persistent disk vs ephemeral),
and resource limits for small CPU instances (512 MB RAM).
"""
import os
from pathlib import Path

# Load local .env if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# Persistent Storage Path (Support Render disk mount e.g. /var/data or local data/)
# When deploying to Render with a persistent disk, set DATA_DIR=/var/data/plantdex
DATA_DIR_PATH = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
DATA_DIR = Path(DATA_DIR_PATH)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Uploads directory
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Thumbnails directory for reference images
THUMBNAILS_DIR = BASE_DIR / "static" / "thumbnails"
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

# Models directory
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    # Flask Security
    SECRET_KEY = os.getenv("SECRET_KEY", "plantdex-secret-key-replace-in-production-touch-grass-2026")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("RENDER", "").lower() == "true" or os.getenv("FLASK_ENV") == "production"

    # SQLite Database
    DB_PATH = str(DATA_DIR / "plantdex.db")

    # Storage Paths
    DATA_DIR = str(DATA_DIR)
    UPLOADS_DIR = str(UPLOADS_DIR)
    THUMBNAILS_DIR = str(THUMBNAILS_DIR)

    # Machine Learning / TFLite Configuration
    MODEL_PATH = os.getenv("MODEL_PATH", str(MODELS_DIR / "plants_v1.tflite"))
    LABELS_PATH = os.getenv("LABELS_PATH", str(BASE_DIR / "data" / "aiy_plants_V1_labelmap.csv"))
    SEED_DATA_PATH = str(BASE_DIR / "data" / "plants_seed.json")

    # Plant Identification Confidence Thresholds
    CONFIDENCE_CAUGHT = float(os.getenv("CONFIDENCE_CAUGHT", "0.50"))  # >= 50% = Caught
    CONFIDENCE_MAYBE = float(os.getenv("CONFIDENCE_MAYBE", "0.25"))    # 25% - 50% = Maybe top 3 choices
    # < 25% = Not Sure (Triggers Unknown / User Named Plant workflow)

    # Optional Google Gemini Vision
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Rate Limiting & Upload constraints
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max upload
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    RATE_LIMIT_LOGIN_MAX = int(os.getenv("RATE_LIMIT_LOGIN_MAX", "10"))  # 10 attempts per minute
    RATE_LIMIT_SCAN_MAX = int(os.getenv("RATE_LIMIT_SCAN_MAX", "30"))    # 30 scans per minute

    # HTTP Client (Polite scraping)
    USER_AGENT = os.getenv(
        "USER_AGENT",
        "PlantDexApp/1.0 (Hacktoberfest Touch Grass Challenge; https://github.com/example/plantdex)"
    )

    # Render Environment Detection
    IS_RENDER = os.getenv("RENDER", "").lower() == "true"
