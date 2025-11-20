import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

# Hardcoded credentials (UPDATE THESE WITH YOUR CREDENTIALS)
KOTAK_CREDENTIALS = {
    "consumer_key": "NnK024fVQEC3j4Inf7g2CBpHIu8a",
    "consumer_secret": "R3rJMRBEoqHEn2OioMLYydOyhCYa",
    "mobile_number": "+918565859556",
    "password": "Pkmast@61",
    "mpin": "008135",  # OR use totp_secret instead
    # "totp_secret": "YOUR_TOTP_SECRET",  # Alternative to mpin
    "environment": "prod",  # or "dev" for testing
}

# Test symbol and quantity
TEST_SYMBOL = "YESBANK"
TEST_QUANTITY = 1
TEST_EXCHANGE = "NSE"
TEST_PRODUCT = "CNC"


def login():
    """Test authentication"""
    logger.info("=" * 60)
    logger.info("TEST 1: Authentication")
    logger.info("=" * 60)

    try:
        from neo_api_client import NeoAPI

        client = NeoAPI(
            consumer_key="NnK024fVQEC3j4Inf7g2CBpHIu8a",
            consumer_secret="R3rJMRBEoqHEn2OioMLYydOyhCYa",
            environment="prod",
            neo_fin_key="neotradeapi",
        )
        client.login(mobilenumber="+918565859556", password="Pkmast@61")
        client.session_2fa(OTP="008135")

        try:
            # Place a Order
            resp = client.scrip_master(exchange_segment="nse_cm")
            print(resp)
            response = client.place_order(
                exchange_segment="nse_cm",
                product="CNC",
                price="22",
                order_type="L",
                quantity="1",
                validity="DAY",
                trading_symbol="YESBANK-EQ",
                transaction_type="B",
                amo="YES",
                disclosed_quantity="0",
            )
            print(response)
        except Exception as e:
            print("Exception when calling OrderApi->place_order: %s\n" % e)

    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        raise


login()
