import tempfile, os
import soundfile as sf
import librosa
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()

def to_wav(tmp_path) -> str:
  y, sr = librosa.load(tmp_path, sr=44100, mono=True)
  out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
  sf.write(out, y, 44100)
  return out

def estimate_bpm_from_audio(wav_path: str):
  y, sr = librosa.load(wav_path, sr=None, mono=True)
  if y.size == 0:
    return 0
  tempi = librosa.beat.tempo(y=y, sr=sr, aggregate=None)
  return int(round(float(tempi.mean()))) if tempi is not None and len(tempi)>0 else 0

@app.get("/")
def root():
  return {"ok": True, "message": "Shadow analyzer up"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
  try:
    raw = await file.read()
    tmp_in = tempfile.NamedTemporaryFile(delete=False)
    tmp_in.write(raw); tmp_in.flush()
    wav_path = to_wav(tmp_in.name)
    bpm = estimate_bpm_from_audio(wav_path)
    os.unlink(tmp_in.name); os.unlink(wav_path)
    return JSONResponse({
      "key": "", "scale": "", "bpm": bpm,
      "progression": "", "confidence": 0.0, "note_count": 0
    })
  except Exception as e:
    return JSONResponse({"error": str(e)}, status_code=500)
