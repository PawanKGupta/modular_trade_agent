"""
Versioned verdict feature contract emitted at sklearn training time and validated at inference.

Paired artifact: `{model_stem}.verdict_features.json` next to `{model_stem}.pkl`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ARTIFACT_KIND = "modular_trade_agent.verdict_features"
VERDICT_FEATURE_SCHEMA_VERSION = 1


def verdict_feature_manifest_path(model_path: Path | str) -> Path:
    """Path to JSON manifest beside the pickled verdict model."""
    p = Path(model_path).resolve()
    return p.with_name(f"{p.stem}.verdict_features.json")


def write_verdict_feature_manifest(
    model_path: Path | str,
    feature_names: list[str],
    *,
    label_classes: list[str] | None = None,
) -> Path:
    """
    Write a versioned manifest listing exact training column order for serve-time alignment.

    Args:
        model_path: Path to the joblib verdict classifier (``.pkl``).
        feature_names: Ordered feature columns used as ``X`` for ``fit``.

    Returns:
        Path to the manifest file written.

    Raises:
        ValueError: If ``feature_names`` is empty or not a flat list of non-empty strings.
    """
    if not feature_names or not all(isinstance(n, str) and n.strip() for n in feature_names):
        raise ValueError("feature_names must be a non-empty list of non-empty strings")

    manifest_path = verdict_feature_manifest_path(model_path)
    payload: dict[str, Any] = {
        "artifact": ARTIFACT_KIND,
        "feature_schema_version": VERDICT_FEATURE_SCHEMA_VERSION,
        "feature_names": list(feature_names),
    }
    if label_classes is not None:
        if not label_classes or not all(isinstance(c, str) and c.strip() for c in label_classes):
            raise ValueError("label_classes must be a non-empty list of non-empty strings")
        payload["label_classes"] = list(label_classes)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "Wrote verdict feature manifest (%s names, schema v%s): %s",
        len(feature_names),
        VERDICT_FEATURE_SCHEMA_VERSION,
        manifest_path.name,
    )
    return manifest_path


def load_verdict_feature_manifest(model_path: Path | str) -> dict[str, Any] | None:
    """
    Load and validate a verdict feature manifest if present beside the pickle.

    Returns:
        Dict with keys ``feature_names`` (list[str]) and ``feature_schema_version`` (int),
        or None if absent, invalid JSON, unknown schema, or wrong artifact kind.
    """
    path = verdict_feature_manifest_path(model_path)
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        logger.warning("Unreadable verdict feature manifest %s: %s", path, e)
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
    if schema != VERDICT_FEATURE_SCHEMA_VERSION:
        logger.warning(
            "Unsupported verdict feature schema_version=%r in %s (supported: %s); "
            "falling back to legacy feature discovery.",
            schema,
            path.name,
            VERDICT_FEATURE_SCHEMA_VERSION,
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

    out: dict[str, Any] = {
        "feature_names": names,
        "feature_schema_version": int(schema),
    }
    raw_labels = data.get("label_classes")
    if raw_labels is not None:
        if (
            isinstance(raw_labels, list)
            and len(raw_labels) > 0
            and all(isinstance(x, str) and x.strip() for x in raw_labels)
        ):
            out["label_classes"] = [str(x) for x in raw_labels]
        else:
            logger.warning(
                "Invalid label_classes in manifest %s (expected non-empty list of strings)",
                path.name,
            )
    return out
