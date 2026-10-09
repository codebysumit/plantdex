"""
Optional Gemini Flash Vision Double-Check Helper
- Uses lightweight direct REST API via requests (zero heavy SDKs to preserve 512 MB RAM)
- Resizes image before transmission to conserve bandwidth
- Strict JSON response contract
- Validates suggestion against official AIY botanical labelmap
- Graceful degradation if offline, rate-limited, or unconfigured
"""
import base64
import json
import logging
from io import BytesIO
from PIL import Image
import requests
from config import Config
from model_engine import get_labels

logger = logging.getLogger("plantdex.gemini")


def double_check_with_gemini(pil_or_image_path):
    """
    Invokes Gemini Flash vision to provide a second opinion on a plant photo.
    Returns dict:
    {
        "status": "success" | "error" | "unconfigured",
        "scientific_name": str,
        "common_name": str,
        "confidence": float,
        "reasoning": str,
        "is_official_dex_label": bool,
        "error_message": str or None
    }
    """
    if not Config.GEMINI_API_KEY:
        return {
            "status": "unconfigured",
            "error_message": "GEMINI_API_KEY is not set. Local AI model is active.",
            "is_official_dex_label": False
        }

    try:
        # Load and resize image to 512px max dimension
        if isinstance(pil_or_image_path, Image.Image):
            img = pil_or_image_path
        else:
            img = Image.open(pil_or_image_path)

        img = img.convert("RGB")
        img.thumbnail((512, 512), Image.Resampling.BILINEAR)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Official Gemini REST generateContent endpoint
        model_name = Config.GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={Config.GEMINI_API_KEY}"

        prompt = (
            "Analyze this botanical photo. You are a senior botanical taxonomist. "
            "Identify the plant. Return ONLY valid JSON with this exact schema: "
            "{\"scientific_name\": \"Genus species\", \"common_name\": \"Common Name\", "
            "\"confidence\": 0.85, \"reasoning\": \"Brief 1-sentence botanical traits observed\"}. "
            "Do NOT include markdown formatting or backticks."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }

        resp = requests.post(url, json=payload, timeout=12.0)

        if resp.status_code == 429:
            return {
                "status": "error",
                "error_message": "Gemini API rate limit reached. Please try again shortly.",
                "is_official_dex_label": False
            }

        if resp.status_code != 200:
            logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
            return {
                "status": "error",
                "error_message": f"Gemini API returned HTTP {resp.status_code}",
                "is_official_dex_label": False
            }

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {
                "status": "error",
                "error_message": "No candidates returned by Gemini vision model.",
                "is_official_dex_label": False
            }

        text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        # Parse JSON
        parsed = json.loads(text_content.strip())

        sci_name = parsed.get("scientific_name", "Unknown Flora").strip()
        common_name = parsed.get("common_name", "").strip()
        conf = float(parsed.get("confidence", 0.70))
        reasoning = parsed.get("reasoning", "").strip()

        # Check against AIY official labels
        labels = get_labels()
        is_official = any(l.lower() == sci_name.lower() for l in labels)

        return {
            "status": "success",
            "scientific_name": sci_name,
            "common_name": common_name,
            "confidence": conf,
            "reasoning": reasoning,
            "is_official_dex_label": is_official,
            "error_message": None
        }

    except Exception as e:
        logger.error(f"Gemini double check failed: {e}")
        return {
            "status": "error",
            "error_message": f"Gemini check failed: {str(e)}",
            "is_official_dex_label": False
        }
