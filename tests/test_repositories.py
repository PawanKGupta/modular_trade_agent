from src.infrastructure.db.models import TradeMode, UserRole
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository


def test_user_and_settings_repos(db_session):
    ur = UserRepository(db_session)
    user = ur.create_user(email="u@example.com", password="Secret123", name="U", role=UserRole.USER)
    assert user.id is not None
    assert user.role == UserRole.USER

    sr = SettingsRepository(db_session)
    settings = sr.ensure_default(user.id)
    assert settings.user_id == user.id
    assert settings.trade_mode == TradeMode.PAPER

    # Update settings
    sr.update(settings, trade_mode=TradeMode.BROKER, broker="kotak-neo")
    assert settings.trade_mode == TradeMode.BROKER
    assert settings.broker == "kotak-neo"
