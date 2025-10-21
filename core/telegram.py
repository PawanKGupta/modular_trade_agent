import requests
from utils.logger import logger  # or just import logging
from dotenv import load_dotenv
import os

# Try to load cred.env if it exists (for local development)
# In GitHub Actions, environment variables are set directly
try:
    load_dotenv("cred.env")
except:
    pass  # File doesn't exist (e.g., in GitHub Actions), use env vars directly

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_long_message(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram token or chat ID not configured.")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return None
        data = response.json()
        if not data.get("ok"):
            logger.error(f"Telegram API returned error: {data}")
            return None
        logger.info("Telegram message sent successfully.")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram send failed: {e}")
        return None

def send_telegram(msg):
    max_length = 4096
    for i in range(0, len(msg), max_length):
        send_long_message(msg[i:i+max_length])
