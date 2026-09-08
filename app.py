from flask import Flask, render_template, request
import json
import os
import urllib.request
import urllib.parse

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

with open("data/diseases.json", "r", encoding="utf-8") as f:
    DISEASES = json.load(f)


def get_weather(latitude, longitude):
    """
    Get current weather and recent rainfall using coordinates.
    Returns None if weather service is unavailable.
    """

    if not latitude or not longitude:
        return None

    try:
        params = urllib.parse.urlencode({
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation,"
                "wind_speed_10m"
            ),
            "hourly": "precipitation",
            "forecast_days": 1,
            "timezone": "auto"
        })

        url = "https://api.open-meteo.com/v1/forecast?" + params

        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        current = data.get("current", {})

        temperature = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        precipitation = current.get("precipitation")
        wind_speed = current.get("wind_speed_10m")

        return {
            "temperature": temperature,
            "humidity": humidity,
            "rainfall": precipitation or 0,
            "wind_speed": wind_speed
        }

    except Exception:
        return None


def calculate_risk(
    crop,
    age,
    moisture,
    irrigation,
    humidity,
    rainfall
):
    score = 20
    reasons = []

    if humidity >= 75:
        score += 20
        reasons.append("High humidity")
    elif humidity >= 60:
        score += 10
        reasons.append("Moderate humidity")

    if rainfall >= 20:
        score += 20
        reasons.append("Recent rainfall")
    elif rainfall >= 5:
        score += 10
        reasons.append("Some rainfall")

    if moisture >= 75:
        score += 15
        reasons.append("High soil moisture")
    elif moisture >= 60:
        score += 8
        reasons.append("Moderate soil moisture")

    if irrigation == "frequent":
        score += 10
        reasons.append("Frequent irrigation")

    if 20 <= age <= 60:
        score += 5
        reasons.append("Susceptible crop stage")

    score = min(score, 95)

    if score >= 70:
        level = "HIGH"
    elif score >= 45:
        level = "MEDIUM"
    else:
        level = "LOW"

    crop_data = DISEASES.get(
        crop,
        DISEASES["Tomato"]
    )

    if level == "HIGH":
        disease = crop_data["high"]
    elif level == "MEDIUM":
        disease = crop_data["medium"]
    else:
        disease = "No major disease signal"

    return (
        score,
        level,
        disease,
        reasons,
        crop_data["advice"]
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():

    crop = request.form.get("crop", "Tomato")

    try:
        age = int(request.form.get("age", 30))
    except ValueError:
        age = 30

    try:
        moisture = int(request.form.get("moisture", 50))
    except ValueError:
        moisture = 50

    irrigation = request.form.get(
        "irrigation",
        "normal"
    )

    try:
        humidity = int(
            request.form.get("humidity", 65)
        )
    except ValueError:
        humidity = 65

    try:
        rainfall = float(
            request.form.get("rainfall", 5)
        )
    except ValueError:
        rainfall = 5

    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    # Get automatic weather data
    weather = get_weather(
        latitude,
        longitude
    )

    # If automatic weather is available,
    # use it for the risk calculation.
    if weather:

        if weather["humidity"] is not None:
            humidity = int(
                round(weather["humidity"])
            )

        if weather["rainfall"] is not None:
            rainfall = float(
                weather["rainfall"]
            )

    # Photo upload
    image_name = None

    image = request.files.get("image")

   if image and image.filename:

    safe_name = os.path.basename(image.filename)

    image.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            safe_name
        )
    )

    image_name = safe_name

    # Calculate risk
    score, level, disease, reasons, advice = calculate_risk(
        crop,
        age,
        moisture,
        irrigation,
        humidity,
        rainfall
    )

    timeline = [
        {
            "day": "Day 1",
            "status": "Normal",
            "class": "low"
        },
        {
            "day": "Day 3",
            "status": "Risk increasing",
            "class": "medium"
        },
        {
            "day": "Day 5",
            "status": "Warning",
            "class": "medium"
        },
        {
            "day": "Today",
            "status": f"{level.title()} risk",
            "class": level.lower()
        }
    ]

    return render_template(
        "result.html",
        crop=crop,
        score=score,
        level=level,
        disease=disease,
        reasons=reasons,
        advice=advice,
        timeline=timeline,
        image_name=image_name,
        latitude=latitude,
        longitude=longitude,
        weather=weather,
        temperature=(
            weather["temperature"]
            if weather else None
        ),
        humidity=humidity,
        rainfall=rainfall,
        wind_speed=(
            weather["wind_speed"]
            if weather else None
        )
    )


if __name__ == "__main__":
    app.run(debug=True)
