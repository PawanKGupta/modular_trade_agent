"""
Versioned price-target feature contract emitted at training time and validated at inference.

Paired artifact: ``{model_stem}.price_features.json`` next to ``{model_stem}.pkl``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ARTIFACT_KIND = "modular_trade_agent.price_features"
PRICE_FEATURE_SCHEMA_VERSION = 1


def price_feature_manifest_path(model_path: Path | str) -> Path:
    """Path to JSON manifest beside the pickled price regressor."""
    p = Path(model_path).resolve()
    return p.with_name(f"{p.stem}.price_features.json")


def write_price_feature_manifest(
    model_path: Path | str,
    feature_names: list[str],
) -> Path:
    """
    Write a versioned manifest listing exact training column order for serve-time alignment.

    Args:
        model_path: Path to the joblib price regressor (``.pkl``).
        feature_names: Ordered feature columns used as ``X`` for ``fit``.

    Returns:
        Path to the manifest file written.

    Raises:
        ValueError: If ``feature_names`` is empty or not a flat list of non-empty strings.
    """
    if not feature_names or not all(isinstance(n, str) and n.strip() for n in feature_names):
        raise ValueError("feature_names must be a non-empty list of non-empty strings")

    manifest_path = price_feature_manifest_path(model_path)
    payload: dict[str, Any] = {
        "artifact": ARTIFACT_KIND,
        "feature_schema_version": PRICE_FEATURE_SCHEMA_VERSION,
        "feature_names": list(feature_names),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "Wrote price feature manifest (%s names, schema v%s): %s",
        len(feature_names),
        PRICE_FEATURE_SCHEMA_VERSION,
        manifest_path.name,
    )
    return manifest_path


def load_price_feature_manifest(model_path: Path | str) -> dict[str, Any] | None:
    """
    Load and validate a price feature manifest if present beside the pickle.

    Returns:
        Dict with keys ``feature_names`` (list[str]) and ``feature_schema_version`` (int),
        or None if absent, invalid JSON, unknown schema, or wrong artifact kind.
    """
    path = price_feature_manifest_path(model_path)
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        logger.warning("Unreadable price feature manifest %s: %s", path, e)
        return None

    if data.get("artifact") != ARTIFACT_KIND:
        logger.debug(
            "Skipping manifest %s: artifact=%r (expected %s)",
            path.name,
            data.get("artifact"),
            ARTIFACT_KIND,
        )
        return None

    schema = data.get("feature_schema_version")
    if schema != PRICE_FEATURE_SCHEMA_VERSION:
        logger.warning(
            "Unsupported price feature schema_version=%r in %s (supported: %s); "
            "falling back to legacy column order.",
            schema,
            path.name,
            PRICE_FEATURE_SCHEMA_VERSION,
        )
        return None

    names = data.get("feature_names")
    if (
        not isinstance(names, list)
        or len(names) == 0
        or not all(isinstance(x, str) and x.strip() for x in names)
    ):
        logger.warning(
            "Invalid feature_names in manifest %s (expected non-empty list of strings)",
            path.name,
        )
        return None

    return {
        "feature_names": names,
        "feature_schema_version": int(schema),
    }
