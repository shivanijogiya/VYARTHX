"""Perceptual hashing (difference hash) without external dependencies beyond Pillow."""
from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageOps


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dhash(image_bytes: bytes, size: int = 8) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def exif_datetime(image_bytes: bytes):
    """Best-effort capture timestamp from EXIF (DateTimeOriginal). Returns datetime or None."""
    from datetime import datetime

    try:
        img = Image.open(io.BytesIO(image_bytes))
        ex = img.getexif()
        sub = ex.get_ifd(0x8769) if hasattr(ex, "get_ifd") else {}
        raw = sub.get(0x9003) or ex.get(0x0132)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None
