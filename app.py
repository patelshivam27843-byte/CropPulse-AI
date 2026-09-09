from flask import Flask, render_template, request, jsonify
import json, os, sqlite3, urllib.parse, urllib.request
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageStat
from ai_vision import analyze_crop_image

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DB = 'croppulse.db'

with open('data/crops.json', encoding='utf-8') as f:
    CROPS = json.load(f)
with open('data/diseases.json', encoding='utf-8') as f:
    DISEASES = json.load(f)

MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, crop TEXT, disease TEXT,
        risk INTEGER, severity TEXT, confidence TEXT, latitude TEXT, longitude TEXT,
        temperature TEXT, humidity TEXT, rainfall TEXT, soil_moisture TEXT, image_name TEXT)''')
    con.commit(); con.close()


def get_weather(lat, lon):
    if not lat or not lon:
        return {}
    params = urllib.parse.urlencode({
        'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,soil_moisture_0_to_7cm',
        'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum',
        'forecast_days': 1, 'timezone': 'auto'
    })
    try:
        with urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=8) as r:
            x = json.loads(r.read().decode())
        c, d = x.get('current', {}), x.get('daily', {})
        return {
            'temperature': c.get('temperature_2m'),
            'humidity': c.get('relative_humidity_2m'),
            'rainfall': (d.get('precipitation_sum') or [0])[0],
            'wind_speed': c.get('wind_speed_10m'),
            'soil_moisture': c.get('soil_moisture_0_to_7cm'),
            'tmax': (d.get('temperature_2m_max') or [None])[0],
            'tmin': (d.get('temperature_2m_min') or [None])[0]
        }
    except Exception:
        return {}


def month_name():
    return datetime.now().strftime('%B')


def estimate_crop_age(crop):
    data = next((c for c in CROPS if c.get('name') == crop), {})
    months = [m for m in data.get('months', []) if m in MONTHS]
    if not months:
        return 30
    now = datetime.now()
    current = now.month - 1
    starts = sorted(MONTHS.index(m) for m in months)
    if current in starts:
        return max(1, min(180, now.day))
    previous = [s for s in starts if s <= current]
    start = max(previous) if previous else starts[-1]
    diff = current - start if current >= start else 12 - start + current
    return max(1, min(180, diff * 30 + now.day))


def estimate_soil(temp, humidity, rain, api_soil=None):
    if api_soil is not None:
        try:
            return max(0.0, min(1.0, float(api_soil)))
        except Exception:
            pass
    t = float(temp if temp is not None else 28)
    h = float(humidity if humidity is not None else 65)
    r = float(rain if rain is not None else 5)
    value = 0.15 + (h / 100) * 0.30 + min(r, 30) / 100
    if t > 32:
        value -= 0.06
    return max(0.12, min(0.75, value))


def estimate_irrigation(temp, rain, soil, crop):
    if rain is not None and rain >= 20: return 'low'
    if soil is not None and soil >= 0.35: return 'low'
    if rain is not None and rain < 3 and temp is not None and temp >= 30: return 'frequent'
    return 'normal'


def crop_recommendations(temp, rain, month):
    ranked=[]
    for c in CROPS:
        score=0
        if month in c.get('months', []): score += 40
        lo,hi=c.get('temp_range',[10,40])
        if temp is not None:
            score += 35 if lo <= temp <= hi else (15 if abs(temp-lo)<=5 or abs(temp-hi)<=5 else 0)
        rlo,rhi=c.get('rainfall_range',[0,300])
        if rain is not None:
            score += 25 if rlo <= rain <= rhi else (10 if abs(rain-rlo)<=20 or abs(rain-rhi)<=20 else 0)
        ranked.append((score,c))
    ranked.sort(key=lambda x:x[0], reverse=True)
    return [{'name':c['name'],'score':s,'reason':c.get('reason','वर्तमान मौसम के अनुसार उपयुक्त विकल्प।')} for s,c in ranked]


def image_quality(path):
    try:
        with Image.open(path) as im:
            w,h=im.size; stat=ImageStat.Stat(im.convert('RGB')); b=sum(stat.mean)/3
            issues=[]
            if min(w,h)<300: issues.append('फोटो का resolution कम है।')
            if b<35: issues.append('फोटो बहुत अंधेरी है।')
            if b>235: issues.append('फोटो बहुत ज्यादा उजली है।')
            return {'ok':not issues,'width':w,'height':h,'brightness':round(b),'issues':issues}
    except Exception:
        return {'ok':False,'width':0,'height':0,'brightness':0,'issues':['फोटो पढ़ी नहीं जा सकी।']}


def disease_from_context(crop, humidity, rainfall, temp, soil):
    score=20
    if humidity is not None:
        score += 22 if humidity>=80 else 12 if humidity>=65 else 0
    if rainfall is not None:
        score += 18 if rainfall>=30 else 9 if rainfall>=10 else 0
    if soil is not None:
        score += 16 if soil>=0.35 else 8 if soil>=0.25 else 0
    if temp is not None and (temp>=35 or temp<=10): score += 8
    level='HIGH' if score>=70 else 'MEDIUM' if score>=45 else 'LOW'
    data=DISEASES.get(crop, DISEASES.get('Tomato',{}))
    disease=data.get('high') if level=='HIGH' else data.get('medium') if level=='MEDIUM' else 'कोई प्रमुख रोग संकेत नहीं'
    return score, level, disease, data.get('advice',[])


def context_from_location(lat,lon,crop='Tomato'):
    weather=get_weather(lat,lon)
    temp=weather.get('temperature'); humidity=weather.get('humidity'); rainfall=weather.get('rainfall',0)
    soil=estimate_soil(temp,humidity,rainfall,weather.get('soil_moisture'))
    age=estimate_crop_age(crop); irrigation=estimate_irrigation(temp,rainfall,soil,crop)
    return weather, {
        'temperature':temp if temp is not None else 28,
        'humidity':humidity if humidity is not None else 65,
        'rainfall':rainfall if rainfall is not None else 5,
        'soil_moisture':soil,'age':age,'irrigation':irrigation,
        'source':'Open-Meteo' if weather else 'Estimated fallback'
    }


@app.route('/')
def index():
    return render_template('index.html', crops=CROPS, month=month_name())




@app.route('/location-context')
def location_context():
    lat=request.args.get('lat','').strip(); lon=request.args.get('lon','').strip(); crop=request.args.get('crop','Tomato')
    weather,values=context_from_location(lat,lon,crop)
    return jsonify({'weather':weather,**values})


@app.route('/analyze',methods=['POST'])
def analyze():
    crop=request.form.get('crop','Tomato'); lat=request.form.get('latitude','').strip(); lon=request.form.get('longitude','').strip()
    weather,values=context_from_location(lat,lon,crop)
    temp,humidity,rainfall=values['temperature'],values['humidity'],values['rainfall']; soil=values['soil_moisture']
    image_name=None; quality=None
    image=request.files.get('image')
    ai_result = None
    ai_error = None
    if image and image.filename:
        filename=secure_filename(image.filename)
        if filename:
            image_name=filename
            path=os.path.join(app.config['UPLOAD_FOLDER'],filename)
            image.save(path)
            # No photo-quality gate: send the uploaded image to the vision model as-is.
            quality=image_quality(path)
            vision=analyze_crop_image(path,crop,{'temperature':temp,'humidity':humidity,'rainfall':rainfall})
            if vision.get('ok'): ai_result=vision
            else: ai_error=vision.get('error')
    score,level,disease,advice=disease_from_context(crop,humidity,rainfall,temp,soil)
    if ai_result:
        disease=ai_result.get('disease',disease)
        advice=ai_result.get('advice') or advice
    recommendations=crop_recommendations(temp,rainfall,month_name())
    con=db(); con.execute('''INSERT INTO history
        (created_at,crop,disease,risk,severity,confidence,latitude,longitude,temperature,humidity,rainfall,soil_moisture,image_name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (datetime.now().strftime('%Y-%m-%d %H:%M'),crop,disease,score,level,'',lat,lon,str(temp),str(humidity),str(rainfall),str(round(soil*100,1)),image_name)); con.commit(); con.close()
    return render_template('result.html',crop=crop,disease=disease,advice=advice,image_name=image_name,quality=quality,
        ai_result=ai_result,ai_error=ai_error,
        weather=weather,temperature=temp,humidity=humidity,rainfall=rainfall,soil_moisture=soil,recommendations=recommendations,
        latitude=lat,longitude=lon,age=values['age'],irrigation=values['irrigation'])


