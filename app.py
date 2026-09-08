from flask import Flask, render_template, request, redirect, url_for
import json, os, sqlite3, urllib.request, urllib.parse
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DB = "croppulse.db"

with open("data/crops.json", "r", encoding="utf-8") as f:
    CROPS = json.load(f)
with open("data/diseases.json", "r", encoding="utf-8") as f:
    DISEASES = json.load(f)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, crop TEXT, disease TEXT, level TEXT,
        score INTEGER, confidence TEXT, latitude REAL, longitude REAL
    )""")
    con.commit()
    con.close()

init_db()

def get_weather(lat, lon):
    try:
        params = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,soil_moisture_0_to_7cm",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": 1, "timezone": "auto"
        })
        with urllib.request.urlopen(
            "https://api.open-meteo.com/v1/forecast?" + params, timeout=10
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
        c, d = data.get("current", {}), data.get("daily", {})
        soil = c.get("soil_moisture_0_to_7cm")
        return {
            "temperature": c.get("temperature_2m"),
            "humidity": c.get("relative_humidity_2m"),
            "rainfall": c.get("precipitation") or 0,
            "daily_rainfall": (d.get("precipitation_sum") or [0])[0] or 0,
            "wind_speed": c.get("wind_speed_10m"),
            "soil_moisture": soil,
            "soil_moisture_note": "Estimated model value"
        }
    except Exception as e:
        print("Weather error:", e)
        return None

def crop_recommendations(month, temp=None, rain=None):
    scored = []
    for crop in CROPS:
        score = 0
        if month in crop["months"]:
            score += 50
        if temp is not None and crop["min_temp"] <= temp <= crop["max_temp"]:
            score += 30
        if rain is not None and crop["min_rain"] <= rain <= crop["max_rain"]:
            score += 20
        scored.append((score, crop))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))
    return [c for s, c in scored[:8] if s > 0]

def image_quality(path):
    try:
        from PIL import Image, ImageStat
        im = Image.open(path).convert("RGB")
        w, h = im.size
        stat = ImageStat.Stat(im)
        brightness = sum(stat.mean) / 3
        if w < 300 or h < 300:
            return False, "Photo resolution is low. Please upload a clearer image."
        if brightness < 35 or brightness > 235:
            return False, "Photo lighting is unclear. Try a well-lit crop photo."
        return True, "Photo quality looks usable for analysis."
    except Exception:
        return True, "Photo received."

def calculate_risk(crop, age, moisture, irrigation, humidity, rainfall, temp=None):
    score, reasons = 20, []
    if humidity is not None:
        if humidity >= 75: score += 20; reasons.append("High humidity")
        elif humidity >= 60: score += 10; reasons.append("Moderate humidity")
    if rainfall is not None:
        if rainfall >= 20: score += 20; reasons.append("High recent rainfall")
        elif rainfall >= 5: score += 10; reasons.append("Recent rainfall")
    if moisture is not None:
        if moisture >= 75: score += 15; reasons.append("High soil moisture")
        elif moisture >= 60: score += 8; reasons.append("Moderate soil moisture")
    if irrigation == "frequent":
        score += 10; reasons.append("Frequent irrigation")
    if 20 <= age <= 60:
        score += 5; reasons.append("Susceptible growth stage")
    if temp is not None and (temp < 12 or temp > 35):
        score += 8; reasons.append("Temperature stress signal")
    score = min(score, 95)
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW"
    data = DISEASES.get(crop, DISEASES["Tomato"])
    disease = data["high"] if level == "HIGH" else data["medium"] if level == "MEDIUM" else "No major disease signal"
    severity = "Severe" if score >= 75 else "Moderate" if score >= 50 else "Mild"
    return score, level, disease, severity, reasons, data["advice"]

@app.route("/")
def index():
    month = datetime.now().month
    return render_template("index.html", crops=CROPS, recommendations=crop_recommendations(month))

@app.route("/analyze", methods=["POST"])
def analyze():
    crop = request.form.get("crop", "Tomato")
    age = int(request.form.get("age", 30) or 30)
    manual_moisture = float(request.form.get("moisture", 50) or 50)
    irrigation = request.form.get("irrigation", "normal")
    humidity = float(request.form.get("humidity", 65) or 65)
    rainfall = float(request.form.get("rainfall", 5) or 5)
    lat = request.form.get("latitude") or None
    lon = request.form.get("longitude") or None

    weather = None
    if lat and lon:
        try:
            weather = get_weather(float(lat), float(lon))
        except ValueError:
            weather = None

    if weather:
        humidity = weather["humidity"] if weather["humidity"] is not None else humidity
        rainfall = weather["daily_rainfall"]
        soil = weather["soil_moisture"]
        moisture = round(soil * 100, 1) if soil is not None else manual_moisture
    else:
        moisture = manual_moisture

    image_name, quality_ok, quality_message = None, True, "No photo uploaded."
    image = request.files.get("image")
    if image and image.filename:
        name = secure_filename(image.filename)
        if name:
            path = os.path.join(app.config["UPLOAD_FOLDER"], name)
            image.save(path)
            image_name = name
            quality_ok, quality_message = image_quality(path)

    temp = weather["temperature"] if weather else None
    score, level, disease, severity, reasons, advice = calculate_risk(
        crop, age, moisture, irrigation, humidity, rainfall, temp
    )

    # IMPORTANT: this is contextual risk scoring, not a trained image-disease model.
    ai_status = "AI model not connected yet"
    ai_confidence = "Pending trained model"
    if image_name and not quality_ok:
        ai_status = "Image quality check failed"
    elif image_name:
        ai_status = "Photo accepted for future CV model"

    con = db()
    con.execute("""INSERT INTO history
        (created_at,crop,disease,level,score,confidence,latitude,longitude)
        VALUES (?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(timespec="seconds"), crop, disease, level,
         score, ai_confidence, lat, lon))
    con.commit()
    con.close()

    recs = crop_recommendations(datetime.now().month, temp, rainfall)
    return render_template("result.html", crop=crop, score=score, level=level,
        disease=disease, severity=severity, reasons=reasons, advice=advice,
        weather=weather, moisture=moisture, image_name=image_name,
        quality_ok=quality_ok, quality_message=quality_message,
        ai_status=ai_status, ai_confidence=ai_confidence,
        latitude=lat, longitude=lon, recommendations=recs)

@app.route("/history")
def history():
    con = db()
    rows = con.execute("SELECT * FROM history ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    return render_template("history.html", rows=rows)

if __name__ == "__main__":
    app.run(debug=True)
