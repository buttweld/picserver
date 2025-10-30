from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from .jpg_to_waveshare73_bmp import convert_to_waveshare_bmp
from app.update_epd7in3f_display import update_epd7in3f_display

import secrets
import io
import os
import threading

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
PROCESSED_DIR = BASE / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 30 * 1024 * 1024  # 30 MB

# Fixed name so the display code always knows where to look
BMP_NAME = "img.bmp"
BMP_PATH = PROCESSED_DIR / BMP_NAME

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")

# simple lock to prevent overlapping display updates
_update_lock = threading.Lock()

def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)

def process_image(input_path: Path, output_path: Path) -> Path:
    """
    Convert the uploaded image into a 7-color BMP for the Waveshare 7.3" display.
    Writes to output_path's folder and returns the final BMP path.
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
    # Ensure the produced file is named img.bmp for consistency
    produced = Path(bmp_path)
    if produced != output_path:
        # rename atomically if needed
        os.replace(produced, output_path)
    return output_path

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

    # Verify it's an actual image
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Save original with consistent name (img.jpg/png/webp)
    src_suffix = ".jpg" if file.content_type == "image/jpeg" else ".png" if file.content_type == "image/png" else ".webp"
    src_path = UPLOAD_DIR / f"img{src_suffix}"
    atomic_write(src_path, data)

    # Process into BMP (PROCESSED_DIR/img.bmp)
    try:
        bmp_path = process_image(src_path, BMP_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    # Cache-bust query so browser shows the fresh files
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
    """Manually trigger updating the e-ink display with the latest processed BMP."""
    if not BMP_PATH.exists():
        return JSONResponse({"ok": False, "msg": "No processed image found."}, status_code=404)

    # prevent concurrent refreshes (SPI is touchy)
    if not _update_lock.acquire(blocking=False):
        return JSONResponse({"ok": False, "msg": "Display update already in progress."}, status_code=409)
    try:
        update_epd7in3f_display(str(BMP_PATH))
        return {"ok": True, "msg": "Display updated."}
    except Exception as e:
        return JSONResponse({"ok": False, "msg": f"Update failed: {e}"}, status_code=500)
    finally:
        _update_lock.release()
