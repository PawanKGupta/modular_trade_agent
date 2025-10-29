"""
Check rejection reason for rejected orders
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
from utils.logger import logger

def check_rejected_orders():
    """Check rejection reasons for recently rejected orders"""
    
    # Initialize auth and orders
    auth = KotakNeoAuth()
    if not auth.login():
        print("Failed to login")
        return
    
    orders_client = KotakNeoOrders(auth)
    
    # Get all orders
    orders_data = orders_client.get_orders()
    
    if not orders_data or 'data' not in orders_data:
        print("No orders found")
        return
    
    # Filter rejected orders
    rejected_orders = []
    for order in orders_data['data']:
        status = (order.get('orderStatus') or order.get('ordSt') or '').lower()
        if 'reject' in status:
            rejected_orders.append(order)
    
    if not rejected_orders:
        print("No rejected orders found")
        return
    
    print(f"\n{'='*80}")
    print(f"Found {len(rejected_orders)} REJECTED orders:")
    print(f"{'='*80}\n")
    
    for order in rejected_orders:
        order_id = order.get('nOrdNo') or order.get('neoOrdNo') or order.get('orderId') or 'N/A'
        symbol = order.get('trdSym') or order.get('tradingSymbol') or order.get('symbol') or 'N/A'
        qty = order.get('qty') or order.get('quantity') or 0
        price = order.get('prc') or order.get('price') or 0
        status = order.get('ordSt') or order.get('orderStatus') or 'N/A'
        
        # Get rejection reason
        rejection_reason = (
            order.get('rejRsn') or 
            order.get('rejectionReason') or 
            order.get('rmk') or  # Sometimes the remark contains the reason
            'No reason provided'
        )
        
        # Get tick size info
        tick_size = order.get('tckSz') or 'N/A'
        
        print(f"Order ID: {order_id}")
        print(f"Symbol: {symbol}")
        print(f"Quantity: {qty}")
        print(f"Price: ₹{price}")
        print(f"Status: {status}")
        print(f"Tick Size: {tick_size}")
        print(f"❌ Rejection Reason: {rejection_reason}")
        print(f"{'-'*80}")
        
        # Print full order details for debugging
        print("\nFull order details:")
        for key, value in order.items():
            if value:  # Only print non-empty fields
                print(f"  {key}: {value}")
        print(f"\n{'='*80}\n")

if __name__ == "__main__":
    try:
        check_rejected_orders()
    except Exception as e:
        logger.error(f"Error checking rejected orders: {e}", exc_info=True)
        print(f"\nError: {e}")
