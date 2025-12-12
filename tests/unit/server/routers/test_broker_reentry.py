"""Tests for reentry data in broker portfolio endpoint"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from server.app.routers import broker
from src.infrastructure.db.models import Positions, TradeMode, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.settings = SimpleNamespace(
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=b"encrypted_creds",
        )

    def get_by_user_id(self, user_id):
        return self.settings


class DummyPositionsRepository:
    def __init__(self, db):
        self.db = db
        self.positions = {}

    def get_by_symbol(self, user_id, symbol):
        return self.positions.get((user_id, symbol.upper()))


class DummyBroker:
    def __init__(self):
        self._connected = True

    def connect(self):
        return True

    def get_holdings(self):
        from modules.kotak_neo_auto_trader.domain import (  # noqa: PLC0415
            Exchange,
            Holding,
            Money,
        )

        return [
            Holding(
                symbol="RELIANCE-EQ",
                quantity=10.0,
                average_price=Money(amount=2500.0, currency="INR"),
                exchange=Exchange.NSE,
            )
        ]

    def get_available_cash(self):
        return 50000.0


def test_get_broker_portfolio_with_reentry_data(monkeypatch):
    """Test that reentry data is fetched from positions table and included in broker holdings"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    def mock_create_temp_env(creds):
        return "/tmp/test.env"

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock auth session
    mock_auth = MagicMock()
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_client.return_value = MagicMock()

    def mock_get_auth_session(user_id, temp_env_file, db):
        return mock_auth

    monkeypatch.setattr(broker, "_get_or_create_auth_session", mock_get_auth_session)

    # Mock broker factory
    mock_broker = DummyBroker()

    def mock_broker_factory_create(broker_type, auth_handler=None):
        return mock_broker

    monkeypatch.setattr(
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
        mock_broker_factory_create,
    )

    # Mock positions repository with reentry data
    mock_position = MagicMock(spec=Positions)
    mock_position.reentry_count = 2
    mock_position.entry_rsi = 28.5
    mock_position.initial_entry_price = 2500.0
    mock_position.reentries = {
        "reentries": [
            {
                "qty": 5,
                "price": 2400.0,
                "time": "2025-01-15T10:00:00",
                "level": 20,
                "rsi": 18.5,
            },
            {
                "qty": 3,
                "price": 2300.0,
                "time": "2025-01-20T10:00:00",
                "level": 10,
                "rsi": 9.2,
            },
        ]
    }

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance for current price
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        db_session = MagicMock()
        result = broker.get_broker_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        assert holding.symbol == "RELIANCE-EQ"
        assert holding.reentry_count == 2
        assert holding.entry_rsi == 28.5
        assert holding.initial_entry_price == 2500.0
        assert holding.reentries is not None
        assert len(holding.reentries) == 2
        assert holding.reentries[0]["qty"] == 5
        assert holding.reentries[0]["price"] == 2400.0
        assert holding.reentries[1]["qty"] == 3


def test_get_broker_portfolio_without_reentry_data(monkeypatch):
    """Test that broker holdings without reentry data return defaults"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    def mock_create_temp_env(creds):
        return "/tmp/test.env"

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock auth session
    mock_auth = MagicMock()
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_client.return_value = MagicMock()

    def mock_get_auth_session(user_id, temp_env_file, db):
        return mock_auth

    monkeypatch.setattr(broker, "_get_or_create_auth_session", mock_get_auth_session)

    # Mock broker factory
    mock_broker = DummyBroker()

    def mock_broker_factory_create(broker_type, auth_handler=None):
        return mock_broker

    monkeypatch.setattr(
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
        mock_broker_factory_create,
    )

    # Mock positions repository - no position found
    positions_repo = DummyPositionsRepository(None)

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance for current price
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        db_session = MagicMock()
        result = broker.get_broker_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        # Should have default values
        assert holding.reentry_count == 0
        assert holding.entry_rsi is None
        assert holding.initial_entry_price is None
        assert holding.reentries is None


def test_get_broker_portfolio_reentry_data_symbol_normalization(monkeypatch):
    """Test that symbol normalization works correctly for broker holdings"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    def mock_create_temp_env(creds):
        return "/tmp/test.env"

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock auth session
    mock_auth = MagicMock()
    mock_auth.is_authenticated.return_value = True
    mock_auth.get_client.return_value = MagicMock()

    def mock_get_auth_session(user_id, temp_env_file, db):
        return mock_auth

    monkeypatch.setattr(broker, "_get_or_create_auth_session", mock_get_auth_session)

    # Mock broker factory
    mock_broker = DummyBroker()

    def mock_broker_factory_create(broker_type, auth_handler=None):
        return mock_broker

    monkeypatch.setattr(
        "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
        mock_broker_factory_create,
    )

    # Mock positions repository - position stored as "RELIANCE" (normalized)
    mock_position = MagicMock(spec=Positions)
    mock_position.reentry_count = 1
    mock_position.entry_rsi = 28.0
    mock_position.initial_entry_price = 2500.0
    mock_position.reentries = {
        "reentries": [{"qty": 5, "price": 2400.0, "time": "2025-01-15T10:00:00"}]
    }

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance for current price
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        db_session = MagicMock()
        result = broker.get_broker_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        # RELIANCE-EQ should match RELIANCE in database
        assert holding.symbol == "RELIANCE-EQ"
        assert holding.reentry_count == 1
        assert holding.entry_rsi == 28.0
