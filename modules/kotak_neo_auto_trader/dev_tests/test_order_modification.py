#!/usr/bin/env python3
"""
Test Order Modification Functionality

Test flow:
1. Place BUY order: YESBANK @ Rs 23.50, qty=2
2. Modify order: Change qty from 2 to 10
3. Verify modification success
4. Cancel the order

Run with: python test_order_modification.py
"""

import sys
from pathlib import Path
import time
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from Kotak Neo env file
env_path = project_root / "modules" / "kotak_neo_auto_trader" / "kotak_neo.env"
load_dotenv(env_path)

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
from utils.logger import logger


def test_order_modification():
    """Test order modification workflow"""

    print("=" * 70)
    print("? ORDER MODIFICATION TEST")
    print("=" * 70)

    # Step 1: Initialize
    print("\n? Step 1: Initializing Kotak Neo connection...")

    try:
        auth = KotakNeoAuth()
        orders = KotakNeoOrders(auth)

        # Login first
        print("   Logging in...")
        if not auth.login():
            print("? Failed to login")
            return False

        if not auth.get_client():
            print("? Failed to authenticate")
            return False
        print("? Authentication successful")
    except ValueError as e:
        print(f"? Authentication failed: {e}")
        print("\n? Please ensure your Kotak Neo credentials are set up:")
        print("   - Check if .env file exists in project root")
        print("   - Or set environment variables for Kotak Neo")
        print("   - Run setup_credentials.py if available")
        return False

    # Step 2: Place initial order
    # Using price below market to prevent immediate execution (limit order)
    print("\n? Step 2: Placing BUY LIMIT order - YESBANK @ Rs 20.00, qty=2")
    symbol = "YESBANK-EQ"  # Use proper symbol format with -EQ suffix
    initial_qty = 2
    price = 20.00  # Below market price - order will remain pending

    order_response = orders.place_limit_buy(
        symbol=symbol,
        quantity=initial_qty,
        price=price,
        variety="REGULAR",  # Regular order for intraday testing
        exchange="NSE",
        product="CNC",
    )

    if not order_response:
        print("? Failed to place order")
        return False

    # Extract order ID
    order_id = None
    if "nOrdNo" in order_response:
        order_id = order_response["nOrdNo"]
    elif "neoOrdNo" in order_response:
        order_id = order_response["neoOrdNo"]
    elif "data" in order_response and isinstance(order_response["data"], dict):
        order_id = order_response["data"].get("nOrdNo") or order_response["data"].get("orderId")

    if not order_id:
        print(f"? Could not extract order ID from response: {order_response}")
        return False

    print(f"? Order placed successfully")
    print(f"   Order ID: {order_id}")
    print(f"   Symbol: {symbol}")
    print(f"   Quantity: {initial_qty}")
    print(f"   Price: Rs {price:.2f}")

    # Wait a moment for order to register
    print("\n? Waiting 2 seconds for order to register...")
    time.sleep(2)

    # Step 3: Verify initial order
    print("\n? Step 3: Verifying initial order...")
    all_orders = orders.get_orders()

    initial_order = None
    if all_orders and isinstance(all_orders, dict) and "data" in all_orders:
        for order in all_orders.get("data", []):
            oid = order.get("neoOrdNo") or order.get("nOrdNo") or order.get("orderId")
            if str(oid) == str(order_id):
                initial_order = order
                break

    if initial_order:
        qty = (
            initial_order.get("quantity")
            or initial_order.get("qty")
            or initial_order.get("tradedQuantity", "N/A")
        )
        price_val = initial_order.get("price") or initial_order.get("prc", 0)
        print(f"? Found order in order book")
        print(f"   Status: {initial_order.get('status', 'N/A')}")
        print(f"   Quantity: {qty}")
        print(f"   Price: Rs {float(price_val):.2f}")
    else:
        print("[WARN]?  Order not found in order book (may be too fast)")

    # Step 4: Modify order quantity
    print("\n? Step 4: Modifying order quantity from 2 to 10...")
    new_qty = 10

    modify_response = orders.modify_order(order_id=str(order_id), quantity=new_qty, price=price)

    if not modify_response:
        print("? Failed to modify order")
        print("   Proceeding to cancel original order...")
        # Still try to cancel
        cancel_response = orders.cancel_order(order_id=str(order_id))
        return False

    print(f"? Order modified successfully")
    print(f"   New Quantity: {new_qty}")
    print(f"   Response: {modify_response}")

    # Wait for modification to register
    print("\n? Waiting 2 seconds for modification to register...")
    time.sleep(2)

    # Step 5: Verify modification
    print("\n? Step 5: Verifying order modification...")
    all_orders = orders.get_orders()

    modified_order = None
    if all_orders and isinstance(all_orders, dict) and "data" in all_orders:
        for order in all_orders.get("data", []):
            oid = order.get("neoOrdNo") or order.get("nOrdNo") or order.get("orderId")
            if str(oid) == str(order_id):
                modified_order = order
                break

    verification_passed = False
    if modified_order:
        # Debug: print available keys
        print(f"   DEBUG - Order keys: {list(modified_order.keys())}")

        qty_val = (
            modified_order.get("quantity")
            or modified_order.get("qty")
            or modified_order.get("filledQty")
            or 0
        )
        current_qty = int(qty_val) if qty_val else 0
        price_val = (
            modified_order.get("price")
            or modified_order.get("prc")
            or modified_order.get("avgPrc", 0)
        )
        status_val = (
            modified_order.get("status")
            or modified_order.get("orderStatus")
            or modified_order.get("ordSt", "N/A")
        )

        print(f"? Found modified order in order book")
        print(f"   Status: {status_val}")
        print(f"   Quantity: {current_qty}")
        print(f"   Price: Rs {float(price_val):.2f}")

        if current_qty == new_qty:
            print(f"\n? VERIFICATION PASSED: Quantity updated from {initial_qty} to {new_qty}")
            verification_passed = True
        else:
            print(
                f"\n[WARN]?  VERIFICATION WARNING: Expected qty={new_qty}, found qty={current_qty}"
            )
    else:
        print("? Modified order not found in order book")

    # Step 6: Cancel order
    print("\n? Step 6: Cancelling order...")
    cancel_response = orders.cancel_order(order_id=str(order_id))

    if cancel_response:
        print(f"? Order cancelled successfully")
        print(f"   Response: {cancel_response}")
    else:
        print("? Failed to cancel order")
        print("[WARN]?  Please manually cancel order from Kotak Neo app")
        print(f"   Order ID: {order_id}")

    # Final verification
    print("\n? Waiting 2 seconds for cancellation to register...")
    time.sleep(2)

    print("\n? Step 7: Final verification...")
    all_orders = orders.get_orders()

    final_order = None
    if all_orders and isinstance(all_orders, dict) and "data" in all_orders:
        for order in all_orders.get("data", []):
            oid = order.get("neoOrdNo") or order.get("nOrdNo") or order.get("orderId")
            if str(oid) == str(order_id):
                final_order = order
                break

    if final_order:
        status = final_order.get("status", "N/A").lower()
        print(f"   Order Status: {status}")
        if status in ["cancelled", "canceled", "rejected"]:
            print("? Order successfully cancelled")
        else:
            print(f"[WARN]?  Order still active with status: {status}")
    else:
        print("? Order removed from active orders")

    # Summary
    print("\n" + "=" * 70)
    print("? TEST SUMMARY")
    print("=" * 70)
    print(f"Order Placement:    ? Success")
    print(f"Order Modification: {'? Success' if modify_response else '? Failed'}")
    print(f"Quantity Verified:  {'? Passed' if verification_passed else '[WARN]?  Warning'}")
    print(f"Order Cancellation: {'? Success' if cancel_response else '? Failed'}")

    if verification_passed and cancel_response:
        print("\n? ALL TESTS PASSED!")
        print("? Order modification functionality is working correctly")
        return True
    elif verification_passed:
        print("\n[WARN]?  PARTIAL SUCCESS")
        print("? Order modification works, but cancellation failed")
        print(f"[WARN]?  Please manually cancel order {order_id}")
        return True
    else:
        print("\n? TEST FAILED")
        print("Order modification did not work as expected")
        return False


if __name__ == "__main__":
    try:
        success = test_order_modification()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN]?  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n? Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
