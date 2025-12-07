"""
Tests for error message extraction from Kotak API responses

Tests cover:
1. Extracting error messages from HTTP response objects
2. Extracting error messages from JSON responses
3. Extracting error messages from error strings
4. Fallback to default messages when extraction fails
5. BrokerServiceUnavailableError exception behavior
"""

from unittest.mock import MagicMock, PropertyMock
from types import SimpleNamespace

import pytest

from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (
    BrokerServiceUnavailableError,
    _extract_api_error_message,
    _get_service_unavailable_message,
)


class TestExtractApiErrorMessage:
    """Tests for _extract_api_error_message function"""

    def test_extract_from_response_json_with_message_field(self):
        """Test extracting error message from response.json() with 'message' field"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "Service under maintenance until 2 PM"}
        mock_response.text = None

        error = MagicMock()
        error.response = mock_response

        result = _extract_api_error_message(error)
        assert result == "Service under maintenance until 2 PM"

    def test_extract_from_response_json_with_error_field(self):
        """Test extracting error message from response.json() with 'error' field"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "API temporarily unavailable"}
        mock_response.text = None

        error = MagicMock()
        error.response = mock_response

        result = _extract_api_error_message(error)
        assert result == "API temporarily unavailable"

    def test_extract_from_response_json_with_description_field(self):
        """Test extracting error message from response.json() with 'description' field"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"description": "Scheduled maintenance in progress"}
        mock_response.text = None

        error = MagicMock()
        error.response = mock_response

        result = _extract_api_error_message(error)
        assert result == "Scheduled maintenance in progress"

    def test_extract_from_response_json_with_error_array(self):
        """Test extracting error message from response.json() with error array"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": [{"message": "Service unavailable"}]
        }
        # Ensure text attribute doesn't interfere
        type(mock_response).text = PropertyMock(return_value=None)

        error = MagicMock()
        error.response = mock_response

        result = _extract_api_error_message(error)
        # The function should extract the message from the error array
        assert result == "Service unavailable"

    def test_extract_from_response_text(self):
        """Test extracting error message from response.text when JSON parsing fails"""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Service temporarily down for maintenance"

        error = MagicMock()
        error.response = mock_response

        result = _extract_api_error_message(error)
        assert result == "Service temporarily down for maintenance"

    def test_extract_from_response_text_too_long(self):
        """Test that response.text is ignored if too long"""
        # Create a simple mock object that behaves like a response
        class MockResponse:
            def json(self):
                raise ValueError("Not JSON")
            
            @property
            def text(self):
                return "x" * 600  # Too long (> 500)

        # Use a real Exception object, not MagicMock
        # The error message will be filtered out at the end
        error = Exception("Connection refused")
        error.response = MockResponse()

        result = _extract_api_error_message(error)
        # Should return None for text that's too long (implementation checks len < 500)
        # The error string "Connection refused" will be filtered out at the end
        assert result is None

    def test_extract_from_error_string_with_json(self):
        """Test extracting error message from error string containing JSON"""
        error = Exception('Connection failed: {"message": "Network timeout", "code": 503}')

        result = _extract_api_error_message(error)
        assert result == "Network timeout"

    def test_extract_from_error_string_with_simple_message(self):
        """Test extracting error message from simple error string"""
        error = Exception("API rate limit exceeded")

        result = _extract_api_error_message(error)
        assert result == "API rate limit exceeded"

    def test_ignore_generic_connection_errors(self):
        """Test that generic connection errors are not extracted"""
        error = Exception("Connection refused")

        result = _extract_api_error_message(error)
        assert result is None

    def test_ignore_network_unreachable_errors(self):
        """Test that network unreachable errors are not extracted"""
        error = Exception("Network is unreachable")

        result = _extract_api_error_message(error)
        assert result is None

    def test_no_response_attribute(self):
        """Test handling error without response attribute"""
        error = Exception("Some other error")

        result = _extract_api_error_message(error)
        # Should return the message if it's not a generic connection error
        assert result == "Some other error"

    def test_response_without_json_or_text(self):
        """Test handling response without json() or text attributes"""
        # Create a simple object without json or text attributes
        class ResponseWithoutText:
            pass

        # Use a real Exception with a message that will be filtered out
        error = Exception("Connection refused")
        error.response = ResponseWithoutText()

        result = _extract_api_error_message(error)
        # Should return None when response has no json or text
        # The error string "Connection refused" will be filtered out at the end
        assert result is None

    def test_json_parsing_exception(self):
        """Test handling JSON parsing exceptions gracefully"""
        # Create a simple class to properly mock response behavior
        class MockResponse:
            def json(self):
                raise Exception("JSON parse error")
            
            @property
            def text(self):
                return None  # No text available

        # Use a real Exception with a message that will be filtered out
        error = Exception("Connection refused")
        error.response = MockResponse()

        result = _extract_api_error_message(error)
        # Should return None when JSON parsing fails and text is None
        # The error string "Connection refused" will be filtered out at the end
        assert result is None


class TestGetServiceUnavailableMessage:
    """Tests for _get_service_unavailable_message function"""

    def test_uses_extracted_api_message_when_available(self):
        """Test that extracted API message is used when available"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "Service under maintenance"}
        mock_response.text = None

        error = MagicMock()
        error.response = mock_response

        default_message = "Default error message"
        result = _get_service_unavailable_message(error, default_message)

        assert result == "Service under maintenance"
        assert result != default_message

    def test_uses_default_message_when_extraction_fails(self):
        """Test that default message is used when extraction fails"""
        error = Exception("Connection refused")

        default_message = "Broker service is temporarily unavailable"
        result = _get_service_unavailable_message(error, default_message)

        assert result == default_message

    def test_handles_none_extraction_gracefully(self):
        """Test handling when extraction returns None"""
        error = Exception("Generic error")

        default_message = "Default message"
        result = _get_service_unavailable_message(error, default_message)

        # Should use default since extraction likely returned None for generic errors
        assert result in [default_message, "Generic error"]


class TestBrokerServiceUnavailableError:
    """Tests for BrokerServiceUnavailableError exception"""

    def test_exception_stores_message(self):
        """Test that exception stores the message correctly"""
        message = "Service temporarily unavailable"
        error = BrokerServiceUnavailableError(message)

        assert error.message == message
        assert str(error) == message

    def test_exception_stores_original_error(self):
        """Test that exception stores the original error"""
        original_error = Exception("Original API error")
        message = "Service unavailable"

        error = BrokerServiceUnavailableError(message, original_error=original_error)

        assert error.original_error == original_error
        assert error.message == message

    def test_exception_without_original_error(self):
        """Test exception creation without original error"""
        message = "Service unavailable"

        error = BrokerServiceUnavailableError(message)

        assert error.message == message
        assert error.original_error is None

    def test_exception_default_message(self):
        """Test exception with default message"""
        error = BrokerServiceUnavailableError()

        assert "Broker service is temporarily unavailable" in error.message

    def test_exception_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught properly"""
        message = "Test error message"

        with pytest.raises(BrokerServiceUnavailableError) as exc_info:
            raise BrokerServiceUnavailableError(message)

        assert exc_info.value.message == message
        assert str(exc_info.value) == message

