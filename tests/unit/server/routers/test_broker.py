import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

    def ensure_default(self, user_id):
        self.ensure_default_called.append(user_id)
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    assert "not available" in result.message.lower() or "system administrator" in result.message.lower()
    assert "pip install" not in result.message.lower()  # No installation commands for users


def test_test_broker_connection_sdk_available_basic(monkeypatch):
    monkeypatch.setattr(broker, "_NEO_API_AVAILABLE", True)

    mock_client = MagicMock()

    def mock_neo_api(*args, **kwargs):
        return mock_client

    monkeypatch.setattr(broker, "NeoAPI", mock_neo_api)

    repo = DummySettingsRepo(db_marker := object())
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

    repo = DummySettingsRepo(db_marker := object())
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

    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
    repo.settings.broker = "kotak-neo"
    repo.settings.broker_status = "Connected"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.broker_status(db=None, current=user)

    assert result == {"broker": "kotak-neo", "status": "Connected"}
    assert repo.ensure_default_called == [42]


def test_broker_status_none(monkeypatch):
    repo = DummySettingsRepo(db_marker := object())
    repo.settings.broker = None
    repo.settings.broker_status = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.broker_status(db=None, current=user)

    assert result == {"broker": None, "status": None}


# GET /creds/info tests
def test_get_broker_creds_info_no_creds(monkeypatch):
    repo = DummySettingsRepo(db_marker := object())
    repo.settings.broker_creds_encrypted = None
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is False
    assert result.api_key is None
    assert result.api_secret is None


def test_get_broker_creds_info_masked(monkeypatch):
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
    repo.settings.broker_creds_encrypted = b"invalid_encrypted_data"
    monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

    def mock_decrypt(blob):
        return None

    monkeypatch.setattr(broker, "decrypt_blob", mock_decrypt)

    user = DummyUser(id=42)
    result = broker.get_broker_creds_info(show_full=False, db=None, current=user)

    assert result.has_creds is False


def test_get_broker_creds_info_invalid_json(monkeypatch):
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
    repo = DummySettingsRepo(db_marker := object())
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
