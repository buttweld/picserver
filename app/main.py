import io
import os
import time
import secrets
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError

from .jpg_to_waveshare73_bmp import convert_to_waveshare_bmp
from app.update_epd7in3f_display import update_epd7in3f_display
from app.get_weather import get_weather

# ------------------------ Logging ------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("picserver")

# ------------------------ Paths --------------------------
BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
PROCESSED_DIR = BASE / "processed"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 30 * 1024 * 1024  # 30 MB

# Fixed output so the display always reads the same file
BMP_NAME = "img.bmp"
BMP_PATH = PROCESSED_DIR / BMP_NAME

# ------------------- Environment helpers ----------------
def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("Env %s=%r is invalid; using default %s", name, raw, default)
        return default

def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("Env %s=%r is invalid; using default %s", name, raw, default)
        return default

# Weather defaults: ODTÜ Makina, Ankara
LAT = _get_float("WEATHER_LAT", 39.889932)
LON = _get_float("WEATHER_LON", 32.780696)
API_KEY = os.getenv("WEATHER_API_KEY")  # no default; treat None as missing
PERIOD_SEC = _get_int("WEATHER_PERIOD_SEC", 300)

# ---------------------- App + mounts ---------------------
app = FastAPI()
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")

# Locks
_update_lock = threading.Lock()
app.state.weather_lock = threading.Lock()

# Weather shared state
app.state.weather_data: Optional[Dict[str, Any]] = None
app.state.weather_updated: Optional[datetime] = None
app.state.weather_error: Optional[str] = None

# --------------------- Utility funcs ---------------------
def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)  # atomic if same FS

def process_image(input_path: Path, output_path: Path) -> Path:
    """
    Convert uploaded image into a 7-color BMP for Waveshare 7.3".
    Writes to output_path directory and returns the final BMP path.
    """
    bmp_path = convert_to_waveshare_bmp(
        input_path=str(input_path),
        output_dir=str(output_path.parent),
        width=800,
        height=480,
        mode="fit",        # or "fill"
        rotate=0,
        dither=True,
        contrast=1.5,
        saturation=1.5,
        sharpness=1.0,
        bmp_mode="RGB"     # or "P"
    )
    produced = Path(bmp_path)
    if produced != output_path:
        os.replace(produced, output_path)
    return output_path

def _weather_once():
    try:
        if not API_KEY:
            raise RuntimeError("WEATHER_API_KEY not set")
        data = get_weather(LAT, LON, API_KEY)
        with app.state.weather_lock:
            app.state.weather_data = data
            app.state.weather_updated = datetime.now(timezone.utc)
            app.state.weather_error = None
        log.info("Weather updated at %s", app.state.weather_updated.isoformat())
        log.info(f"Weather information:\n{data}")
    except Exception as e:
        with app.state.weather_lock:
            app.state.weather_error = str(e)
        log.warning("Weather update failed: %s", e)

def _weather_worker(stop_event: threading.Event):
    _weather_once()  # run immediately on start
    while not stop_event.is_set():
        for _ in range(PERIOD_SEC):
            if stop_event.is_set():
                break
            time.sleep(1)
        if stop_event.is_set():
            break
        _weather_once()

# ------------------- Lifespan (startup/shutdown) --------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app_: FastAPI):
    stop = threading.Event()
    app_.state._weather_stop_event = stop
    t = threading.Thread(target=_weather_worker, args=(stop,), daemon=True)
    t.start()
    app_.state._weather_thread = t
    log.info(
        "Weather thread started: lat=%.6f lon=%.6f period=%ss",
        LAT, LON, PERIOD_SEC
    )
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=5)

app.router.lifespan_context = lifespan

# ------------------------- Routes ------------------------
@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 30 MB).")

    # Verify it's an image (on a copy of the bytes)
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Save original with a consistent name (or add a token if you expect concurrency)
    src_suffix = (
        ".jpg" if file.content_type == "image/jpeg"
        else ".png" if file.content_type == "image/png"
        else ".webp"
    )
    src_path = UPLOAD_DIR / f"img{src_suffix}"
    atomic_write(src_path, data)

    # Process into BMP
    try:
        bmp_path = process_image(src_path, BMP_PATH)
    except Exception as e:
        log.exception("Processing failed")
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    # Cache-bust so the browser shows the fresh files
    tok = secrets.token_hex(4)

    return templates.TemplateResponse(
        "done.html",
        {
            "request": request,
            "original_url": f"/uploads/{src_path.name}?v={tok}",
            "processed_url": f"/processed/{bmp_path.name}?v={tok}",
        },
    )

@app.post("/update")
def update_display():
    """Manually update the e-ink display with the latest processed BMP."""
    if not BMP_PATH.exists():
        return JSONResponse({"ok": False, "msg": "No processed image found."}, status_code=404)

    if not _update_lock.acquire(blocking=False):
        return JSONResponse({"ok": False, "msg": "Display update already in progress."}, status_code=409)
    try:
        update_epd7in3f_display(str(BMP_PATH))
        return {"ok": True, "msg": "Display updated."}
    except Exception as e:
        log.exception("Display update failed")
        return JSONResponse({"ok": False, "msg": f"Update failed: {e}"}, status_code=500)
    finally:
        _update_lock.release()

@app.get("/weather")
def get_cached_weather():
    with app.state.weather_lock:
        if app.state.weather_data is None:
            # Distinguish between "warming up" and "error"
            if app.state.weather_error:
                return JSONResponse({"ok": False, "error": app.state.weather_error}, status_code=503)
            return JSONResponse({"ok": False, "error": "Weather not ready"}, status_code=202)
        return {
            "ok": True,
            "data": app.state.weather_data,
            "updated_utc": app.state.weather_updated.isoformat() if app.state.weather_updated else None,
            "lat": LAT,
            "lon": LON,
            "period_sec": PERIOD_SEC,
        }
