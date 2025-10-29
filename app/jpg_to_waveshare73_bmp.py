#!/usr/bin/env python3
"""
jpg_to_waveshare73_bmp.py
---------------------------------
Convert JPG (or PNG) images into 7‑color BMPs optimized for the
Waveshare 7.3" ACeP e‑ink display (800x480).

Features:
- Fixed 7‑color palette (Black, White, Red, Yellow, Blue, Green, Orange)
- Dithering (Floyd–Steinberg) for better gradients on e‑ink
- Two resize modes: "fit" (contain/letterbox) or "fill" (cover/crop)
- Optional contrast/saturation/sharpness boosts
- Orientation helpers (rotate 0/90/180/270)
- Output as 8‑bit palettized BMP or 24‑bit BMP

Usage:
  python jpg_to_waveshare73_bmp.py input.jpg
  python jpg_to_waveshare73_bmp.py *.jpg --out outdir --mode fill --dither --contrast 1.2
  python jpg_to_waveshare73_bmp.py in_dir --glob "*.jpg" --rotate 90 --bmp-mode RGB

Notes:
- Default target size is 800x480 (Waveshare 7.3" ACeP).
- "fit" preserves the whole image (might pad with white).
- "fill" fills the screen (crops edges if aspect ratios differ).
- If your downstream code expects 24‑bit BMPs, use --bmp-mode RGB.
"""

import argparse
import math
import os
import sys
import glob
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageEnhance

# ---- Waveshare 7‑color palette (confirmed: Black, White, Red, Yellow, Blue, Green, Orange) ----
# Sources:
# - Waveshare 7.3" ACeP product page & application notes commonly reference these 7 states.
# RGB triplets chosen to be canonical primaries; displays may approximate.
WAVESHARE_7C_PALETTE: Tuple[Tuple[int, int, int], ...] = (
    (0, 0, 0),         # Black
    (255, 255, 255),   # White
    (255, 0, 0),       # Red
    (255, 255, 0),     # Yellow
    (0, 0, 255),       # Blue
    (0, 255, 0),       # Green
    (255, 165, 0),     # Orange
)

def build_palette_image() -> Image.Image:
    """Build a PIL 'P' image with our 7‑color palette padded to 256 entries."""
    pal_img = Image.new("P", (1, 1))
    flat = []
    for rgb in WAVESHARE_7C_PALETTE:
        flat.extend(rgb)
    # pad remaining (256-7) colors with zeros
    flat.extend([0] * (256*3 - len(flat)))
    pal_img.putpalette(flat)
    return pal_img

def resize_with_mode(img: Image.Image, target: Tuple[int, int], mode: str, bg=(255, 255, 255)) -> Image.Image:
    """Resize image to target (w,h) using 'fit' (contain) or 'fill' (cover)."""
    tw, th = target
    iw, ih = img.size
    if mode not in {"fit", "fill"}:
        raise ValueError("mode must be 'fit' or 'fill'")

    src_aspect = iw / ih
    dst_aspect = tw / th

    if mode == "fit":
        # contain: scale to fit inside target, pad with background
        if src_aspect > dst_aspect:
            new_w = tw
            new_h = round(tw / src_aspect)
        else:
            new_h = th
            new_w = round(th * src_aspect)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (tw, th), bg)
        x = (tw - new_w) // 2
        y = (th - new_h) // 2
        canvas.paste(resized, (x, y))
        return canvas
    else:
        # fill: scale until the smaller side fits, then center crop
        if src_aspect < dst_aspect:
            new_w = tw
            new_h = round(tw / src_aspect)
        else:
            new_h = th
            new_w = round(th * src_aspect)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        # center-crop to target
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        right = left + tw
        bottom = top + th
        return resized.crop((left, top, right, bottom))

def enhance_image(img: Image.Image, contrast: float, saturation: float, sharpness: float) -> Image.Image:
    """Apply optional enhancements to help e‑ink contrast/legibility."""
    if contrast and abs(contrast - 1.0) > 1e-3:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation and abs(saturation - 1.0) > 1e-3:
        img = ImageEnhance.Color(img).enhance(saturation)
    if sharpness and abs(sharpness - 1.0) > 1e-3:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img

def quantize_to_7c(img_rgb: Image.Image, dither: bool) -> Image.Image:
    """Quantize an RGB image to the fixed 7‑color palette."""
    pal_img = build_palette_image()
    dither_flag = Image.FLOYDSTEINBERG if dither else Image.NONE
    # quantize returns a 'P' mode image with our palette embedded
    q = img_rgb.quantize(palette=pal_img, dither=dither_flag)
    return q

