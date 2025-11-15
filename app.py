from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# MODELS
# -------------------------------
class TextPayload(BaseModel):
    text: str
    audio_type: str | None = None
    action_type: str | None = None
    estimate_music: bool | None = False
    capture_date: str | None = None
    upload_date: str | None = None


# -------------------------------
# ROUTES
# -------------------------------

@app.get("/")
def home():
    return {"status": "Shadow backend running", "version": "1.0"}


# ------------ TEXT ANALYSIS (from transcription) ------------
@app.post("/analyse/text")
async def analyse_text(payload: TextPayload):
    """
    Zapier sends: transcription text + metadata
    Returns: structured JSON for Airtable / Notion
    """

    text = payload.text.lower()

    # Quick mode detection (better logic later)
    if payload.audio_type:
        mode = payload.audio_type
    elif "song" in text:
        mode = "Music"
    elif "idea" in text or "story" in text:
        mode = "Writing"
    else:
        mode = "Concept"

    result = {
        "mode": mode,
        "summary": text[:200] + "...",
        "tags": ["Idea", "Reflection"],
        "genre": "",
        "mood": "",
        "key_guess": "",
        "bpm_guess": "",
        "chord_progression": "",
        "references": [],
        "capture_date": payload.capture_date,
        "upload_date": payload.upload_date,
    }

    return result


# ------------ AUDIO FILE ANALYSIS ------------
import time
import hmac
import hashlib
import base64
import json
import requests

ACR_HOST = "identify-ap-southeast-1.acrcloud.com"
ACR_ACCESS_KEY = "2e792315bc46e4ea4654b407a28a0f9a"
ACR_ACCESS_SECRET = "4qmupBXDrMs3EaAJhLo9MNp4QukHgFZUiCcrv17G"

MAX_BYTES_FOR_ACR = 2_000_000  # ~2MB chunk for ACR (roughly 15–25s depending on format)

@app.post("/analyse/audio")
async def analyse_audio(
    file: UploadFile = File(...),
    audio_type: str = Form(None),
    action_type: str = Form(None),
    estimate_music: bool = Form(False),
    capture_date: str = Form(None),
    upload_date: str = Form(None),
):
    # 1) Read full file (so original is still usable elsewhere)
    full_audio_bytes = await file.read()
    original_size = len(full_audio_bytes)

    # 2) Create a cropped version JUST for ACR
    #    Use a middle slice so you're more likely to catch the good part
    if original_size <= MAX_BYTES_FOR_ACR:
        acr_bytes = full_audio_bytes
        crop_info = "full file used"
    else:
        start = max(0, original_size // 2 - MAX_BYTES_FOR_ACR // 2)
        end = start + MAX_BYTES_FOR_ACR
        acr_bytes = full_audio_bytes[start:end]
        crop_info = f"middle {MAX_BYTES_FOR_ACR} bytes of {original_size}"

    # ---- ACRCloud auth + request ----
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = (
        http_method + "\n" +
        http_uri + "\n" +
        ACR_ACCESS_KEY + "\n" +
        data_type + "\n" +
        signature_version + "\n" +
        timestamp
    )

    sign = base64.b64encode(
        hmac.new(
            ACR_ACCESS_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1
        ).digest()
    ).decode("utf-8")

    files = {
        "sample": ("audio", acr_bytes, file.content_type)
    }

    data = {
        "access_key": ACR_ACCESS_KEY,
        "sample_bytes": str(len(acr_bytes)),
        "timestamp": timestamp,
        "signature": sign,
        "data_type": data_type,
        "signature_version": signature_version,
    }

    acr_response = requests.post(
        f"https://{ACR_HOST}/v1/identify",
        files=files,
        data=data,
        timeout=15,
    )

    try:
        acr_json = acr_response.json()
    except Exception:
        acr_json = {
            "error": "Invalid JSON returned from ACRCloud",
            "status_code": acr_response.status_code,
            "raw": acr_response.text,
        }

    return {
        "filename": file.filename,
        "audio_type": audio_type,
        "action_type": action_type,
        "estimate_music": estimate_music,
        "capture_date": capture_date,
        "upload_date": upload_date,
        "original_size_bytes": original_size,
        "sent_to_acr_bytes": len(acr_bytes),
        "crop_info": crop_info,
        "acr_result": acr_json,
    }



# ------------ HEALTH CHECK FOR ZAPIER ----------
@app.get("/health")
def health():
    return {"ok": True}

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
