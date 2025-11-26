"""
Tests for security utilities - token masking and sensitive data handling
"""

from modules.kotak_neo_auto_trader.utils.security_utils import (
    mask_sensitive_value,
    mask_token_in_dict,
    safe_log_dict,
    sanitize_log_message,
)


class TestMaskSensitiveValue:
    def test_mask_short_value(self):
        """Short values should be fully masked"""
        assert mask_sensitive_value("abc") == "***"
        assert mask_sensitive_value("abcd") == "****"

    def test_mask_long_value(self):
        """Long values should show first/last chars"""
        result = mask_sensitive_value("my_secret_token_12345", visible_chars=4)
        assert result == "my_s...2345"
        assert "secret" not in result

    def test_mask_empty_value(self):
        """Empty/None values should be masked"""
        assert mask_sensitive_value("") == "***"
        assert mask_sensitive_value(None) == "***"

    def test_mask_non_string(self):
        """Non-string values should be masked"""
        assert mask_sensitive_value(12345) == "***"
        assert mask_sensitive_value([1, 2, 3]) == "***"


class TestMaskTokenInDict:
    def test_mask_token_keys(self):
        """Should mask values for token-related keys"""
        data = {
            "user": "john",
            "token": "secret_token_12345",
            "access_token": "another_secret",
        }
        result = mask_token_in_dict(data)

        assert result["user"] == "john"
        assert "secret" not in result["token"]
        assert "..." in result["token"]
        assert "secret" not in result["access_token"]

    def test_mask_password_keys(self):
        """Should mask password and secret keys"""
        data = {
            "username": "john",
            "password": "MyP@ssw0rd!",
            "api_secret": "secret123",
        }
        result = mask_token_in_dict(data)

        assert result["username"] == "john"
        assert "P@ss" not in result["password"]
        assert "secret" not in result["api_secret"]

    def test_mask_nested_dict(self):
        """Should recursively mask nested dictionaries"""
        data = {
            "user": "john",
            "auth": {"token": "secret_token", "session": {"jwt": "very_secret_jwt"}},
        }
        result = mask_token_in_dict(data)

        assert result["user"] == "john"
        assert "secret" not in result["auth"]["token"]
        assert "very_secret" not in result["auth"]["session"]["jwt"]

    def test_mask_list_of_dicts(self):
        """Should mask dictionaries within lists"""
        data = {
            "users": [
                {"name": "john", "token": "secret1"},
                {"name": "jane", "token": "secret2"},
            ]
        }
        result = mask_token_in_dict(data)

        assert result["users"][0]["name"] == "john"
        assert "secret" not in result["users"][0]["token"]
        assert "secret" not in result["users"][1]["token"]

    def test_case_insensitive_matching(self):
        """Should match keys case-insensitively"""
        data = {
            "Token": "secret1",
            "ACCESS_TOKEN": "secret2",
            "Session_Token": "secret3",
        }
        result = mask_token_in_dict(data)

        assert "secret" not in result["Token"]
        assert "secret" not in result["ACCESS_TOKEN"]
        assert "secret" not in result["Session_Token"]

    def test_non_dict_input(self):
        """Should return non-dict inputs unchanged"""
        assert mask_token_in_dict("string") == "string"
        assert mask_token_in_dict(123) == 123
        assert mask_token_in_dict(None) is None


class TestSanitizeLogMessage:
    def test_mask_jwt_tokens(self):
        """Should mask JWT tokens in log messages"""
        message = (
            "Got token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
            "eyJ1c2VyX2lkIjoxMjM0NTY3ODkwfQ.signature_part"
        )
        result = sanitize_log_message(message)

        assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in result
        assert "eyJ...***" in result

    def test_mask_long_tokens(self):
        """Should mask long alphanumeric tokens (40+ chars)"""
        message = "Session: abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567"
        result = sanitize_log_message(message)

        assert len("abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567") > 40
        assert "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567" not in result
        assert "abc123de...***" in result

    def test_preserve_short_strings(self):
        """Should not mask short strings"""
        message = "User logged in with session abc123"
        result = sanitize_log_message(message)

        assert "abc123" in result  # Short string preserved
        assert result == message


class TestSafeLogDict:
    def test_safe_log_with_sensitive_data(self):
        """Should return safe string representation with masked data"""
        data = {
            "user": "john",
            "token": "secret_token_12345",
            "api_key": "my_api_key_secret",
        }
        result = safe_log_dict(data)

        assert "john" in result
        assert "secret_token_12345" not in result
        assert "my_api_key_secret" not in result
        assert "token" in result  # Key should still be present
        assert "api_key" in result  # Key should still be present

    def test_safe_log_non_sensitive(self):
        """Should preserve non-sensitive data"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "count": 42,
        }
        result = safe_log_dict(data)

        assert "John Doe" in result
        assert "john@example.com" in result
        assert "42" in result


class TestSecurityIntegration:
    """Integration tests for real-world scenarios"""

    def test_kotak_api_response(self):
        """Should mask tokens in Kotak API-like response"""
        response = {
            "status": "success",
            "data": {
                "user_id": "12345",
                "session_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.payload.signature",
                "hsservid": "SERVER_123456789",
            },
            "message": "Login successful",
        }

        result = mask_token_in_dict(response)

        assert result["status"] == "success"
        assert result["data"]["user_id"] == "12345"
        assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in str(result)
        assert "SERVER_123456789" not in str(result)
        assert result["message"] == "Login successful"

    def test_order_response(self):
        """Should preserve order data while masking auth headers"""
        response = {
            "order_id": "ORD123",
            "symbol": "TATASTEEL",
            "price": 100.50,
            "authorization": "Bearer secret_token_12345",
        }

        result = mask_token_in_dict(response)

        assert result["order_id"] == "ORD123"
        assert result["symbol"] == "TATASTEEL"
        assert result["price"] == 100.50
        assert "secret_token_12345" not in str(result)
