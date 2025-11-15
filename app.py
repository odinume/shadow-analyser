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

# TEMP: Hardcode credentials so we can get it working tonight.
# Replace with os.getenv later once Railway behaves.
ACR_HOST = "identify-ap-southeast-1.acrcloud.com"
ACR_ACCESS_KEY = "2e792315bc46e4ea4654b407a28a0f9a"
ACR_ACCESS_SECRET = "4qmupBXDrMs3EaAJhLo9MNp4QukHgFZUiCcrv17G"


from pydub import AudioSegment
from tempfile import NamedTemporaryFile

@app.post("/analyse/audio")
async def analyse_audio(
    file: UploadFile = File(...),
    audio_type: str = Form(None),
    action_type: str = Form(None),
    estimate_music: bool = Form(False),
    capture_date: str = Form(None),
    upload_date: str = Form(None),
    start_time: int = Form(0),       # <-- NEW
    duration: int = Form(15),        # <-- NEW
):
    """
    Receives full audio file.
    Trims a segment for ACRCloud (start_time → start_time+duration),
    but keeps original full file data for Airtable.
    """

    # -------- Read full audio into memory --------
    full_audio_bytes = await file.read()

    # -------- Load secrets --------
    host = os.environ.get("ACR_HOST")
    access_key = os.environ.get("ACR_ACCESS_KEY")
    secret_key = os.environ.get("ACR_SECRET_KEY")

    if not host or not access_key or not secret_key:
        return {"error": "ACRCloud keys missing in environment variables"}

    # -------- Use pydub to load full audio --------
    audio = AudioSegment.from_file(
        io.BytesIO(full_audio_bytes),
        format=file.filename.split(".")[-1].lower()
    )

    # Convert times from seconds → milliseconds
    start_ms = max(0, start_time * 1000)
    end_ms = min(len(audio), start_ms + duration * 1000)

    trimmed = audio[start_ms:end_ms]

    # Save trimmed segment to temp file to send to ACR
    with NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        trimmed.export(tmp.name, format="mp3")
        trimmed_path = tmp.name

    # -------- ACRCloud request prep --------
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = (
        http_method + "\n" +
        http_uri + "\n" +
        access_key + "\n" +
        data_type + "\n" +
        signature_version + "\n" +
        timestamp
    )

    sign = base64.b64encode(
        hmac.new(
            secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
    ).decode('utf-8')

    # Read trimmed file bytes
    with open(trimmed_path, "rb") as f:
        trimmed_bytes = f.read()

    data = {
        "access_key": access_key,
        "sample_bytes": str(len(trimmed_bytes)),
        "timestamp": timestamp,
        "signature": sign,
        "data_type": data_type,
        "signature_version": signature_version
    }

    files = {
        "sample": ("audio.mp3", trimmed_bytes, "audio/mpeg")
    }

    acr_response = requests.post(
        f"https://{host}/v1/identify",
        files=files,
        data=data
    )

    try:
        acr_json = acr_response.json()
    except:
        acr_json = {"error": "Invalid JSON returned from ACRCloud", "raw": acr_response.text}

    # Cleanup temp file
    try:
        os.remove(trimmed_path)
    except:
        pass

    # -------- Final output --------
    return {
        "filename": file.filename,
        "audio_type": audio_type,
        "action_type": action_type,
        "estimate_music": estimate_music,
        "capture_date": capture_date,
        "upload_date": upload_date,

        # FULL FILE still goes to Airtable — you handle that in Zapier
        "full_file_stored": True,

        # ACR result for the trimmed slice
        "acr_result": acr_json,

        # Debug info
        "start_time_used": start_time,
        "duration_used": duration,
        "segment_length_ms": end_ms - start_ms,
    }


# ------------ HEALTH CHECK FOR ZAPIER ----------
@app.get("/health")
def health():
    return {"ok": True}

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
