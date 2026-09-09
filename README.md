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
