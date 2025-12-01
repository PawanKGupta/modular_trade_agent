"""Repository for UserTradingConfig management"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserTradingConfig
from src.infrastructure.db.timezone_utils import ist_now


class UserTradingConfigRepository:
    """Repository for managing user-specific trading configurations"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> UserTradingConfig | None:
        """Get trading config for a user"""
        return self.db.query(UserTradingConfig).filter(UserTradingConfig.user_id == user_id).first()

    def get_or_create_default(self, user_id: int) -> UserTradingConfig:
        """Get or create default trading config for a user"""
        config = self.get(user_id)
        if not config:
            config = UserTradingConfig(user_id=user_id)
            # All fields have defaults in the model, so we can just create it
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config

    def create(self, user_id: int, **kwargs) -> UserTradingConfig:
        """Create a new trading config for a user"""
        # Check if config already exists
        existing = self.get(user_id)
        if existing:
            raise ValueError(f"Trading config already exists for user {user_id}")

        config = UserTradingConfig(user_id=user_id, **kwargs)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update(self, user_id: int, **kwargs) -> UserTradingConfig:
        """Update trading config for a user"""
        config = self.get_or_create_default(user_id)

        # Update only provided fields
        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        config.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(config)
        return config

    def reset_to_defaults(self, user_id: int) -> UserTradingConfig:
        """Reset trading config to default values"""
        config = self.get(user_id)
        if config:
            # Delete existing config
            self.db.delete(config)
            self.db.commit()

        # Create new config with defaults
        return self.get_or_create_default(user_id)

    def delete(self, user_id: int) -> None:
        """Delete trading config for a user"""
        config = self.get(user_id)
        if config:
            self.db.delete(config)
            self.db.commit()
