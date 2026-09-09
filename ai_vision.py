import os, base64, json, requests

OPENAI_URL = "https://api.openai.com/v1/responses"
MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-5.6-luna")

def _extract_text(data):
    if isinstance(data, dict):
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()
        parts = []
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if isinstance(c, dict) and isinstance(c.get("text"), str):
                    parts.append(c["text"])
        return "\n".join(parts).strip()
    return ""

def analyze_crop_image(image_path, crop, location_context=None):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "AI service is not configured."}
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ctx = location_context or {}
    prompt = f"""You are CropPulse AI's crop-disease vision assistant for Indian farmers.
Analyze the uploaded plant/crop photo itself. Never use a fixed/demo disease answer.
Selected crop: {crop}.
Optional context: temperature={ctx.get('temperature','unknown')} C, humidity={ctx.get('humidity','unknown')}%, rainfall={ctx.get('rainfall','unknown')} mm.
Return ONLY valid JSON with keys: disease (short Hindi name of most likely visible disease/problem, or 'पहचान स्पष्ट नहीं है'), signs (one short Hindi sentence about visible signs), advice (array of 3 short safe Hindi management steps), confidence (0-100 visual evidence score).
The image may be dark, blurry, distant, rotated, noisy or poorly framed. Still inspect it and make the best evidence-based attempt. Do not invent a disease when evidence is insufficient. Do not discuss field risk, weather risk or generic crop recommendations in the disease answer. Do not give pesticide dose or mixing instructions."""
    payload = {"model": MODEL, "input": [{"role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}
    ]}], "max_output_tokens": 500}
    try:
        r = requests.post(OPENAI_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
        if not r.ok:
            return {"ok": False, "error": f"AI request failed ({r.status_code})."}
        text = _extract_text(r.json())
        if not text:
            return {"ok": False, "error": "AI returned no analysis."}
        try:
            parsed = json.loads(text)
        except Exception:
            a,b=text.find("{"),text.rfind("}")
            parsed=json.loads(text[a:b+1]) if a>=0 and b>a else None
        if not isinstance(parsed, dict):
            return {"ok": False, "error": "AI returned an unreadable result."}
        advice=parsed.get("advice") if isinstance(parsed.get("advice"),list) else []
        return {"ok":True,"disease":str(parsed.get("disease") or "पहचान स्पष्ट नहीं है"),"signs":str(parsed.get("signs") or "दिखाई देने वाले लक्षणों से स्पष्ट पहचान नहीं हो सकी।"),"advice":[str(x) for x in advice[:4]],"confidence":parsed.get("confidence")}
    except Exception:
        return {"ok": False, "error": "AI analysis could not be completed."}
