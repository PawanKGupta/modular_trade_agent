"""Persist admin-uploaded offline payment QR images on disk."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
BILLING_DATA_DIR = ROOT_DIR / "data" / "billing"
QR_BASENAME = "offline_payment_qr"
MAX_QR_BYTES = 2 * 1024 * 1024

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class OfflinePaymentQrValidationError(ValueError):
    """Invalid upload (type, size, or empty)."""


def _billing_dir() -> Path:
    BILLING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return BILLING_DATA_DIR


def find_uploaded_qr_path() -> Path | None:
    """Return path to the stored QR file, if any."""
    directory = _billing_dir()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        candidate = directory / f"{QR_BASENAME}{ext}"
        if candidate.is_file():
            return candidate
    return None


def offline_payment_qr_uploaded() -> bool:
    return find_uploaded_qr_path() is not None


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def _detect_image_ext(content: bytes) -> str | None:
    """Return file extension from magic bytes, or None if not a supported image."""
    if len(content) >= 8 and content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if len(content) >= 3 and content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if len(content) >= 6 and content[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def save_offline_payment_qr(content: bytes, content_type: str | None) -> Path:
    if not content:
        raise OfflinePaymentQrValidationError("QR image file is empty")
    if len(content) > MAX_QR_BYTES:
        raise OfflinePaymentQrValidationError(
            f"QR image must be at most {MAX_QR_BYTES // (1024 * 1024)} MB"
        )
    normalized = _normalize_content_type(content_type)
    ext = _CONTENT_TYPE_TO_EXT.get(normalized)
    if not ext:
        allowed = ", ".join(sorted(_CONTENT_TYPE_TO_EXT))
        raise OfflinePaymentQrValidationError(f"Unsupported image type. Use one of: {allowed}")

    detected_ext = _detect_image_ext(content)
    if detected_ext is None:
        raise OfflinePaymentQrValidationError(
            "File is not a valid PNG, JPEG, WebP, or GIF image"
        )
    if detected_ext != ext:
        raise OfflinePaymentQrValidationError(
            f"Image content does not match declared type ({normalized})"
        )

    delete_offline_payment_qr()
    path = _billing_dir() / f"{QR_BASENAME}{ext}"
    path.write_bytes(content)
    return path


def delete_offline_payment_qr() -> None:
    directory = _billing_dir()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        candidate = directory / f"{QR_BASENAME}{ext}"
        if candidate.is_file():
            candidate.unlink()


def media_type_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "application/octet-stream"
