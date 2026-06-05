"""Tests for offline payment QR file storage."""

from pathlib import Path

import pytest

from src.application.services import billing_offline_qr_storage as storage


@pytest.fixture
def qr_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BILLING_DATA_DIR", tmp_path)
    return tmp_path


def test_save_and_find_png(qr_dir: Path):
    data = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    path = storage.save_offline_payment_qr(data, "image/png")
    assert path.name == "offline_payment_qr.png"
    assert storage.find_uploaded_qr_path() == path
    assert storage.offline_payment_qr_uploaded() is True


def test_save_replaces_previous(qr_dir: Path):
    storage.save_offline_payment_qr(b"\x89PNG\r\n\x1a\n" + b"a" * 32, "image/png")
    storage.save_offline_payment_qr(b"\xff\xd8\xff" + b"b" * 32, "image/jpeg")
    assert storage.find_uploaded_qr_path() is not None
    assert storage.find_uploaded_qr_path().suffix == ".jpg"
    assert not (qr_dir / "offline_payment_qr.png").exists()


def test_rejects_unsupported_type(qr_dir: Path):
    with pytest.raises(storage.OfflinePaymentQrValidationError, match="Unsupported"):
        storage.save_offline_payment_qr(b"not-an-image", "text/plain")


def test_rejects_invalid_image_bytes(qr_dir: Path):
    with pytest.raises(storage.OfflinePaymentQrValidationError, match="not a valid"):
        storage.save_offline_payment_qr(b"not-an-image", "image/png")


def test_rejects_content_type_mismatch(qr_dir: Path):
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    with pytest.raises(storage.OfflinePaymentQrValidationError, match="does not match"):
        storage.save_offline_payment_qr(png, "image/jpeg")


def test_delete_removes_file(qr_dir: Path):
    storage.save_offline_payment_qr(b"\x89PNG\r\n\x1a\n" + b"x" * 32, "image/png")
    storage.delete_offline_payment_qr()
    assert storage.find_uploaded_qr_path() is None
