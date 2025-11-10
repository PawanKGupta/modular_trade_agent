#!/usr/bin/env python3
"""
Tests for error handling utilities
"""

import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.utils.error_handlers import (
    handle_broker_error,
    safe_execute,
    BrokerErrorHandler
)


class TestHandleBrokerError:
    """Test handle_broker_error decorator"""
    
    def test_decorator_success(self):
        """Test decorator with successful execution"""
        @handle_broker_error("test operation", default_return=None)
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
    
    def test_decorator_error_returns_default(self):
        """Test decorator returns default on error"""
        @handle_broker_error("test operation", default_return=None)
        def test_func():
            raise ValueError("Test error")
        
        result = test_func()
        assert result is None
    
    def test_decorator_error_returns_custom_default(self):
        """Test decorator returns custom default on error"""
        @handle_broker_error("test operation", default_return={})
        def test_func():
            raise ValueError("Test error")
        
        result = test_func()
        assert result == {}
    
    @patch('modules.kotak_neo_auto_trader.utils.error_handlers.logger')
    def test_decorator_logs_error(self, mock_logger):
        """Test decorator logs error"""
        @handle_broker_error("test operation", default_return=None, log_level='warning')
        def test_func():
            raise ValueError("Test error")
        
        test_func()
        mock_logger.warning.assert_called_once()
        assert "Error in test operation" in str(mock_logger.warning.call_args)
    
    def test_decorator_reraise(self):
        """Test decorator with reraise=True"""
        @handle_broker_error("test operation", default_return=None, reraise=True)
        def test_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_func()


class TestSafeExecute:
    """Test safe_execute function"""
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful execution"""
        result = safe_execute(
            lambda: "success",
            "test operation",
            default_return=None
        )
        assert result == "success"
    
    def test_safe_execute_error_returns_default(self):
        """Test safe_execute returns default on error"""
        result = safe_execute(
            lambda: (_ for _ in ()).throw(ValueError("Test error")),
            "test operation",
            default_return=None
        )
        assert result is None
    
    @patch('modules.kotak_neo_auto_trader.utils.error_handlers.logger')
    def test_safe_execute_logs_error(self, mock_logger):
        """Test safe_execute logs error"""
        safe_execute(
            lambda: (_ for _ in ()).throw(ValueError("Test error")),
            "test operation",
            default_return=None,
            log_level='error'
        )
        mock_logger.error.assert_called_once()
        assert "Error in test operation" in str(mock_logger.error.call_args)
    
    def test_safe_execute_reraise(self):
        """Test safe_execute with reraise=True"""
        with pytest.raises(ValueError):
            safe_execute(
                lambda: (_ for _ in ()).throw(ValueError("Test error")),
                "test operation",
                default_return=None,
                reraise=True
            )


class TestBrokerErrorHandler:
    """Test BrokerErrorHandler context manager"""
    
    def test_context_manager_success(self):
        """Test context manager with successful execution"""
        with BrokerErrorHandler("test operation", default_return=None) as handler:
            result = "success"
            handler.check_result(result)
        
        assert not handler.error_occurred
        assert handler.exception is None
    
    def test_context_manager_suppresses_exception(self):
        """Test context manager suppresses exception"""
        with BrokerErrorHandler("test operation", default_return=None) as handler:
            raise ValueError("Test error")
        
        assert handler.error_occurred
        assert isinstance(handler.exception, ValueError)
    
    @patch('modules.kotak_neo_auto_trader.utils.error_handlers.logger')
    def test_context_manager_logs_error(self, mock_logger):
        """Test context manager logs error"""
        with BrokerErrorHandler("test operation", default_return=None, log_level='error'):
            raise ValueError("Test error")
        
        mock_logger.error.assert_called_once()
        assert "Error in test operation" in str(mock_logger.error.call_args)
    
    def test_check_result_with_none(self):
        """Test check_result returns default for None"""
        with BrokerErrorHandler("test operation", default_return={}) as handler:
            result = handler.check_result(None)
        
        assert result == {}
    
    def test_check_result_with_value(self):
        """Test check_result returns value if not None"""
        with BrokerErrorHandler("test operation", default_return=None) as handler:
            result = handler.check_result("success")
        
        assert result == "success"





