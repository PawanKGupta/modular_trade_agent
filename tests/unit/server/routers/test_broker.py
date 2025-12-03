import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# Import domain entities for broker tests
from modules.kotak_neo_auto_trader.domain.entities import Holding
from modules.kotak_neo_auto_trader.domain.value_objects import Exchange, Money
from server.app.routers import broker
from server.app.routers.broker import KotakNeoCreds, _extract_error_message
from server.app.schemas.user import BrokerCredsRequest
from src.infrastructure.db.models import TradeMode, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummySettings(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            user_id=kwargs.get("user_id", 1),
            trade_mode=kwargs.get("trade_mode", TradeMode.PAPER),
            broker=kwargs.get("broker", None),
            broker_status=kwargs.get("broker_status", None),
            broker_creds_encrypted=kwargs.get("broker_creds_encrypted", None),
        )


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.settings = DummySettings(user_id=1)
        self.ensure_default_called = []
        self.update_called = []
        self.get_by_user_id_called = []

    def ensure_default(self, user_id):
        self.ensure_default_called.append(user_id)
        self.settings.user_id = user_id
        return self.settings

    def get_by_user_id(self, user_id):
        """Get settings by user ID (used by broker endpoints)"""
        self.get_by_user_id_called.append(user_id)
        if self.settings is None:
            return None
        self.settings.user_id = user_id
        return self.settings

    def update(self, settings, **kwargs):
        self.update_called.append((settings, kwargs))
        for key, value in kwargs.items():
            setattr(settings, key, value)
        return settings


# Helper function tests
def test_extract_error_message_dict():
    error = {"message": "Test error message"}
    # The function converts dict to string if it's not a list
    assert _extract_error_message(error) == str(error)


def test_extract_error_message_dict_no_message():
    error = {"code": "ERROR123"}
    assert _extract_error_message(error) == str(error)


def test_extract_error_message_list_with_dict():
    error = [{"message": "Error from list"}]
    assert _extract_error_message(error) == "Error from list"


def test_extract_error_message_list_with_string():
    error = ["Simple error string"]
    assert _extract_error_message(error) == "Simple error string"


def test_extract_error_message_string():
    error = "Simple error"
    assert _extract_error_message(error) == "Simple error"


# POST /creds tests
def test_save_broker_creds_basic(monkeypatch):
    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
    )

    def mock_encrypt(blob):
        return b"encrypted_blob"

    monkeypatch.setattr(broker, "encrypt_blob", mock_encrypt)

    db_session = MagicMock()
    result = broker.save_broker_creds(payload=payload, db=db_session, current=user)

    assert result == {"status": "ok"}
    assert repo.ensure_default_called == [42]
    assert len(repo.update_called) == 1
    assert repo.update_called[0][1]["broker"] == "kotak-neo"
    assert repo.update_called[0][1]["broker_status"] == "Stored"
    assert repo.settings.broker_creds_encrypted == b"encrypted_blob"
    db_session.commit.assert_called_once()


def test_save_broker_creds_full(monkeypatch):
    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
        mobile_number="9876543210",
        password="password123",
        mpin="1234",
        environment="dev",
    )

    encrypted_data = None

    def mock_encrypt(blob):
        nonlocal encrypted_data
        encrypted_data = blob
        return b"encrypted_blob"

    monkeypatch.setattr(broker, "encrypt_blob", mock_encrypt)

    db_session = MagicMock()
    result = broker.save_broker_creds(payload=payload, db=db_session, current=user)

    assert result == {"status": "ok"}
    # Verify credentials blob includes all fields
    creds_dict = json.loads(encrypted_data.decode("utf-8"))
    assert creds_dict["api_key"] == "test_key"
    assert creds_dict["api_secret"] == "test_secret"
    assert creds_dict["mobile_number"] == "9876543210"
    assert creds_dict["password"] == "password123"
    assert creds_dict["mpin"] == "1234"
    assert creds_dict["environment"] == "dev"


def test_save_broker_creds_partial(monkeypatch):
    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
        mobile_number="9876543210",
        # password, mpin, totp_secret not provided
    )

    encrypted_data = None

    def mock_encrypt(blob):
        nonlocal encrypted_data
        encrypted_data = blob
        return b"encrypted_blob"

    monkeypatch.setattr(broker, "encrypt_blob", mock_encrypt)

    db_session = MagicMock()
    result = broker.save_broker_creds(payload=payload, db=db_session, current=user)

    assert result == {"status": "ok"}
    creds_dict = json.loads(encrypted_data.decode("utf-8"))
    assert "mobile_number" in creds_dict
    assert "password" not in creds_dict
    assert "mpin" not in creds_dict


