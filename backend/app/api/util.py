from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy.inspection import inspect

MAX_UPLOAD = 8 * 1024 * 1024


def to_dict(obj: Any, exclude: tuple[str, ...] = ()) -> dict:
    out = {}
    for c in inspect(obj).mapper.column_attrs:
        if c.key in exclude:
            continue
        v = getattr(obj, c.key)
        out[c.key] = v.isoformat() if isinstance(v, datetime) else v
    return out


async def read_image(f: UploadFile | None, required: bool = False) -> tuple[bytes | None, str]:
    if f is None or not getattr(f, "filename", None):
        if required:
            raise HTTPException(400, "An image is required")
        return None, ""
    data = await f.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Image too large (max 8 MB)")
    try:
        im = Image.open(io.BytesIO(data))
        im.verify()
    except Exception:
        raise HTTPException(400, "File is not a valid image")
    return data, f.filename or ""
