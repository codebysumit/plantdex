"""
Model Download & Verification Utility for PlantDex
Downloads the Google AIY Plants V1 TFLite quantized classifier.
Source: Google AIY Projects / TensorFlow Hub / Kaggle Models
License: Apache License 2.0
"""
import os
import sys
import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "plants_v1.tflite"

# TensorFlow Hub direct download URL for AIY Plants V1 TFLite model
MODEL_URLS = [
    "https://tfhub.dev/google/lite-model/aiy/vision/classifier/plants_V1/3?lite-format=tflite",
    "https://storage.googleapis.com/tfhub-lite-models/google/aiy/vision/classifier/plants_V1/3.tflite",
]


def download_model(target_path=MODEL_PATH, force=False):
    target_path = Path(target_path)
    if target_path.exists() and not force:
        size_mb = target_path.stat().st_size / (1024 * 1024)
        print(f"Model already exists at {target_path} ({size_mb:.2f} MB). Skipping download.")
        return True

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")

    print("Downloading Google AIY Plants V1 classifier (~3.7 MB)...")
    success = False
    for url in MODEL_URLS:
        try:
            print(f"Trying download from: {url}")
            headers = {"User-Agent": "PlantDexModelDownloader/1.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "wb") as f:
                while chunk := resp.read(64 * 1024):
                    f.write(chunk)
            if temp_path.stat().st_size > 100_000:
                temp_path.replace(target_path)
                size_mb = target_path.stat().st_size / (1024 * 1024)
                print(f"Successfully downloaded model to {target_path} ({size_mb:.2f} MB).")
                success = True
                break
        except Exception as e:
            print(f"Download failed from {url}: {e}")
            if temp_path.exists():
                temp_path.unlink()

    return success


if __name__ == "__main__":
    ok = download_model()
    sys.exit(0 if ok else 1)