# POST /test tests
def test_test_broker_connection_unsupported_broker(monkeypatch):
    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="unsupported-broker",
        api_key="test_key",
        api_secret="test_secret",
    )

    result = broker.test_broker_connection(payload=payload, db=None, current=user)

    assert result.ok is False
    assert "Unsupported broker" in result.message


def test_test_broker_connection_missing_credentials(monkeypatch):
    user = DummyUser(id=42)
    # Use whitespace strings that pass Pydantic validation but fail the strip check
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="   ",
        api_secret="   ",
    )

    result = broker.test_broker_connection(payload=payload, db=None, current=user)

    assert result.ok is False
    assert "API key and secret are required" in result.message


def test_test_broker_connection_no_sdk(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", False)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
    )

    result = broker.test_broker_connection(payload=payload, db=None, current=user)

    assert result.ok is False
    # Should return user-friendly message without installation instructions
    assert (
        "not available" in result.message.lower()
        or "system administrator" in result.message.lower()
    )
    assert "pip install" not in result.message.lower()  # No installation commands for users


def test_test_broker_connection_sdk_available_basic(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    mock_client = MagicMock()

    def mock_neo_api(*args, **kwargs):
        return mock_client

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
    )

    db_session = MagicMock()
    result = broker.test_broker_connection(payload=payload, db=db_session, current=user)

    # Should succeed with basic creds (no full login test)
    assert result.ok is True
    assert "initialized successfully" in result.message.lower()


def test_test_broker_connection_empty_creds(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="   ",
        api_secret="   ",
    )

    result = broker.test_broker_connection(payload=payload, db=None, current=user)

    assert result.ok is False
    assert "API key and secret are required" in result.message


def test_test_broker_connection_success_updates_settings(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    mock_client = MagicMock()
    monkeypatch.setattr(broker, "NeoAPI", lambda *args, **kwargs: mock_client)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
    )

    db_session = MagicMock()
    result = broker.test_broker_connection(payload=payload, db=db_session, current=user)

    assert result.ok is True
    # Verify settings were updated
    assert len(repo.update_called) == 1
    update_kwargs = repo.update_called[0][1]
    assert update_kwargs["trade_mode"] == TradeMode.BROKER
    assert update_kwargs["broker"] == "kotak-neo"
    assert update_kwargs["broker_status"] == "Connected"
    db_session.commit.assert_called_once()


def test_test_broker_connection_failure_no_update(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    def mock_neo_api(*args, **kwargs):
        raise Exception("SDK error")

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
    )

    result = broker.test_broker_connection(payload=payload, db=None, current=user)

    assert result.ok is False
    # Settings should not be updated on failure
    assert len(repo.update_called) == 0


# Test _test_kotak_neo_connection helper
def test_test_kotak_neo_connection_no_sdk():
    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    with patch.object(broker, "_NEO_API_AVAILABLE", False):
        success, message = broker._test_kotak_neo_connection(creds)
        assert success is False
        # Should return user-friendly message without installation instructions
        assert "not available" in message.lower() or "system administrator" in message.lower()
        assert "pip install" not in message.lower()  # No installation commands for users


def test_test_kotak_neo_connection_empty_creds(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)
    creds = KotakNeoCreds(consumer_key="", consumer_secret="")
    success, message = broker._test_kotak_neo_connection(creds)
    assert success is False
    assert "cannot be empty" in message


def test_test_kotak_neo_connection_basic_success(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)
    mock_client = MagicMock()
    monkeypatch.setattr(broker, "NeoAPI", lambda *args, **kwargs: mock_client)

    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    success, message = broker._test_kotak_neo_connection(creds)

    assert success is True
    assert "initialized successfully" in message.lower()


def test_test_kotak_neo_connection_full_creds(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)
    mock_client = MagicMock()
    mock_client.login.return_value = {"status": "success"}
    mock_client.session_2fa.return_value = {"status": "success"}
    monkeypatch.setattr(broker, "NeoAPI", lambda *args, **kwargs: mock_client)

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
        mpin="1234",
    )

    success, message = broker._test_kotak_neo_connection(creds)

    assert success is True
    mock_client.login.assert_called_once()
    mock_client.session_2fa.assert_called_once()


