from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from .jpg_to_waveshare73_bmp import convert_to_waveshare_bmp
from app.update_epd7in3f_display import update_epd7in3f_display

import secrets
import io

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
PROCESSED_DIR = BASE / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 30 * 1024 * 1024  # 30 MB

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")

def process_image(input_path: Path, output_path: Path) -> None:
    """
    Convert a given image into a 7-color BMP suitable for the Waveshare 7.3" e-ink display.
    """
    # Call your existing conversion function
    bmp_path = convert_to_waveshare_bmp(
        input_path=str(input_path),
        output_dir=str(output_path.parent),
        width=800,
        height=480,
        mode="fit",         # or "fill" if you prefer cropping to fill
        rotate=0,
        dither=True,
        contrast=1.5,
        saturation=1.5,
        sharpness=1.0,
        bmp_mode="RGB"        # "P" for 8-bit palette, or "RGB" for 24-bit BMP
    )

    print(f"✅ Processed {input_path.name} → {bmp_path}")

    print("Updating eink display...")
    update_epd7in3f_display(str(bmp_path))


@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    # Read and size-check in memory (safer on small devices)
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 30 MB).")

    # Verify it is actually an image (guards against bogus MIME)
    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Set file name as img and set the suffix
    src_suffix = ".jpg" if file.content_type == "image/jpeg" else ".png" if file.content_type == "image/png" else ".webp"
    src_path = UPLOAD_DIR / f"img{src_suffix}"
    out_path = PROCESSED_DIR / f"img.bmp"

    # Write the uploaded bytes to disk
    src_path.write_bytes(data)

    # Run your processing
    try:
        process_image(src_path, out_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return templates.TemplateResponse(
        "done.html",
        {
            "request": request,
            "original_url": f"/uploads/{src_path.name}",
            "processed_url": f"/processed/{out_path.name}",
        },
    )
