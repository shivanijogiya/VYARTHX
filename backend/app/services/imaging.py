"""Image utilities: SHA-256, perceptual difference hash (dHash) and simple quality checks (numpy + Pillow)."""
from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image, ImageOps


def load_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dhash(img: Image.Image, size: int = 8) -> str:
    """64-bit difference hash. Robust to resizing/re-compression, so re-uploads of the same photo are caught."""
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = np.asarray(g, dtype=np.int16)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def quality(img: Image.Image) -> dict:
    """Brightness and sharpness (variance of a Laplacian, the classic blur metric) computed in numpy."""
    g = np.asarray(img.convert("L").resize((256, 256)), dtype=np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    sharp = float(lap.var())
    bright = float(g.mean())
    issues = []
    if bright < 35:
        issues.append("Image is very dark")
    if bright > 235:
        issues.append("Image is over-exposed")
    if sharp < 15:
        issues.append("Image looks blurred")
    return {"brightness": round(bright, 1), "sharpness": round(sharp, 1), "issues": issues,
            "width": img.width, "height": img.height}
