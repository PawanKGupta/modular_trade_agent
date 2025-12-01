"""Repository for MLModel management"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import MLModel


class MLModelRepository:
    """Repository for managing ML model versioning"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        model_type: str,
        version: str,
        model_path: str,
        training_job_id: int,
        created_by: int,
        accuracy: float | None = None,
        is_active: bool = False,
    ) -> MLModel:
        """Create a new ML model"""
        model = MLModel(
            model_type=model_type,
            version=version,
            model_path=model_path,
            training_job_id=training_job_id,
            created_by=created_by,
            accuracy=accuracy,
            is_active=is_active,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get(self, model_id: int) -> MLModel | None:
        """Get model by ID"""
        return self.db.get(MLModel, model_id)

    def get_by_type_version(self, model_type: str, version: str) -> MLModel | None:
        """Get model by type and version"""
        stmt = select(MLModel).where(
            MLModel.model_type == model_type,
            MLModel.version == version,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active(self, model_type: str) -> MLModel | None:
        """Get active model for a type"""
        stmt = select(MLModel).where(
            MLModel.model_type == model_type,
            MLModel.is_active == True,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        model_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[MLModel]:
        """List models with filters"""
        stmt = select(MLModel)

        if model_type:
            stmt = stmt.where(MLModel.model_type == model_type)
        if is_active is not None:
            stmt = stmt.where(MLModel.is_active == is_active)

        stmt = stmt.order_by(MLModel.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def set_active(self, model_id: int, deactivate_others: bool = True) -> MLModel:
        """Set a model as active (optionally deactivate others of same type)"""
        model = self.get(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        if deactivate_others:
            # Deactivate all other models of the same type
            stmt = select(MLModel).where(
                MLModel.model_type == model.model_type,
                MLModel.id != model_id,
            )
            other_models = list(self.db.execute(stmt).scalars().all())
            for other_model in other_models:
                other_model.is_active = False

        model.is_active = True
        self.db.commit()
        self.db.refresh(model)
        return model
