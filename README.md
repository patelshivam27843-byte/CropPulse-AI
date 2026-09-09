# CropPulse AI — Final GitHub Replacement Package

Farmer-friendly Flask prototype for SIH 26131.

## Included
- Premium green agricultural homepage
- Natural Indian farmer field imagery + India map + crop photo ribbon
- GPS location capture
- Location-based weather: temperature, humidity, rainfall, wind
- Estimated soil moisture
- Automatic estimated crop age
- Automatic irrigation suggestion
- Automatic hidden fallback temperature/humidity values
- Crop search and crop database
- Season/weather-based crop recommendations
- Plant photo upload and photo-quality check
- Hindi AI Fasal Doctor result focused on the **possible crop disease only**
- Hindi voice playback with a working Stop button
- AI किसान साथी chatbot with field context
- Farmer history
- Hindi/English language toggle hook
- Firebase Phone OTP, Email/Password and Google authentication UI
- Responsive mobile layout

## Important setup
### Firebase real login
1. Create a Firebase Web App.
2. Enable Phone, Email/Password and Google sign-in providers.
3. Add your Render domain to Firebase authorized domains.
4. Put the Firebase Web App config in `static/firebase-config.js`.
5. Deploy to Render.

Do not put a Firebase service-account private key in the frontend config.

### Real disease AI model
The UI is ready for a real computer-vision disease model, but this ZIP does **not** invent a trained model or fake confidence. Add your validated model/inference code under `models/` and connect it inside `/analyze` before claiming photo-based disease detection.

The current disease text is produced from the crop + field/weather context. It is not a substitute for a trained image classifier.

## Weather / soil note
Soil moisture is an estimate/model value when a field sensor is not available. Crop age is also an estimate unless the farmer provides an actual sowing date.

## Image credits
Homepage image sources and licenses are listed in `static/assets/README.md`.

## Real AI crop-disease diagnosis
The photo diagnosis uses Google's Gemini multimodal API when `GEMINI_API_KEY` is configured in Render. The server sends the uploaded crop image plus crop/weather context and asks the model to return a structured disease result. It does not use the old context-only disease selector for the photo result.

### Render environment variables
Set:
- `GEMINI_API_KEY` = your Google AI Studio API key
- `GEMINI_MODEL` = `gemini-2.5-flash` (optional)

Without `GEMINI_API_KEY`, the app will not pretend that a fixed disease answer came from AI; it will tell the farmer that AI photo diagnosis is unavailable.

Google's Gemini API supports image inputs and structured JSON responses. See the official docs: https://ai.google.dev/gemini-api/docs/image-understanding and https://ai.google.dev/api/generate-content


## Authentication
Login/OTP/Google authentication has been intentionally removed. The portal works without an account.

## Real photo disease AI
The uploaded crop photo is sent to the OpenAI Responses API when `OPENAI_API_KEY` is configured in Render. The model analyzes the actual image; there is no fixed disease response and no photo-quality gate. If the visual evidence is insufficient, the AI says that instead of inventing a disease.

Render environment variables:
- `OPENAI_API_KEY` = your OpenAI API key
- `OPENAI_VISION_MODEL` = `gpt-5.6-luna` (optional; default)

Never put the API key in GitHub. The analysis result page uses a real Indian farmer spreading fertilizer image from Wikimedia Commons, CC BY-SA 2.0: https://commons.wikimedia.org/wiki/File:An_Indian_farmer_spreading_fertilizer_over_a_crop.jpg
