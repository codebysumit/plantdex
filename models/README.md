# Google AIY Plants Classifier V1

## Overview
- **Name**: AIY Vision Classifier Plants V1
- **Developer**: Google / AIY Projects
- **Format**: TensorFlow Lite (`.tflite`), quantized int8 / uint8 or float32
- **Model Size**: ~3.7 MB (extremely lightweight, ideal for 512 MB RAM CPU instances)
- **Input Specification**: `[1, 224, 224, 3]` RGB image
- **Output Specification**: `[1, 2102]` softmax probabilities across 2,101 botanical classes + 1 background class
- **License**: Apache License 2.0 (Open Source)
- **Source**: [TensorFlow Hub](https://tfhub.dev/google/lite-model/aiy/vision/classifier/plants_V1/3) / [Kaggle Models](https://www.kaggle.com/models/google/aiy/tfLite/vision-classifier-plants-v1)

## Automatic Download
When deploying on Render or running locally, `models/download_model.py` downloads `plants_v1.tflite` automatically:
```bash
python models/download_model.py
```
If the model file is not present, PlantDex will attempt to download it on startup or operate in a robust fallback mode for unit testing.
