from flask import Flask, render_template, request
import json, os, random

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

with open("data/diseases.json", "r", encoding="utf-8") as f:
    DISEASES = json.load(f)

def calculate_risk(crop, age, moisture, irrigation, humidity, rainfall):
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

    # Demo prediction; replace with trained ML model later.
    crop_data = DISEASES.get(crop, DISEASES["Tomato"])
    disease = crop_data["high"] if level == "HIGH" else crop_data["medium"] if level == "MEDIUM" else "No major disease signal"

    return score, level, disease, reasons, crop_data["advice"]

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    crop = request.form.get("crop", "Tomato")
    age = int(request.form.get("age", 30))
    moisture = int(request.form.get("moisture", 50))
    irrigation = request.form.get("irrigation", "normal")
    humidity = int(request.form.get("humidity", 65))
    rainfall = float(request.form.get("rainfall", 5))

    image_name = None
    image = request.files.get("image")
    if image and image.filename:
        safe_name = os.path.basename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], safe_name))
        image_name = safe_name

    score, level, disease, reasons, advice = calculate_risk(
        crop, age, moisture, irrigation, humidity, rainfall
    )

    timeline = [
        {"day": "Day 1", "status": "Normal", "class": "low"},
        {"day": "Day 3", "status": "Risk increasing", "class": "medium"},
        {"day": "Day 5", "status": "Warning", "class": "medium"},
        {"day": "Today", "status": f"{level.title()} risk", "class": level.lower()},
    ]

    return render_template(
        "result.html",
        crop=crop, score=score, level=level, disease=disease,
        reasons=reasons, advice=advice, timeline=timeline,
        image_name=image_name
    )

if __name__ == "__main__":
    app.run(debug=False)
