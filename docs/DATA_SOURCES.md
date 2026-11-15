# Data sources & honesty

See `data/sources/registry.json` (also shown in-app under **Data & Honesty**).

* **Real:** Chennai locality *names*, OpenStreetMap tiles, the bundled ImageNet MobileNetV2 model (Apache-2.0).
* **Not retrieved:** CPCB, data.gov.in, GCC, TNPCB and TrashNet/TACO were unreachable from the build environment. No numbers from them are shown.
* **Simulated (labelled):** ward populations/history, facility placements and capacities, dumpsite capacities, fleet, users, handovers, complaints. Locality centroids are approximate.
* **Estimates (labelled):** CO₂e (illustrative placeholder factors), compost yield, biogas, fuel.
* **Trained:** only the GradientBoosting ward forecaster, on simulated history. The image model is generic ImageNet, **not** waste-trained or validated on Indian waste.
* **Not connected:** municipal systems, vehicle GPS, weighing scales, recycler confirmation APIs, IRCTC/Indian Railways (reward is "Proposed Indian Railways / IRCTC Partnership — Simulation Only").
