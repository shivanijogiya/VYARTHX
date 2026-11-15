# Bundled model: MobileNetV2 (ONNX, ImageNet)

* File: `mobilenetv2-12.onnx` (ONNX Model Zoo), labels `imagenet_classes.txt`. Licence: Apache-2.0.
* It is a **generic ImageNet classifier. It was NOT trained or fine-tuned on waste images** and VYARTHX does not claim otherwise.
* Use in VYARTHX: its top-5 ImageNet labels are mapped by a hand-written table to waste-KB items, then merged with keyword matches from the user's text. Low confidence or conflicts trigger a clarification request; hazardous categories always require human-review guidance.
* Expected limits: unfamiliar objects, cluttered scenes and soiled items are often mis-ranked. Treat results as assistance, not ground truth.
* To train a waste-specific model see `ml/training/README.md`.