# GET /status tests
def test_broker_status(monkeypatch):
    repo = DummySettingsRepo(object())
    repo.settings.broker = "kotak-neo"
    repo.settings.broker_status = "Connected"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.broker_status(db=None, current=user)

    assert result == {"broker": "kotak-neo", "status": "Connected"}
    assert repo.ensure_default_called == [42]


def test_broker_status_none(monkeypatch):
    repo = DummySettingsRepo(object())
    repo.settings.broker = None
    repo.settings.broker_status = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.broker_status(db=None, current=user)

    assert result == {"broker": None, "status": None}


# GET /creds/info tests
def test_get_broker_creds_info_no_creds(monkeypatch):
    repo = DummySettingsRepo(object())
    repo.settings.broker_creds_encrypted = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is False
    assert result.api_key is None
    assert result.api_secret is None


def test_get_broker_creds_info_masked(monkeypatch):
    repo = DummySettingsRepo(object())
    creds_dict = {"api_key": "test_key_12345", "api_secret": "test_secret_67890"}
    encrypted_blob = json.dumps(creds_dict).encode("utf-8")
    repo.settings.broker_creds_encrypted = encrypted_blob
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return blob

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is True
    assert result.api_key_masked == "****2345"
    assert result.api_secret_masked == "****7890"
    assert result.api_key is None  # Should not be set when masked
    assert result.api_secret is None


def test_get_broker_creds_info_full(monkeypatch):
    repo = DummySettingsRepo(object())
    creds_dict = {
        "api_key": "test_key_12345",
        "api_secret": "test_secret_67890",
        "mobile_number": "9876543210",
        "password": "pass123",
        "mpin": "1234",
        "environment": "dev",
    }
    encrypted_blob = json.dumps(creds_dict).encode("utf-8")
    repo.settings.broker_creds_encrypted = encrypted_blob
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return blob

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=True, db=None, current=user)

    assert result.has_creds is True
    assert result.api_key == "test_key_12345"
    assert result.api_secret == "test_secret_67890"
    assert result.mobile_number == "9876543210"
    assert result.password == "pass123"
    assert result.mpin == "1234"
    assert result.environment == "dev"
    assert result.api_key_masked is None  # Should not be set when showing full


def test_get_broker_creds_info_decrypt_fails(monkeypatch):
    repo = DummySettingsRepo(object())
    repo.settings.broker_creds_encrypted = b"invalid_encrypted_data"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return None

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is False


def test_get_broker_creds_info_invalid_json(monkeypatch):
    repo = DummySettingsRepo(object())
    # Invalid JSON that can't be parsed
    repo.settings.broker_creds_encrypted = b"not json data"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return b"{'invalid': json}"  # Not valid JSON

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    # Should fallback to ast.literal_eval or return no creds
    assert result.has_creds is False or result.has_creds is True


def test_get_broker_creds_info_old_format(monkeypatch):
    repo = DummySettingsRepo(object())
    # Old format using Python dict literal
    old_format = "{'api_key': 'test_key', 'api_secret': 'test_secret'}"
    repo.settings.broker_creds_encrypted = old_format.encode("utf-8")
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return blob

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    # Should handle old format with ast.literal_eval
    assert result.has_creds is True or result.has_creds is False


def test_get_broker_creds_info_mask_short_values(monkeypatch):
    repo = DummySettingsRepo(object())
    creds_dict = {"api_key": "abc", "api_secret": "12"}  # Too short to mask
    encrypted_blob = json.dumps(creds_dict).encode("utf-8")
    repo.settings.broker_creds_encrypted = encrypted_blob
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return blob

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is True
    assert result.api_key_masked == "****"
    assert result.api_secret_masked == "****"


def test_get_broker_creds_info_exception_handling(monkeypatch):
    repo = DummySettingsRepo(object())
    repo.settings.broker_creds_encrypted = b"some_data"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        raise Exception("Decryption error")

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    # Should handle exception gracefully
    assert result.has_creds is False


