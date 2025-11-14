#!/usr/bin/env python3
"""
Test: SDK raises AttributeError inside session_2fa
This tests the scenario where the SDK itself raises "'NoneType' object has no attribute 'get'"
"""

import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth


class TestSDKAttributeError(unittest.TestCase):
    """Test SDK raising AttributeError inside session_2fa"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_sdk_raises_attribute_error(self):
        """Test that SDK raising AttributeError is handled gracefully"""
        mock_client = Mock()
        # SDK raises AttributeError when trying to access .get() on None
        mock_client.session_2fa.side_effect = AttributeError("'NoneType' object has no attribute 'get'")
        
        self.auth._initialize_client = lambda: mock_client
        
        # Should not raise exception, should return True (session already active)
        result = self.auth.login()
        
        self.assertTrue(result, "Login should succeed when SDK raises NoneType.get error")
        self.assertEqual(mock_client.session_2fa.call_count, 1)
    
    def test_sdk_raises_generic_exception_with_nonetype_get(self):
        """Test that generic exception with NoneType.get message is handled"""
        mock_client = Mock()
        # SDK raises generic exception with NoneType.get in message
        mock_client.session_2fa.side_effect = Exception("'NoneType' object has no attribute 'get'")
        
        self.auth._initialize_client = lambda: mock_client
        
        # Should not raise exception, should return True
        result = self.auth.login()
        
        self.assertTrue(result, "Login should succeed when SDK raises NoneType.get error")
        self.assertEqual(mock_client.session_2fa.call_count, 1)


if __name__ == '__main__':
    unittest.main()
