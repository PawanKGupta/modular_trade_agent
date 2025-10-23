#!/usr/bin/env python3
"""
Simple test script to verify Telegram connection works in GitHub Actions
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.telegram import send_telegram, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import logger
from datetime import datetime

def test_telegram():
    """Test Telegram connection"""
    
    print("=== Telegram Connection Test ===")
    print(f"Bot Token exists: {bool(TELEGRAM_BOT_TOKEN)}")
    print(f"Chat ID exists: {bool(TELEGRAM_CHAT_ID)}")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials")
        return False
    
    # Send test message
    test_msg = f"🧪 GitHub Actions Test\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\nTelegram connection working! ✅"
    
    try:
        result = send_telegram(test_msg)
        if result:
            print("✅ Telegram test message sent successfully!")
            return True
        else:
            print("❌ Failed to send Telegram message")
            return False
    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_telegram()
    sys.exit(0 if success else 1)