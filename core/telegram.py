import requests
from utils.logger import logger  # or just import logging
from dotenv import load_dotenv
import os

# Try to load from multiple possible locations
# Priority: env vars -> cred.env -> config/.env (GCP)
try:
    # Try local development file
    load_dotenv("cred.env")
except:
    pass

try:
    # Try GCP Secret Manager mounted location
    load_dotenv("config/.env")
except:
    pass

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
    """
    Send telegram message with intelligent splitting at logical boundaries.
    
    Splits at stock boundaries (lines starting with numbers like "1. TICKER:")
    to avoid cutting stock information in half.
    """
    max_length = 4096
    
    # If message is short enough, send as-is
    if len(msg) <= max_length:
        send_long_message(msg)
        return
    
    # Split into logical chunks (at stock boundaries)
    lines = msg.split('\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    # Extract header (everything before first stock entry)
    header_lines = []
    stock_start_idx = 0
    for i, line in enumerate(lines):
        # Look for first stock entry (e.g., "1. TICKER:" or "1. TICKER.NS:")
        if line.strip() and line.strip()[0].isdigit() and ('. ' in line and ':' in line):
            stock_start_idx = i
            break
        header_lines.append(line)
    
    header = '\n'.join(header_lines)
    
    # Process stocks
    current_chunk = [header] if header else []
    current_length = len(header) + 1 if header else 0
    
    in_stock_block = False
    stock_block = []
    
    for i in range(stock_start_idx, len(lines)):
        line = lines[i]
        
        # Detect start of new stock block (e.g., "12. TICKER:")
        is_stock_start = (line.strip() and 
                         line.strip()[0].isdigit() and 
                         '. ' in line and 
                         ':' in line and
                         not line.strip().startswith('\t'))
        
        if is_stock_start:
            # If we have a previous stock block, try to add it
            if stock_block:
                block_text = '\n'.join(stock_block)
                block_length = len(block_text) + 1
                
                # Check if adding this block would exceed limit
                if current_length + block_length > max_length:
                    # Save current chunk and start new one
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [header] if header else []
                    current_length = len(header) + 1 if header else 0
                
                current_chunk.extend(stock_block)
                current_length += block_length
            
            # Start new stock block
            stock_block = [line]
            in_stock_block = True
        else:
            # Add line to current stock block
            if in_stock_block:
                stock_block.append(line)
    
    # Add final stock block
    if stock_block:
        block_text = '\n'.join(stock_block)
        block_length = len(block_text) + 1
        
        if current_length + block_length > max_length:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [header] if header else []
            current_length = len(header) + 1 if header else 0
        
        current_chunk.extend(stock_block)
    
    # Add final chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    # Send all chunks
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            logger.info(f"Sending Telegram message part {i+1}/{len(chunks)} ({len(chunk)} chars)")
        send_long_message(chunk)
