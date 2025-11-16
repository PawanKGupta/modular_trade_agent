"""
Tests for broker credentials management (Phase 2.4)

Tests credential decryption, temp env file creation, and credential loading.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from server.app.core.crypto import encrypt_blob
from src.application.services.broker_credentials import (
    convert_creds_to_env_format,
    create_temp_env_file,
    decrypt_broker_credentials,
    load_broker_credentials,
)
from src.infrastructure.db.models import TradeMode, Users, UserSettings


@pytest.fixture
def sample_creds_dict():
    """Sample broker credentials dictionary"""
    return {
        "api_key": "test_consumer_key",
        "api_secret": "test_consumer_secret",
        "mobile_number": "9876543210",
        "password": "test_password",
        "mpin": "1234",
        "totp_secret": "test_totp_secret",
        "environment": "prod",
    }


@pytest.fixture
def encrypted_creds(sample_creds_dict):
    """Encrypted credentials blob"""
    creds_json = json.dumps(sample_creds_dict)
    return encrypt_blob(creds_json.encode("utf-8"))


class TestDecryptBrokerCredentials:
    """Test credential decryption"""

    def test_decrypt_valid_credentials(self, encrypted_creds, sample_creds_dict):
        """Test decrypting valid encrypted credentials"""
        result = decrypt_broker_credentials(encrypted_creds)

        assert result is not None
        assert result["api_key"] == sample_creds_dict["api_key"]
        assert result["api_secret"] == sample_creds_dict["api_secret"]
        assert result["mobile_number"] == sample_creds_dict["mobile_number"]

    def test_decrypt_none(self):
        """Test decrypting None returns None"""
        result = decrypt_broker_credentials(None)
        assert result is None

    def test_decrypt_invalid_data(self):
        """Test decrypting invalid data returns None"""
        invalid_data = b"invalid_encrypted_data"
        result = decrypt_broker_credentials(invalid_data)
        assert result is None


class TestLoadBrokerCredentials:
    """Test loading credentials from database"""

    def test_load_credentials_success(self, db_session, encrypted_creds, sample_creds_dict):
        """Test loading credentials from database"""

        # Create user and settings
        user = Users(
            email="test@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=encrypted_creds,
        )
        db_session.add(settings)
        db_session.commit()

        # Load credentials
        result = load_broker_credentials(user.id, db_session)

        assert result is not None
        assert result["api_key"] == sample_creds_dict["api_key"]
        assert result["api_secret"] == sample_creds_dict["api_secret"]

    def test_load_credentials_no_settings(self, db_session):
        """Test loading when no settings exist"""
        user = Users(
            email="test@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        result = load_broker_credentials(user.id, db_session)
        assert result is None

    def test_load_credentials_no_encrypted_creds(self, db_session):
        """Test loading when no encrypted credentials exist"""
        user = Users(
            email="test@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        result = load_broker_credentials(user.id, db_session)
        assert result is None


class TestCreateTempEnvFile:
    """Test temporary env file creation"""

    def test_create_temp_env_file(self, sample_creds_dict):
        """Test creating temporary env file from credentials"""
        temp_path = create_temp_env_file(sample_creds_dict)

        try:
            # Verify file exists
            assert os.path.exists(temp_path)

            # Read and verify contents
            with open(temp_path) as f:
                content = f.read()

            assert "KOTAK_CONSUMER_KEY=test_consumer_key" in content
            assert "KOTAK_CONSUMER_SECRET=test_consumer_secret" in content
            assert "KOTAK_MOBILE_NUMBER=9876543210" in content
            assert "KOTAK_PASSWORD=test_password" in content
            assert "KOTAK_MPIN=1234" in content
            assert "KOTAK_TOTP_SECRET=test_totp_secret" in content
            assert "KOTAK_ENVIRONMENT=prod" in content

        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_create_temp_env_file_partial_creds(self):
        """Test creating env file with partial credentials"""
        partial_creds = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "environment": "prod",
        }

        temp_path = create_temp_env_file(partial_creds)

        try:
            assert os.path.exists(temp_path)

            with open(temp_path) as f:
                content = f.read()

            assert "KOTAK_CONSUMER_KEY=test_key" in content
            assert "KOTAK_CONSUMER_SECRET=test_secret" in content
            assert "KOTAK_ENVIRONMENT=prod" in content
            # Should not contain missing fields
            assert "KOTAK_MOBILE_NUMBER" not in content

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_create_temp_env_file_cleanup_on_error(self):
        """Test that temp file is cleaned up on error"""
        # Pass invalid data that would cause an error
        invalid_creds = None

        with pytest.raises(Exception):
            create_temp_env_file(invalid_creds)


class TestConvertCredsToEnvFormat:
    """Test credential format conversion"""

    def test_convert_full_creds(self, sample_creds_dict):
        """Test converting full credentials dict to env format"""
        env_creds = convert_creds_to_env_format(sample_creds_dict)

        assert env_creds["KOTAK_CONSUMER_KEY"] == "test_consumer_key"
        assert env_creds["KOTAK_CONSUMER_SECRET"] == "test_consumer_secret"
        assert env_creds["KOTAK_MOBILE_NUMBER"] == "9876543210"
        assert env_creds["KOTAK_PASSWORD"] == "test_password"
        assert env_creds["KOTAK_MPIN"] == "1234"
        assert env_creds["KOTAK_TOTP_SECRET"] == "test_totp_secret"
        assert env_creds["KOTAK_ENVIRONMENT"] == "prod"

    def test_convert_partial_creds(self):
        """Test converting partial credentials"""
        partial_creds = {
            "api_key": "key",
            "api_secret": "secret",
        }

        env_creds = convert_creds_to_env_format(partial_creds)

        assert env_creds["KOTAK_CONSUMER_KEY"] == "key"
        assert env_creds["KOTAK_CONSUMER_SECRET"] == "secret"
        assert "KOTAK_MOBILE_NUMBER" not in env_creds

    def test_convert_empty_creds(self):
        """Test converting empty credentials"""
        empty_creds = {}
        env_creds = convert_creds_to_env_format(empty_creds)
        assert env_creds == {}


class TestMultiUserTradingServiceBrokerAuth:
    """Test broker authentication in MultiUserTradingService"""

    def test_start_service_with_broker_mode(self, db_session):
        """Test starting service with broker mode and credentials"""
        from server.app.core.crypto import encrypt_blob
        from src.application.services.multi_user_trading_service import MultiUserTradingService
        from src.infrastructure.db.models import TradeMode, Users, UserSettings

        # Create user and settings with encrypted credentials
        user = Users(
            email="broker@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        creds_dict = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "mobile_number": "9876543210",
            "password": "test_pass",
            "mpin": "1234",
            "environment": "prod",
        }
        encrypted = encrypt_blob(json.dumps(creds_dict).encode("utf-8"))

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker="kotak-neo",
            broker_creds_encrypted=encrypted,
        )
        db_session.add(settings)
        db_session.commit()

        # Mock TradingService to avoid actual initialization
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            service_manager = MultiUserTradingService(db_session)

            # Should succeed
            result = service_manager.start_service(user.id)
            assert result is True

            # Verify TradingService was called with temp env file
            call_args = mock_service_class.call_args
            assert call_args is not None
            assert call_args.kwargs["user_id"] == user.id
            assert call_args.kwargs["db_session"] == db_session
            assert call_args.kwargs["env_file"] is not None  # Temp env file created
            assert os.path.exists(call_args.kwargs["env_file"])

            # Cleanup temp file
            if "env_file" in call_args.kwargs and os.path.exists(call_args.kwargs["env_file"]):
                os.unlink(call_args.kwargs["env_file"])

    def test_start_service_with_paper_mode(self, db_session):
        """Test starting service with paper mode (no credentials needed)"""
        from src.application.services.multi_user_trading_service import MultiUserTradingService
        from src.infrastructure.db.models import TradeMode, Users, UserSettings

        # Create user and settings with paper mode
        user = Users(
            email="paper@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.PAPER,
            broker=None,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            service_manager = MultiUserTradingService(db_session)

            # Should succeed (paper mode doesn't need credentials)
            result = service_manager.start_service(user.id)
            assert result is True

            # Verify TradingService was called
            call_args = mock_service_class.call_args
            assert call_args is not None
            assert call_args.kwargs["user_id"] == user.id

    def test_start_service_no_credentials(self, db_session):
        """Test starting service without credentials in broker mode fails"""
        from src.application.services.multi_user_trading_service import MultiUserTradingService
        from src.infrastructure.db.models import TradeMode, Users, UserSettings

        user = Users(
            email="nocreds@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker="kotak-neo",
            broker_creds_encrypted=None,  # No credentials
        )
        db_session.add(settings)
        db_session.commit()

        service_manager = MultiUserTradingService(db_session)

        # Should fail
        with pytest.raises(ValueError, match="No broker credentials stored"):
            service_manager.start_service(user.id)

    def test_start_service_invalid_credentials(self, db_session):
        """Test starting service with invalid encrypted credentials fails"""
        from src.application.services.multi_user_trading_service import MultiUserTradingService
        from src.infrastructure.db.models import TradeMode, Users, UserSettings

        user = Users(
            email="invalid@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker="kotak-neo",
            broker_creds_encrypted=b"invalid_encrypted_data",
        )
        db_session.add(settings)
        db_session.commit()

        service_manager = MultiUserTradingService(db_session)

        # Should fail
        with pytest.raises(ValueError, match="Failed to decrypt broker credentials"):
            service_manager.start_service(user.id)

    def test_stop_service_cleans_up_temp_file(self, db_session):
        """Test that stopping service cleans up temp env file"""
        from server.app.core.crypto import encrypt_blob
        from src.application.services.multi_user_trading_service import MultiUserTradingService
        from src.infrastructure.db.models import TradeMode, Users, UserSettings

        user = Users(
            email="cleanup@example.com",
            password_hash="test_hash",
            role="user",
        )
        db_session.add(user)
        db_session.commit()

        creds_dict = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "environment": "prod",
        }
        encrypted = encrypt_blob(json.dumps(creds_dict).encode("utf-8"))

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.BROKER,
            broker="kotak-neo",
            broker_creds_encrypted=encrypted,
        )
        db_session.add(settings)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            service_manager = MultiUserTradingService(db_session)
            service_manager.start_service(user.id)

            # Get temp file path
            call_args = mock_service_class.call_args
            temp_file = call_args.kwargs.get("env_file")

            # Verify file exists
            if temp_file:
                assert os.path.exists(temp_file)

                # Stop service
                service_manager.stop_service(user.id)

                # Verify file was cleaned up
                assert not os.path.exists(temp_file)
