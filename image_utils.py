"""
Image Processing Utilities for PlantDex
- Sanitization & EXIF/GPS stripping for user privacy
- Orientation correction via EXIF transpose
- Pillow format verification
- Center square cropping
- Resizing to ~512px WebP/JPEG
- Safe randomized UUID file naming
"""
import uuid
from io import BytesIO
from pathlib import Path
from config import Config

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


def process_user_photo(file_storage_or_bytes, filename=None):
    """
    Validates, strips metadata, square crops, and saves a user photo.
    Returns relative filename under uploads/ (e.g. 'c4a18f2e-....webp').
    Raises ValueError on invalid image.
    """
    try:
        if hasattr(file_storage_or_bytes, "read"):
            data = file_storage_or_bytes.read()
        else:
            data = file_storage_or_bytes

        if len(data) > Config.MAX_CONTENT_LENGTH:
            raise ValueError("File exceeds maximum allowed size (8 MB).")

        img = Image.open(BytesIO(data))
        img.verify()  # Verify integrity

        # Re-open after verify (PIL requirement)
        img = Image.open(BytesIO(data))

        # Auto-correct phone orientation
        img = ImageOps.exif_transpose(img)

        # Ensure RGB color space
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        # Center square crop
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        cropped = img.crop((left, top, right, bottom))

        # Resize to 512x512
        final_img = cropped.resize((512, 512), Image.Resampling.LANCZOS)

        # Strip all EXIF / GPS: creating a clean image without copying metadata
        clean_img = Image.new("RGB", final_img.size)
        clean_img.paste(final_img)

        # Generate unique filename
        unique_name = f"{uuid.uuid4().hex}.webp"
        save_path = Path(Config.UPLOADS_DIR) / unique_name

        # Save as optimized WebP
        try:
            clean_img.save(save_path, "WEBP", quality=82, method=6)
        except Exception:
            # Fallback to JPEG if WebP encoder unavailable
            unique_name = f"{uuid.uuid4().hex}.jpg"
            save_path = Path(Config.UPLOADS_DIR) / unique_name
            clean_img.save(save_path, "JPEG", quality=85, optimize=True)

        return unique_name

    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")


def get_image_for_model(photo_path_or_bytes):
    """
    Opens an image, corrects orientation, converts to RGB, and returns PIL Image.
    """
    if isinstance(photo_path_or_bytes, (str, Path)):
        img = Image.open(photo_path_or_bytes)
    else:
        img = Image.open(BytesIO(photo_path_or_bytes))

    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")
