# CropPulse AI — GitHub Replacement Package

This package is prepared to replace the current CropPulse AI Flask website files.

## Included
- Premium farmer-friendly homepage inspired by the provided reference style
- Farmer/Expert login page UI
- GPS location detection
- Location-based Open-Meteo weather
- Temperature, humidity, rainfall and wind
- Estimated soil moisture
- Automatic crop-age estimate (clearly marked estimated)
- Automatic irrigation suggestion (clearly marked estimated)
- Automatic fallback temperature/humidity when live weather is unavailable
- Crop search and crop database
- Season/weather-based crop recommendations
- Crop photo upload + basic photo quality check
- Field risk assessment
- AI-ready disease/pest detection architecture (trained vision model still required for pixel-level diagnosis)
- Hindi AI Crop Doctor result portal
- Hindi text-to-speech result reading
- AI किसान साथी chatbot connected to field context
- Chatbot voice read-aloud button on result page
- Analysis history with SQLite

## GitHub replacement
Upload/replace these files in the repository root:
- app.py
- requirements.txt
- README.md
- data/crops.json
- data/diseases.json
- templates/index.html
- templates/login.html
- templates/result.html
- templates/history.html
- static/style.css
- static/uploads/.gitkeep

Do not upload the generated `croppulse.db` or Python cache folders.

## Render
After committing the replacement files to the `main` branch, Render should auto-deploy if Auto-Deploy is enabled.
Start command:
`gunicorn app:app`

## Important
The current prototype does not claim that the uploaded photo itself has been diagnosed by a trained computer-vision model. A validated crop-disease/pest model must be connected before showing real AI disease confidence.