def save_bmp(img_quantized: Image.Image, out_path: Path, bmp_mode: str):
    """
    Save BMP as either:
      - 'P' (8‑bit palettized BMP with embedded 7‑color palette)
      - 'RGB' (24‑bit BMP, if downstream expects truecolor)
    """
    if bmp_mode.upper() == "P":
        if img_quantized.mode != "P":
            img_quantized = img_quantized.convert("P")
        img_quantized.save(out_path, format="BMP")
    elif bmp_mode.upper() == "RGB":
        img_rgb = img_quantized.convert("RGB")
        img_rgb.save(out_path, format="BMP")
    else:
        raise ValueError("--bmp-mode must be 'P' or 'RGB'")

def iter_input_paths(arg_path: str, glob_pat: str | None) -> Iterable[Path]:
    p = Path(arg_path)
    if p.is_dir():
        pattern = glob_pat or "*.jpg"
        for fp in sorted(p.glob(pattern)):
            if fp.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                yield fp
    else:
        yield p

def main():
    parser = argparse.ArgumentParser(description="Convert images to 7‑color BMPs for Waveshare 7.3\" ACeP e‑ink (800x480).")
    parser.add_argument("input", help="Input file or directory.")
    parser.add_argument("--glob", default=None, help="Glob pattern if input is a directory (e.g. \"*.jpg\").")
    parser.add_argument("--out", default="out_bmp", help="Output directory (default: out_bmp).")
    parser.add_argument("--width", type=int, default=800, help="Target width (default: 800).")
    parser.add_argument("--height", type=int, default=480, help="Target height (default: 480).")
    parser.add_argument("--mode", choices=["fit", "fill"], default="fit", help="Resize mode: fit=contain (letterbox), fill=cover (crop).")
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0, help="Rotate degrees clockwise before resizing (default: 0).")
    parser.add_argument("--dither", action="store_true", help="Use Floyd–Steinberg dithering for quantization.")
    parser.add_argument("--no-dither", dest="dither", action="store_false", help="Disable dithering.")
    parser.set_defaults(dither=True)
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast boost (e.g., 1.2).")
    parser.add_argument("--saturation", type=float, default=1.0, help="Saturation boost (e.g., 1.1).")
    parser.add_argument("--sharpness", type=float, default=1.0, help="Sharpness boost (e.g., 1.1).")
    parser.add_argument("--bmp-mode", choices=["P", "RGB"], default="P", help="BMP output type: P=8‑bit palettized, RGB=24‑bit truecolor.")
    parser.add_argument("--bg", default="white", help="Background for letterboxing (CSS name or #RRGGBB). Default white.")
    args = parser.parse_args()

    # Parse background color
    bg_color = (255, 255, 255)
    try:
        if args.bg.startswith("#") and len(args.bg) in (4, 7):
            bg_color = Image.Image()._getencoder("zip", None, None)  # dummy to use PIL color parsing
        # Use PIL to parse color
        tmp = Image.new("RGB", (1, 1), args.bg)
        bg_color = tmp.getpixel((0, 0))
    except Exception:
        pass  # fallback to white if parsing fails

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    target = (args.width, args.height)

    count_ok = 0
    count_err = 0

    for in_path in iter_input_paths(args.input, args.glob):
        try:
            img = Image.open(in_path).convert("RGB")

            # Optional rotation
            if args.rotate:
                img = img.rotate(-args.rotate, expand=True)  # PIL: positive angle is counter-clockwise

            # Resize
            img = resize_with_mode(img, target, args.mode, bg=bg_color)

            # Optional enhancements
            img = enhance_image(img, args.contrast, args.saturation, args.sharpness)

            # Quantize to 7 colors
            q = quantize_to_7c(img, dither=args.dither)

            # Save BMP
            out_name = f"{in_path.stem}.bmp"
            out_path = out_dir / out_name
            save_bmp(q, out_path, bmp_mode=args.bmp_mode)

            print(f"[OK] {in_path} -> {out_path}")
            count_ok += 1
        except Exception as e:
            print(f"[ERR] {in_path}: {e}", file=sys.stderr)
            count_err += 1

    print(f"Done. Converted: {count_ok}, Errors: {count_err}")
    if count_err > 0:
        sys.exit(1)

def convert_to_waveshare_bmp(
    input_path,
    output_dir="out_bmp",
    width=800,
    height=480,
    mode="fit",
    rotate=0,
    dither=True,
    contrast=1.0,
    saturation=1.0,
    sharpness=1.0,
    bmp_mode="P",
):
    """Convenient programmatic API wrapper."""
    from pathlib import Path
    from PIL import Image

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(input_path).convert("RGB")
    if rotate:
        img = img.rotate(-rotate, expand=True)

    # Directly call helper functions defined in this file
    target = (width, height)
    img = resize_with_mode(img, target, mode)
    img = enhance_image(img, contrast, saturation, sharpness)
    q = quantize_to_7c(img, dither=dither)
    out_path = out_dir / f"{Path(input_path).stem}.bmp"
    save_bmp(q, out_path, bmp_mode=bmp_mode)

    return out_path



if __name__ == "__main__":
    main()
