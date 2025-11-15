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
import os
import time
import hmac
import hashlib
import base64
import json
import requests

@app.post("/analyse/audio")
async def analyse_audio(
    file: UploadFile = File(...),
    audio_type: str = Form(None),
    action_type: str = Form(None),
    estimate_music: bool = Form(False),
    capture_date: str = Form(None),
    upload_date: str = Form(None),
):
    """
    Receives an audio file from Zapier, sends it to ACRCloud,
    and returns structured musical metadata + transcription details.
    """

    # --------- read file into memory ---------
    audio_bytes = await file.read()

    # --------- load keys from environment ---------
    host = os.environ.get("ACR_HOST")
    access_key = os.environ.get("ACR_ACCESS_KEY")
    secret_key = os.environ.get("ACR_SECRET_KEY")

    if not host or not access_key or not secret_key:
        return {"error": "ACRCloud keys missing in environment variables"}

    # --------- ACRCloud request prep ---------
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    # Create the signature
    string_to_sign = (
        http_method + "\n" +
        http_uri + "\n" +
        access_key + "\n" +
        data_type + "\n" +
        signature_version + "\n" +
        timestamp
    )

    # Sign with HMAC-SHA1
    sign = base64.b64encode(
        hmac.new(
            secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
    ).decode('utf-8')

    # --------- Form Data ---------
    files = {
        "sample": ("audio", audio_bytes, file.content_type)
    }

    data = {
        "access_key": access_key,
        "sample_bytes": str(len(audio_bytes)),
        "timestamp": timestamp,
        "signature": sign,
        "data_type": data_type,
        "signature_version": signature_version
    }

    # --------- Send to ACRCloud ---------
    acr_response = requests.post(
        f"https://{host}/v1/identify",
        files=files,
        data=data
    )

    try:
        acr_json = acr_response.json()
    except:
        acr_json = {"error": "Invalid JSON returned from ACRCloud", "raw": acr_response.text}

    # --------- Return the structured result ---------
    return {
        "filename": file.filename,
        "audio_type": audio_type,
        "action_type": action_type,
        "estimate_music": estimate_music,
        "capture_date": capture_date,
        "upload_date": upload_date,
        "acr_result": acr_json
    }

    filename = file.filename

    # For now, fake detection (test stability first)
    result = {
        "filename": filename,
        "audio_type": audio_type,
        "action_type": action_type,
        "estimate_music": estimate_music,
        "analysis": "Audio received successfully (v1 placeholder)",
        "key_guess": "",
        "bpm_guess": "",
        "chord_progression": "",
        "capture_date": capture_date,
        "upload_date": upload_date,
    }

    return result


# ------------ IMAGE ANALYSIS -----------------
@app.post("/analyse/image")
async def analyse_image(
    file: UploadFile = File(...),
    action_type: str = Form(None),
    capture_date: str = Form(None),
    upload_date: str = Form(None),
):
    result = {
        "filename": file.filename,
        "action_type": action_type,
        "analysis": "Image received successfully (v1 placeholder)",
        "capture_date": capture_date,
        "upload_date": upload_date,
    }

    return result


# ------------ HEALTH CHECK FOR ZAPIER ----------
@app.get("/health")
def health():
    return {"ok": True}

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
