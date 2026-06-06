"""
Resolve ML price target/stop model paths and detect on-disk availability.

Production often enables ``ml_price_enabled`` while only the verdict classifier
(``models/verdict_model_random_forest.pkl``) is deployed. Training writes
``price_model_<type>_<target>.pkl``; this module discovers those files and the
canonical default name.
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.logger import logger

# Canonical default expected by StrategyConfig / docs (may not exist until trained).
DEFAULT_ML_PRICE_TARGET_FILENAME = "price_model_random_forest.pkl"
DEFAULT_ML_PRICE_TARGET_PATH = Path("models") / DEFAULT_ML_PRICE_TARGET_FILENAME


def project_models_dir() -> Path:
    """``models/`` directory relative to repo root (``PROJECT_ROOT`` or cwd)."""
    root = os.getenv("PROJECT_ROOT", "").strip()
    base = Path(root) if root else Path.cwd()
    return (base / "models").resolve()


def discover_ml_price_target_path(
    *,
    configured_path: str | None = None,
    db_session: object | None = None,
) -> Path | None:
    """
    Return the first existing price-target model file, or None.

    Order: explicit path → active ``price_regressor`` in DB → canonical default
    → any ``models/price_model_*.pkl`` (newest mtime).
    """
    candidates: list[Path] = []

    if configured_path and str(configured_path).strip():
        candidates.append(Path(configured_path.strip()))

    if db_session is not None:
        try:
            from utils.ml_model_resolver import get_active_model_path  # noqa: PLC0415

            active = get_active_model_path(db_session, "price_regressor")
            if active:
                candidates.append(Path(active))
        except Exception as exc:
            logger.debug("Could not resolve active price_regressor model: %s", exc)

    models_dir = project_models_dir()
    candidates.append(models_dir / DEFAULT_ML_PRICE_TARGET_FILENAME)

    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved

    globbed = sorted(
        models_dir.glob("price_model_*.pkl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return globbed[0] if globbed else None


def resolve_ml_price_target_path_str(
    *,
    configured_path: str | None = None,
    db_session: object | None = None,
) -> str:
    """Path string for StrategyConfig (discovered file or canonical default)."""
    found = discover_ml_price_target_path(configured_path=configured_path, db_session=db_session)
    if found is not None:
        return str(found)
    if configured_path and str(configured_path).strip():
        return str(configured_path).strip()
    return str(DEFAULT_ML_PRICE_TARGET_PATH)


def ml_price_target_model_available(
    *,
    configured_path: str | None = None,
    db_session: object | None = None,
) -> bool:
    """True when a price-target ``.pkl`` exists at a resolved location."""
    return (
        discover_ml_price_target_path(configured_path=configured_path, db_session=db_session)
        is not None
    )


def ml_stop_loss_model_available(configured_path: str | None) -> bool:
    """True when optional stop-loss model path exists."""
    if not configured_path or not str(configured_path).strip():
        return False
    return Path(configured_path.strip()).is_file()
