"""
AIY Plants TFLite Inference Engine for PlantDex
- CPU-only execution optimized for small servers (512 MB RAM)
- Loads model once at startup, guarded by a threading.Lock
- 3-view multi-crop inference (full, center-crop, mirrored center-crop)
- Automatic background label suppression
- Supports ai-edge-litert, tflite-runtime, and mock fallback
"""
import os
import time
import logging
import threading
from pathlib import Path
from config import Config

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

logger = logging.getLogger("plantdex.model")

_model_lock = threading.Lock()
_interpreter = None
_input_details = None
_output_details = None
_labels = []
_bg_indices = set()
_model_load_time_ms = 0.0


def _load_labels():
    """Loads CSV labelmap into memory."""
    global _labels, _bg_indices
    labels_file = Path(Config.LABELS_PATH)
    if not labels_file.exists():
        logger.warning(f"Labelmap not found at {labels_file}")
        return []

    labels = []
    bg_indices = set()
    with open(labels_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for idx, line in enumerate(lines[1:]):  # skip header
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                name = parts[1].strip()
                labels.append(name)
                if name.lower() == "background":
                    bg_indices.add(len(labels) - 1)

    _labels = labels
    _bg_indices = bg_indices
    logger.info(f"Loaded {len(_labels)} botanical labels (Background index: {_bg_indices})")
    return _labels


def get_labels():
    if not _labels:
        _load_labels()
    return _labels


def initialize_model(model_path=None):
    """
    Initializes TFLite interpreter once at application startup.
    Returns True if successfully initialized, False otherwise.
    """
    global _interpreter, _input_details, _output_details, _model_load_time_ms
    start_t = time.time()
    _load_labels()

    path = model_path or Config.MODEL_PATH
    if not os.path.exists(path):
        logger.warning(f"TFLite model file not found at {path}. Model engine will run in mock/test mode.")
        _interpreter = None
        return False

    try:
        # 1. Try Google's newest ai-edge-litert
        try:
            from ai_edge_litert.interpreter import Interpreter
            logger.info("Using ai-edge-litert runtime.")
        except ImportError:
            # 2. Try standard tflite-runtime
            try:
                from tflite_runtime.interpreter import Interpreter
                logger.info("Using tflite-runtime.")
            except ImportError:
                # 3. Try tensorflow.lite
                from tensorflow.lite import Interpreter
                logger.info("Using tensorflow.lite runtime.")

        with _model_lock:
            _interpreter = Interpreter(model_path=str(path))
            _interpreter.allocate_tensors()
            _input_details = _interpreter.get_input_details()[0]
            _output_details = _interpreter.get_output_details()[0]

        _model_load_time_ms = (time.time() - start_t) * 1000.0
        logger.info(
            f"AIY Plants model initialized in {_model_load_time_ms:.1f}ms. "
            f"Input shape: {_input_details['shape']}, Output shape: {_output_details['shape']}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize TFLite interpreter: {e}")
        _interpreter = None
        return False


def get_model_status():
    """Returns runtime diagnostics for health check and admin view."""
    return {
        "loaded": _interpreter is not None,
        "labels_count": len(_labels),
        "load_time_ms": round(_model_load_time_ms, 2),
        "model_path": Config.MODEL_PATH,
    }


def _run_single_view(pil_image):
    """Runs a single 224x224 RGB image through the TFLite interpreter."""
    global _interpreter, _input_details, _output_details
    h, w = _input_details["shape"][1], _input_details["shape"][2]
    resized = pil_image.resize((w, h), Image.Resampling.BILINEAR)
    x = np.expand_dims(np.array(resized), 0)

    if _input_details["dtype"] == np.uint8:
        x = x.astype(np.uint8)
    else:
        x = x.astype(np.float32) / 255.0

    with _model_lock:
        _interpreter.set_tensor(_input_details["index"], x)
        _interpreter.invoke()
        y = _interpreter.get_tensor(_output_details["index"])[0].astype(np.float32)

    if _output_details["dtype"] == np.uint8:
        scale, zero = _output_details.get("quantization", (0.0, 0))
        y = (y - zero) * scale if scale else y / 255.0

    return y


def classify_image(pil_or_path, top_k=3):
    """
    Multi-crop classification (full image, center crop, mirrored center crop).
    Averages probabilities, zeroes out 'background', and returns top-k predictions:
    [ (scientific_name, confidence_float), ... ]
    """
    labels = get_labels()
    if not labels:
        return [("Unknown Botanical Species", 0.10)]

    # Open and orient image
    if isinstance(pil_or_path, (str, Path)):
        img = Image.open(pil_or_path)
    else:
        img = pil_or_path

    img = ImageOps.exif_transpose(img).convert("RGB")

    # If interpreter is not loaded (e.g. testing without TFLite binaries), provide deterministic fallback
    if _interpreter is None:
        logger.debug("TFLite interpreter not active; returning baseline prediction.")
        # Return first non-background label with low confidence
        first_label = labels[1] if len(labels) > 1 else "Plantae"
        return [(first_label, 0.42), (labels[2] if len(labels) > 2 else "Flora", 0.28)]

    # Multi-view crops
    w, h = img.size
    s = min(w, h)
    center = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    mirrored = ImageOps.mirror(center)

    views = [img, center, mirrored]
    probs_list = [_run_single_view(v) for v in views]
    probs = np.mean(probs_list, axis=0)

    # Suppress background class
    for bg_idx in _bg_indices:
        if bg_idx < len(probs):
            probs[bg_idx] = 0.0

    # Ensure softmax sum / normalization
    total = np.sum(probs)
    if total > 0:
        probs = probs / total

    n = min(len(probs), len(labels))
    top_indices = np.argsort(probs[:n])[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append((labels[idx], float(probs[idx])))

    return results


def evaluate_confidence(confidence):
    """
    Applies official PlantDex confidence tiers:
    - >= 0.50 -> 'CAUGHT'
    - 0.25 to 0.50 -> 'MAYBE'
    - < 0.25 -> 'NOT_SURE'
    """
    if confidence >= Config.CONFIDENCE_CAUGHT:
        return "CAUGHT"
    elif confidence >= Config.CONFIDENCE_MAYBE:
        return "MAYBE"
    else:
        return "NOT_SURE"