@app.route('/history')
def history():
    con=db(); rows=con.execute('SELECT * FROM history ORDER BY id DESC LIMIT 50').fetchall(); con.close(); return render_template('history.html',rows=rows)


@app.route('/api/crops')
def api_crops(): return jsonify(CROPS)


@app.route('/api/chat',methods=['POST'])
def chat():
    data=request.get_json(silent=True) or {}; message=(data.get('message') or '').strip().lower(); ctx=data.get('context') or {}
    crop=ctx.get('crop','आपकी फसल'); temp=ctx.get('temperature','-'); humidity=ctx.get('humidity','-'); rain=ctx.get('rainfall','-'); soil=ctx.get('soil_moisture','-'); disease=ctx.get('disease','अभी स्पष्ट नहीं')
    if any(k in message for k in ['बीमारी','रोग','disease','problem','पत्ता','कीट','pest']):
        reply=f'{crop} के लिए उपलब्ध जानकारी में संभावित समस्या: {disease}। साफ पत्ती/पौधे की फोटो से पहचान बेहतर की जा सकती है।'
    elif any(k in message for k in ['मौसम','weather','बारिश','rain','temperature','तापमान']):
        reply=f'आपके खेत के लिए तापमान लगभग {temp}°C, हवा की नमी {humidity}% और बारिश {rain} mm है।'
    elif any(k in message for k in ['नमी','moisture','soil','मिट्टी']):
        reply=f'मिट्टी की अनुमानित नमी {soil}% है। यह मॉडल/मौसम आधारित अनुमान है, सेंसर की exact reading नहीं।'
    elif any(k in message for k in ['सिंचाई','irrigation','पानी']):
        reply='सिंचाई की जरूरत मौसम और मिट्टी की अनुमानित नमी के अनुसार बदल सकती है। खेत की वास्तविक स्थिति भी देखें।'
    elif any(k in message for k in ['दवा','pesticide','कीटनाशक','इलाज','treatment']):
        reply='दवा चुनने से पहले रोग की सही पहचान और स्थानीय कृषि सलाह/उत्पाद लेबल देखें। गलत दवा नुकसान कर सकती है।'
    else:
        reply=f'मैं {crop} के बारे में बीमारी, मौसम, मिट्टी की नमी, सिंचाई और देखभाल से जुड़े सवालों में मदद कर सकता हूँ।'
    return jsonify({'reply':reply})


init_db()
if __name__=='__main__': app.run(debug=True)
