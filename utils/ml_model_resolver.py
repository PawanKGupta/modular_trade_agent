"""
ML Model Path Resolver

Helper functions to resolve ML model paths from version strings.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from src.infrastructure.db.models import MLModel
from utils.logger import logger


def get_model_path_from_version(db: Session, model_type: str, version: str | None) -> str | None:
    """
    Get model path from version string (e.g., "v1.0", "v2.0").

    Args:
        db: Database session
        model_type: "verdict_classifier" or "price_regressor"
        version: Version string like "v1.0" or None

    Returns:
        Model path if found, None otherwise
    """
    if not version:
        return None

    try:
        # Query database for model with this version
        from sqlalchemy import select

        stmt = select(MLModel).where(
            MLModel.model_type == model_type,
            MLModel.version == version,
        )
        model = db.execute(stmt).scalar_one_or_none()

        if model and model.model_path:
            model_path = Path(model.model_path)
            if model_path.exists():
                logger.debug(f"Found model path for {model_type} v{version}: {model_path}")
                return str(model_path)
            else:
                logger.warning(f"Model path from database doesn't exist: {model_path}")
        else:
            logger.debug(f"No model found in database for {model_type} v{version}")

    except Exception as e:
        logger.warning(f"Error resolving model path from version {version}: {e}")

    return None


def get_active_model_path(db: Session, model_type: str) -> str | None:
    """
    Get path to active model for given type.

    Args:
        db: Database session
        model_type: "verdict_classifier" or "price_regressor"

    Returns:
        Model path if found, None otherwise
    """
    try:
        from sqlalchemy import select

        stmt = select(MLModel).where(
            MLModel.model_type == model_type,
            MLModel.is_active == True,
        )
        model = db.execute(stmt).scalar_one_or_none()

        if model and model.model_path:
            model_path = Path(model.model_path)
            if model_path.exists():
                logger.debug(f"Found active model path for {model_type}: {model_path}")
                return str(model_path)
            else:
                logger.warning(f"Active model path from database doesn't exist: {model_path}")
        else:
            logger.debug(f"No active model found in database for {model_type}")

    except Exception as e:
        logger.warning(f"Error getting active model path: {e}")

    return None
