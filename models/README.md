# Crop-disease vision model

The current Flask prototype keeps the AI disease-result UI separate from the weather/risk engine.
To connect a real trained computer-vision model, add the model and inference code here and call it from `/analyze`.

Do not display a confidence score unless the model actually returns a calibrated/validated confidence.
Do not treat weather/risk heuristics as image-based disease detection.