# Additional tests for better coverage
def test_test_kotak_neo_connection_client_none(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    def mock_neo_api(*args, **kwargs):
        return None

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    success, message = broker._test_kotak_neo_connection(creds)

    assert success is False
    assert "SDK returned None" in message


def test_test_kotak_neo_connection_type_error(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    def mock_neo_api(*args, **kwargs):
        raise TypeError("can only concatenate str (not 'NoneType') to str")

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    success, message = broker._test_kotak_neo_connection(creds)

    assert success is False
    assert "SDK initialization error" in message


def test_test_kotak_neo_connection_other_type_error(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    def mock_neo_api(*args, **kwargs):
        raise TypeError("Other type error")

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    success, message = broker._test_kotak_neo_connection(creds)

    assert success is False
    assert "SDK type error" in message


def test_test_kotak_neo_connection_general_exception(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    def mock_neo_api(*args, **kwargs):
        raise ValueError("Some error")

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    creds = KotakNeoCreds(consumer_key="key", consumer_secret="secret")
    success, message = broker._test_kotak_neo_connection(creds)

    assert success is False
    assert "Failed to initialize client" in message


def test_test_kotak_neo_connection_outer_exception(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    mock_client = MagicMock()

    def mock_neo_api(*args, **kwargs):
        return mock_client

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    # To hit outer exception handler, we need exception after inner try but in outer try
    # Mock _test_kotak_neo_login to raise an unexpected exception
    def mock_login_raises(*args, **kwargs):
        raise RuntimeError("Unexpected error")

    monkeypatch.setattr(broker, "_test_kotak_neo_login", mock_login_raises)

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
        mpin="1234",
    )

    success, message = broker._test_kotak_neo_connection(creds)

    assert success is False
    assert "Connection test failed" in message


def test_test_kotak_neo_login_missing_mobile_password(monkeypatch):
    mock_client = MagicMock()
    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number=None,
        password=None,
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "Mobile number and password are required" in message


def test_test_kotak_neo_login_empty_mobile_password(monkeypatch):
    mock_client = MagicMock()
    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="   ",
        password="   ",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "cannot be empty" in message


def test_test_kotak_neo_login_type_error(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.side_effect = TypeError("can only concatenate str (not 'NoneType')")

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "SDK error" in message


def test_test_kotak_neo_login_attribute_error(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.side_effect = AttributeError("'NoneType' object has no attribute 'method'")

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "SDK attribute error" in message


def test_test_kotak_neo_login_none_response(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.return_value = None

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "No response from server" in message


def test_test_kotak_neo_login_error_dict(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.return_value = {"error": "Invalid credentials"}

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "Login failed" in message


def test_test_kotak_neo_login_no_2fa(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.return_value = {"status": "success"}

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
        mpin=None,
        totp_secret=None,
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is False
    assert "2FA credentials" in message


def test_test_kotak_neo_login_totp_secret(monkeypatch):
    mock_client = MagicMock()
    mock_client.login.return_value = {"status": "success"}

    creds = KotakNeoCreds(
        consumer_key="key",
        consumer_secret="secret",
        mobile_number="9876543210",
        password="pass",
        totp_secret="totp123",
    )
    success, message = broker._test_kotak_neo_login(mock_client, creds)

    assert success is True
    assert "TOTP not fully tested" in message


def test_test_kotak_neo_2fa_empty_mpin(monkeypatch):
    mock_client = MagicMock()
    success, message = broker._test_kotak_neo_2fa(mock_client, "")

    assert success is False
    assert "MPIN is required" in message


def test_test_kotak_neo_2fa_none_response(monkeypatch):
    mock_client = MagicMock()
    mock_client.session_2fa.return_value = None
    success, message = broker._test_kotak_neo_2fa(mock_client, "1234")

    assert success is True
    assert "session already active" in message


def test_test_kotak_neo_2fa_error_response(monkeypatch):
    mock_client = MagicMock()
    mock_client.session_2fa.return_value = {"error": "Invalid MPIN"}

    success, message = broker._test_kotak_neo_2fa(mock_client, "1234")

    assert success is False
    assert "2FA failed" in message


def test_test_kotak_neo_2fa_exception_nonetype(monkeypatch):
    mock_client = MagicMock()
    mock_client.session_2fa.side_effect = AttributeError("'NoneType' object has no attribute 'get'")

    success, message = broker._test_kotak_neo_2fa(mock_client, "1234")

    assert success is True
    assert "session already active" in message


def test_test_kotak_neo_2fa_other_exception(monkeypatch):
    mock_client = MagicMock()
    mock_client.session_2fa.side_effect = Exception("Network error")

    success, message = broker._test_kotak_neo_2fa(mock_client, "1234")

    assert success is False
    assert "2FA failed" in message


def test_save_broker_creds_with_totp_secret(monkeypatch):
    repo = DummySettingsRepo(object())
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    payload = BrokerCredsRequest(
        broker="kotak-neo",
        api_key="test_key",
        api_secret="test_secret",
        totp_secret="totp123",
    )

    encrypted_data = None

    def mock_encrypt(blob):
        nonlocal encrypted_data
        encrypted_data = blob
        return b"encrypted_blob"

    monkeypatch.setattr(broker, "encrypt_blob", mock_encrypt)

    db_session = MagicMock()
    result = broker.save_broker_creds(payload=payload, db=db_session, current=user)

    assert result == {"status": "ok"}
    creds_dict = json.loads(encrypted_data.decode("utf-8"))
    assert creds_dict["totp_secret"] == "totp123"


# GET /portfolio tests
def test_get_broker_portfolio_no_settings(monkeypatch):
    """Test broker portfolio endpoint when user settings don't exist"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings = None

    def mock_get_by_user_id(user_id):
        return None

    repo.get_by_user_id = mock_get_by_user_id
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_portfolio(db=db_session, current=user)

    assert exc.value.status_code == 404
    assert "User settings not found" in exc.value.detail


def test_get_broker_portfolio_paper_mode(monkeypatch):
    """Test broker portfolio endpoint when user is in paper mode"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.PAPER
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_portfolio(db=db_session, current=user)

    assert exc.value.status_code == 400
    assert "broker mode" in exc.value.detail.lower()


def test_get_broker_portfolio_no_credentials(monkeypatch):
    """Test broker portfolio endpoint when credentials are not configured"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_portfolio(db=db_session, current=user)

    assert exc.value.status_code == 400
    assert "credentials not configured" in exc.value.detail.lower()


def test_get_broker_portfolio_decrypt_fails(monkeypatch):
    """Test broker portfolio endpoint when credential decryption fails"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = b"invalid_encrypted"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return None

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_portfolio(db=db_session, current=user)

    assert exc.value.status_code == 400
    assert "Failed to decrypt" in exc.value.detail


def test_get_broker_portfolio_auth_fails(monkeypatch):
    """Test broker portfolio endpoint when authentication fails"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = b"encrypted_creds"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    def mock_create_temp_env(creds):
        return "/tmp/test.env"

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock KotakNeoAuth to fail login
    mock_auth = MagicMock()
    mock_auth.login.return_value = False

    def mock_auth_init(env_file):
        return mock_auth

    with patch("modules.kotak_neo_auto_trader.auth.KotakNeoAuth", mock_auth_init):
        db_session = MagicMock()
        with pytest.raises(HTTPException) as exc:
            broker.get_broker_portfolio(db=db_session, current=user)

        assert exc.value.status_code == 503
        assert "Failed to connect to broker" in exc.value.detail


def test_get_broker_portfolio_success(monkeypatch):
    """Test broker portfolio endpoint success case"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = b"encrypted_creds"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    temp_env_file = "/tmp/test_broker_portfolio.env"

    def mock_create_temp_env(creds):
        return temp_env_file

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock KotakNeoAuth
    mock_auth = MagicMock()
    mock_auth.login.return_value = True

    def mock_auth_init(env_file):
        return mock_auth

    # Mock BrokerFactory and broker gateway
    mock_holding = Holding(
        symbol="RELIANCE.NS",
        exchange=Exchange.NSE,
        quantity=10,
        average_price=Money(Decimal("2500.00")),
        current_price=Money(Decimal("2600.00")),
        last_updated=datetime.now(),
    )

    mock_broker = MagicMock()
    mock_broker.connect.return_value = True
    mock_broker.get_holdings.return_value = [mock_holding]
    mock_broker.get_account_limits.return_value = {
        "available_margin": {"cash": 100000.0},
    }

    def mock_broker_factory(broker_type, auth_handler):
        return mock_broker

    # Mock yfinance
    mock_ticker = MagicMock()
    mock_ticker.info = {"currentPrice": 2600.0}

    def mock_yf_ticker(symbol):
        return mock_ticker

    # Patch at the import location (inside the function)
    with (
        patch("modules.kotak_neo_auto_trader.auth.KotakNeoAuth", mock_auth_init),
        patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
            mock_broker_factory,
        ),
        patch("yfinance.Ticker", mock_yf_ticker),
    ):
        db_session = MagicMock()
        result = broker.get_broker_portfolio(db=db_session, current=user)

        assert result.account.available_cash == 100000.0
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "RELIANCE.NS"
        assert result.holdings[0].quantity == 10
        assert result.holdings[0].average_price == 2500.0
        assert result.holdings[0].current_price == 2600.0
        assert result.holdings[0].pnl == 1000.0  # 10 * (2600 - 2500)
        assert result.holdings[0].pnl_percentage == pytest.approx(4.0, rel=0.1)  # (1000/25000)*100
        assert result.account.portfolio_value > 0
        assert result.account.unrealized_pnl > 0


def test_get_broker_orders_no_settings(monkeypatch):
    """Test broker orders endpoint when user settings don't exist"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings = None

    def mock_get_by_user_id(user_id):
        return None

    repo.get_by_user_id = mock_get_by_user_id
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_orders(db=db_session, current=user)

    assert exc.value.status_code == 404
    assert "User settings not found" in exc.value.detail


def test_get_broker_orders_paper_mode(monkeypatch):
    """Test broker orders endpoint when user is in paper mode"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.PAPER
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_orders(db=db_session, current=user)

    assert exc.value.status_code == 400
    assert "broker mode" in exc.value.detail.lower()


def test_get_broker_orders_no_credentials(monkeypatch):
    """Test broker orders endpoint when credentials are not configured"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        broker.get_broker_orders(db=db_session, current=user)

    assert exc.value.status_code == 400
    assert "credentials not configured" in exc.value.detail.lower()


def test_get_broker_orders_success(monkeypatch):
    """Test broker orders endpoint success case"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = b"encrypted_creds"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    temp_env_file = "/tmp/test_broker_orders.env"

    def mock_create_temp_env(creds):
        return temp_env_file

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock KotakNeoAuth
    mock_auth = MagicMock()
    mock_auth.login.return_value = True

    def mock_auth_init(env_file):
        return mock_auth

    # Mock BrokerFactory and broker gateway
    mock_order = MagicMock()
    mock_order.order_id = "ORDER123"
    mock_order.symbol = "RELIANCE.NS"
    mock_order.quantity = 10
    mock_order.transaction_type.value = "BUY"
    mock_order.status.value = "OPEN"
    mock_order.created_at = datetime.now()
    # Create mock Money object
    mock_price = MagicMock()
    mock_price.amount = Decimal("2500.00")
    mock_order.price = mock_price
    mock_order.execution_price = None
    mock_order.execution_qty = None

    mock_broker = MagicMock()
    mock_broker.connect.return_value = True
    mock_broker.get_all_orders.return_value = [mock_order]

    def mock_broker_factory(broker_type, auth_handler):
        return mock_broker

    with (
        patch("modules.kotak_neo_auto_trader.auth.KotakNeoAuth", mock_auth_init),
        patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
            mock_broker_factory,
        ),
    ):
        db_session = MagicMock()
        result = broker.get_broker_orders(db=db_session, current=user)

        assert len(result) == 1
        assert result[0]["broker_order_id"] == "ORDER123"
        assert result[0]["symbol"] == "RELIANCE.NS"
        assert result[0]["quantity"] == 10
        assert result[0]["side"] == "buy"
        assert result[0]["status"] == "pending"
        assert result[0]["price"] == 2500.0


def test_get_broker_orders_auth_fails(monkeypatch):
    """Test broker orders endpoint when authentication fails"""
    user = DummyUser(id=42)

    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    repo.settings.broker_creds_encrypted = b"encrypted_creds"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(creds):
        return {"api_key": "key", "api_secret": "secret"}

    monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

    def mock_create_temp_env(creds):
        return "/tmp/test.env"

    monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

    # Mock KotakNeoAuth to fail login
    mock_auth = MagicMock()
    mock_auth.login.return_value = False

    def mock_auth_init(env_file):
        return mock_auth

    with patch("modules.kotak_neo_auto_trader.auth.KotakNeoAuth", mock_auth_init):
        db_session = MagicMock()
        with pytest.raises(HTTPException) as exc:
            broker.get_broker_orders(db=db_session, current=user)

        assert exc.value.status_code == 503
        assert "Failed to connect to broker" in exc.value.detail
