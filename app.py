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
    Zapier sends audio file.
    Returns placeholder analysis until we plug in the music ML model.
    """

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
