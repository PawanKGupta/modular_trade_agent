from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, UserSettings


class SettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> UserSettings | None:
        return self.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    def ensure_default(self, user_id: int) -> UserSettings:
        settings = self.get_by_user_id(user_id)
        if settings:
            return settings
        settings = UserSettings(user_id=user_id, trade_mode=TradeMode.PAPER)
        self.db.add(settings)
        try:
            self.db.commit()
        except Exception as e:
            print(f"[SettingsRepository] commit failed for user_id={user_id}: {e}")
            raise
        self.db.refresh(settings)
        return settings

    def update(
        self,
        settings: UserSettings,
        *,
        trade_mode: TradeMode | None = None,
        broker: str | None = None,
        broker_status: str | None = None,
        broker_creds_encrypted: bytes | None = None,
        ui_preferences: dict | None = None,
    ) -> UserSettings:
        if trade_mode is not None:
            settings.trade_mode = trade_mode
        if broker is not None:
            settings.broker = broker
        if broker_status is not None:
            settings.broker_status = broker_status
        if broker_creds_encrypted is not None:
            settings.broker_creds_encrypted = broker_creds_encrypted
        if ui_preferences is not None:
            settings.ui_preferences = ui_preferences
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_ui_preferences(self, user_id: int) -> dict:
        """Get UI preferences for a user, returning empty dict if not set."""
        settings = self.get_by_user_id(user_id)
        if settings and settings.ui_preferences:
            return settings.ui_preferences
        return {}

    def update_ui_preferences(self, user_id: int, preferences: dict) -> dict:
        """Update UI preferences for a user, merging with existing preferences."""
        settings = self.ensure_default(user_id)
        current_prefs = settings.ui_preferences or {}
        # Merge with existing preferences
        merged_prefs = {**current_prefs, **preferences}
        settings = self.update(settings, ui_preferences=merged_prefs)
        return settings.ui_preferences or {}
