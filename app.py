from flask import Flask, render_template, request, redirect, url_for, jsonify
import json, os, sqlite3, urllib.parse, urllib.request
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageStat

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
DB = "croppulse.db"

with open("data/crops.json", encoding="utf-8") as f:
    CROPS = json.load(f)
with open("data/diseases.json", encoding="utf-8") as f:
    DISEASES = json.load(f)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, crop TEXT, disease TEXT, risk INTEGER,
        severity TEXT, confidence TEXT, latitude TEXT, longitude TEXT,
        temperature TEXT, humidity TEXT, rainfall TEXT, soil_moisture TEXT,
        image_name TEXT
    )""")
    con.commit(); con.close()

def get_weather(lat, lon):
    if not lat or not lon:
        return {}
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,soil_moisture_0_to_7cm",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 1, "timezone": "auto"
    })
    try:
        with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?"+params, timeout=8) as r:
            x=json.loads(r.read().decode())
        c=x.get("current",{}); d=x.get("daily",{})
        return {
            "temperature": c.get("temperature_2m"),
            "humidity": c.get("relative_humidity_2m"),
            "rainfall": (d.get("precipitation_sum") or [0])[0],
            "wind_speed": c.get("wind_speed_10m"),
            "soil_moisture": c.get("soil_moisture_0_to_7cm"),
            "tmax": (d.get("temperature_2m_max") or [None])[0],
            "tmin": (d.get("temperature_2m_min") or [None])[0]
        }
    except Exception:
        return {}

def month_name():
    return datetime.now().strftime("%B")

def crop_recommendations(temp, rain, month):
    ranked=[]
    for c in CROPS:
        score=0
        months=c.get("months",[])
        if month in months: score += 40
        lo,hi=c.get("temp_range",[10,40])
        if temp is not None:
            if lo <= temp <= hi: score += 35
            elif abs(temp-lo)<=5 or abs(temp-hi)<=5: score += 15
        rlo,rhi=c.get("rainfall_range",[0,300])
        if rain is not None:
            if rlo <= rain <= rhi: score += 25
            elif abs(rain-rlo)<=20 or abs(rain-rhi)<=20: score += 10
        ranked.append((score,c))
    ranked.sort(key=lambda x:x[0], reverse=True)
    return [{"name":c["name"],"score":s,"reason":c.get("reason","Suitable for current conditions.")} for s,c in ranked]

def image_quality(path):
    try:
        with Image.open(path) as im:
            w,h=im.size
            stat=ImageStat.Stat(im.convert("RGB"))
            brightness=sum(stat.mean)/3
            issues=[]
            if min(w,h)<300: issues.append("Image resolution is low.")
            if brightness<35: issues.append("Image is too dark.")
            if brightness>235: issues.append("Image is overexposed.")
            return {"ok": not issues, "width":w, "height":h, "brightness":round(brightness), "issues":issues}
    except Exception:
        return {"ok":False,"width":0,"height":0,"brightness":0,"issues":["Unsupported or unreadable image."]}

def risk(crop, age, irrigation, humidity, rainfall, temp, soil):
    score=20; reasons=[]
    if humidity is not None:
        if humidity>=80: score+=22; reasons.append("Very high humidity")
        elif humidity>=65: score+=12; reasons.append("Elevated humidity")
    if rainfall is not None:
        if rainfall>=30: score+=18; reasons.append("High recent rainfall")
        elif rainfall>=10: score+=9; reasons.append("Recent rainfall")
    if soil is not None:
        if soil>=0.35: score+=16; reasons.append("High estimated soil moisture")
        elif soil>=0.25: score+=8; reasons.append("Moderate estimated soil moisture")
    if irrigation=="frequent": score+=8; reasons.append("Frequent irrigation")
    if 20<=age<=60: score+=5; reasons.append("Susceptible crop stage")
    if temp is not None and (temp>=35 or temp<=10): score+=8; reasons.append("Temperature stress")
    score=min(95,score)
    level="HIGH" if score>=70 else "MEDIUM" if score>=45 else "LOW"
    data=DISEASES.get(crop,DISEASES.get("Tomato"))
    disease=data["high"] if level=="HIGH" else data["medium"] if level=="MEDIUM" else "No major disease signal"
    return score,level,disease,reasons,data.get("advice",[])

@app.route("/")
def index():
    return render_template("index.html", crops=CROPS, month=month_name())

@app.route("/analyze", methods=["POST"])
def analyze():
    crop=request.form.get("crop","Tomato")
    age=int(request.form.get("age",30) or 30)
    irrigation=request.form.get("irrigation","normal")
    lat=request.form.get("latitude","").strip()
    lon=request.form.get("longitude","").strip()

    weather=get_weather(lat,lon)
    humidity=weather.get("humidity")
    rainfall=weather.get("rainfall")
    temp=weather.get("temperature")
    soil=weather.get("soil_moisture")

    # Manual fallback when location/weather is unavailable
    if humidity is None: humidity=int(request.form.get("humidity",65) or 65)
    if rainfall is None: rainfall=float(request.form.get("rainfall",5) or 5)
    if temp is None: temp=float(request.form.get("temperature",28) or 28)
    if soil is None:
        manual=float(request.form.get("moisture",50) or 50)
        soil=manual/100.0

    image_name=None; quality=None
    image=request.files.get("image")
    if image and image.filename:
        filename=secure_filename(image.filename)
        if filename:
            image_name=filename
            path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
            image.save(path)
            quality=image_quality(path)

    score,level,disease,reasons,advice=risk(crop,age,irrigation,humidity,rainfall,temp,soil)
    recommendations=crop_recommendations(temp,rainfall,month_name())

    # Deliberately do not claim AI confidence until a trained CV model is connected.
    ai_status="AI vision model ready for integration"
    ai_confidence="Pending trained crop-disease model"
    ai_note="This prototype uses field, weather and image-quality signals. It does not diagnose from pixels yet."

    con=db()
    con.execute("""INSERT INTO history
    (created_at,crop,disease,risk,severity,confidence,latitude,longitude,temperature,humidity,rainfall,soil_moisture,image_name)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (datetime.now().strftime("%Y-%m-%d %H:%M"),crop,disease,score,level,ai_confidence,
     lat,lon,str(temp),str(humidity),str(rainfall),str(round(soil*100,1)),image_name))
    con.commit(); con.close()

    return render_template("result.html", crop=crop, score=score, level=level,
        disease=disease,reasons=reasons,advice=advice,image_name=image_name,
        quality=quality,weather=weather,temperature=temp,humidity=humidity,
        rainfall=rainfall,soil_moisture=soil,recommendations=recommendations,
        latitude=lat,longitude=lon,ai_status=ai_status,ai_confidence=ai_confidence,ai_note=ai_note)

@app.route("/history")
def history():
    con=db(); rows=con.execute("SELECT * FROM history ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    return render_template("history.html", rows=rows)

@app.route("/api/crops")
def api_crops():
    return jsonify(CROPS)

init_db()

if __name__=="__main__":
    app.run(debug=True)
