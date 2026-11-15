# Training a waste-specific classifier (not done in this build)

No waste model was trained for this submission. To do so:
1. Obtain TrashNet / TACO (check licences) and place images under `data/datasets/<class>/`.
2. Fine-tune a MobileNetV2 head (PyTorch/TF), export to ONNX with the same 224x224 preprocessing used in `backend/app/services/vision.py`.
3. Replace `ml/models/mobilenetv2-12.onnx`, supply a class list and update the label→KB mapping in `vision.py`.
4. Report held-out accuracy honestly in `ml/models/MODEL_CARD.md`.

The only model *trained* in VYARTHX is the ward-level waste-generation forecaster (scikit-learn GradientBoosting) in `backend/app/services/forecast.py`; it is trained on SIMULATED history at start-up and reports its holdout error on that simulated data.
