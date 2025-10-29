#!/usr/bin/env python3
"""
Orders Management Module for Kotak Neo API
Handles order retrieval, tracking, placement, and GTT orders
"""

from typing import Optional, Dict, List
# Use existing project logger
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

try:
    from .auth import KotakNeoAuth
except ImportError:
    from auth import KotakNeoAuth


class KotakNeoOrders:
    """
    Order management for Kotak Neo API
    """
    
    def __init__(self, auth: KotakNeoAuth):
        """
        Initialize orders manager
        
        Args:
            auth (KotakNeoAuth): Authenticated session instance
        """
        self.auth = auth
        logger.info(" KotakNeoOrders initialized")
    
    # -------------------- Placement --------------------
    def place_equity_order(self,
                           symbol: str,
                           quantity: int,
                           price: float = 0.0,
                           transaction_type: str = "BUY",
                           product: str = "CNC",
                           order_type: str = "MARKET",
                           validity: str = "DAY",
                           variety: str = "AMO",
                           exchange: str = "NSE",
                           remarks: str = "") -> Optional[Dict]:
        """
        Place an equity order (defaults to AMO for after-market).
        Attempts multiple method names and adapts payload to method signature.
        """
        import inspect
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            def _sanitize(value):
                import json
                from collections.abc import Mapping, Sequence
                if isinstance(value, (str, int, float, bool)) or value is None:
                    return value
                if isinstance(value, Mapping):
                    return {str(k): _sanitize(v) for k, v in value.items()}
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                    return [ _sanitize(v) for v in value ]
                try:
                    json.dumps(value)
                    return value
                except Exception:
                    return str(value)

            base_payload = {
                "exchange": exchange,
                "tradingSymbol": symbol,
                "transactionType": ("B" if transaction_type.upper()=="BUY" else ("S" if transaction_type.upper()=="SELL" else transaction_type)),
                "quantity": str(int(quantity)),
                "price": str(float(price)) if order_type.upper() == "LIMIT" else "0",
                "product": product.upper(),
                "orderType": ("MKT" if order_type.upper()=="MARKET" else ("L" if order_type.upper()=="LIMIT" else order_type.upper())),
                "validity": validity.upper(),
                "variety": variety.upper(),
                "disclosedQuantity": 0,
                "triggerPrice": "0",
                "remarks": remarks,
            }

            # Synonym mappings if target method expects alternative keys
            alt_keys = {
                # common JSON -> alt param names
                "tradingSymbol": "symbol",
                "transactionType": "txnType",
                "quantity": "qty",
                "orderType": "type",
                "disclosedQuantity": "discQty",
                "triggerPrice": "trigPrice",
                # SDK variants observed in errors/docs
                "tradingSymbol": "trading_symbol",
                "transactionType": "transaction_type",
                "orderType": "order_type",
                "variety": "order_variety",
                "product": "product_type",
            }

            def call_method(name: str) -> Optional[Dict]:
                if not hasattr(client, name):
                    return None
                method = getattr(client, name)
                try:
                    params = set(inspect.signature(method).parameters.keys())
                except (ValueError, TypeError):
                    # Builtins or C-implemented callables may not expose signature; try direct
                    params = set()
                
                # Build payload for this method
                payload = {}
                # Special-case: some SDKs require 'exchange_segment' instead of 'exchange'
                if 'exchange_segment' in params:
                    ex_seg = exchange.upper() if exchange.upper() in ('NSE','BSE') else exchange
                    payload['exchange_segment'] = ex_seg
                if 'exchange' in params:
                    payload['exchange'] = exchange.upper()
                for k, v in base_payload.items():
                    if k in params:
                        payload[k] = v
                    elif k in alt_keys and alt_keys[k] in params:
                        payload[alt_keys[k]] = v
                
                logger.info(f" Placing {transaction_type.upper()} {order_type.upper()} order: {symbol} x{quantity} @ {price} [{variety}/{product}] via {name}")
                response = method(**payload)
                # Normalize response to a dict when possible
                if isinstance(response, dict):
                    # Detect errors regardless of key casing
                    keys_lower = {str(k).lower() for k in response.keys()}
                    if any(k in keys_lower for k in ("error", "errors")):
                        logger.error(f" Order rejected: {response}")
                        return None
                    safe = _sanitize(response)
                    logger.info(f"✅ Order placed: {safe}")
                    return safe
                # Non-dict responses: convert to string and treat as success only if indicative
                resp_text = str(response)
                if 'error' in resp_text.lower() or 'invalid' in resp_text.lower():
                    logger.error(f" Order rejected/invalid: {resp_text}")
                    return None
                logger.info(f"✅ Order placed (raw): {resp_text}")
                return {"raw": resp_text}

            for method_name in ("place_order", "order_place", "placeorder"):
                try:
                    resp = call_method(method_name)
                    if resp:
                        return resp
                except TypeError as e:
                    logger.warning(f"Signature mismatch in {method_name}: {e}")
                except Exception as e:
                    logger.warning(f"Order placement via {method_name} failed: {e}")

            logger.error(f"❌ Failed to place order for {symbol}: no compatible method/params")
            return None
        
        except Exception as e:
            logger.error(f" Error placing order for {symbol}: {e}")
            return None

    def place_market_buy(self, symbol: str, quantity: int, variety: str = "AMO", exchange: str = "NSE", product: str = "CNC") -> Optional[Dict]:
        return self.place_equity_order(symbol=symbol, quantity=quantity, transaction_type="BUY", order_type="MARKET", variety=variety, exchange=exchange, product=product)

    def place_limit_buy(self, symbol: str, quantity: int, price: float, variety: str = "AMO", exchange: str = "NSE", product: str = "CNC") -> Optional[Dict]:
        return self.place_equity_order(symbol=symbol, quantity=quantity, price=price, transaction_type="BUY", order_type="LIMIT", variety=variety, exchange=exchange, product=product)

    def place_market_sell(self, symbol: str, quantity: int, variety: str = "AMO", exchange: str = "NSE", product: str = "CNC") -> Optional[Dict]:
        return self.place_equity_order(symbol=symbol, quantity=quantity, transaction_type="SELL", order_type="MARKET", variety=variety, exchange=exchange, product=product)

    def place_limit_sell(self, symbol: str, quantity: int, price: float, variety: str = "AMO", exchange: str = "NSE", product: str = "CNC") -> Optional[Dict]:
        return self.place_equity_order(symbol=symbol, quantity=quantity, price=price, transaction_type="SELL", order_type="LIMIT", variety=variety, exchange=exchange, product=product)

    # -------------------- GTT Placement (unsupported) --------------------
    def place_gtt_order(self, *args, **kwargs) -> Optional[Dict]:
        """Disabled: Kotak Neo API does not support GTT for this integration."""
        logger.warning("GTT orders are not supported by Kotak Neo API; operation disabled.")
        return None

    def place_gtt_buy(self, *args, **kwargs) -> Optional[Dict]:
        """Disabled: Kotak Neo API does not support GTT for this integration."""
        logger.warning("GTT orders are not supported by Kotak Neo API; operation disabled.")
        return None

    # -------------------- Cancel / Manage --------------------
    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """Cancel an order by ID, trying multiple SDK method names/params."""
        client = self.auth.get_client()
        if not client:
            return None
        import inspect
        try:
            def call_method(name: str) -> Optional[Dict]:
                if not hasattr(client, name):
                    return None
                method = getattr(client, name)
                try:
                    params = set(inspect.signature(method).parameters.keys())
                except (ValueError, TypeError):
                    params = set()
                payload = {}
                for key in ("order_id", "orderId", "neoOrdNo", "ordId", "id"):
                    if key in params:
                        payload[key] = order_id
                if not payload:
                    # Try positional fallback
                    try:
                        resp = method(order_id)
                        return resp if isinstance(resp, dict) else {"raw": str(resp)}
                    except Exception:
                        return None
                resp = method(**payload)
                return resp if isinstance(resp, dict) else {"raw": str(resp)}
            for method_name in ("cancel_order", "order_cancel", "cancelOrder", "cancelorder", "modify_order"):
                try:
                    resp = call_method(method_name)
                    if resp:
                        logger.info(f"✅ Cancelled order {order_id} via {method_name}")
                        return resp
                except Exception as e:
                    logger.warning(f"Cancel via {method_name} failed: {e}")
            logger.error(f"❌ Failed to cancel order {order_id}")
            return None
        except Exception as e:
            logger.error(f" Error cancelling order {order_id}: {e}")
            return None

    def cancel_pending_buys_for_symbol(self, symbol_variants: list[str]) -> int:
        """Cancel all pending BUY orders for any of the given symbol variants.
        Returns count cancelled.
        """
        pend = self.get_pending_orders() or []
        cancelled = 0
        for o in pend:
            try:
                txn = str(o.get('transactionType','')).upper()
                sym = str(o.get('tradingSymbol','')).upper()
                if not txn.startswith('B'):
                    continue
                if sym not in set(v.upper() for v in symbol_variants):
                    continue
                oid = o.get('neoOrdNo') or o.get('orderId') or o.get('ordId') or o.get('id')
                if not oid:
                    continue
                if self.cancel_order(str(oid)):
                    cancelled += 1
            except Exception:
                continue
        return cancelled

    # -------------------- Retrieval --------------------
    def get_orders(self) -> Optional[Dict]:
        """Get all existing regular orders (not GTT) with fallbacks and raw logging."""
        client = self.auth.get_client()
        if not client:
            return None
        
        def _call_any(method_names):
            for name in method_names:
                try:
                    if hasattr(client, name):
                        return getattr(client, name)()
                except Exception:
                    continue
            return None
        
        try:
            logger.info(" Retrieving existing orders...")
            orders = _call_any(["order_report", "get_order_report", "orderBook", "orders", "order_book"]) or {}
            
            if isinstance(orders, dict) and "error" in orders:
                logger.error(f" Failed to get orders: {orders['error']}")
                return None
            
            # Process and display orders
            if isinstance(orders, dict) and 'data' in orders and orders['data']:
                orders_data = orders['data']
                logger.info(f" Found {len(orders_data)} orders")
                
                # Log first order structure for debugging (only once)
                if orders_data and len(orders_data) > 0:
                    logger.debug(f"First order structure (keys): {list(orders_data[0].keys())}")
                
                # Group orders by status
                order_stats = {}
                for order in orders_data:
                    # Try multiple field name variations
                    order_id = (
                        order.get('neoOrdNo') or 
                        order.get('nOrdNo') or 
                        order.get('orderId') or 
                        order.get('ordId') or 
                        'N/A'
                    )
                    symbol = (
                        order.get('tradingSymbol') or 
                        order.get('trdSym') or 
                        order.get('symbol') or 
                        'N/A'
                    )
                    order_type = (
                        order.get('orderType') or 
                        order.get('ordTyp') or 
                        order.get('type') or 
                        'N/A'
                    )
                    quantity = (
                        order.get('quantity') or 
                        order.get('qty') or 
                        order.get('filledQty') or 
                        0
                    )
                    price = (
                        order.get('price') or 
                        order.get('prc') or 
                        order.get('avgPrc') or 
                        0
                    )
                    status = (
                        order.get('orderStatus') or 
                        order.get('ordSt') or 
                        order.get('status') or 
                        'N/A'
                    )
                    transaction_type = (
                        order.get('transactionType') or 
                        order.get('trnsTp') or 
                        order.get('txnType') or 
                        'N/A'
                    )
                    
                    # Check for rejection reason
                    rejection_reason = (
                        order.get('rejRsn') or 
                        order.get('rejectionReason') or 
                        order.get('rmk') or
                        ''
                    )
                    
                    if rejection_reason and 'reject' in status.lower():
                        logger.info(f"📝 Order {order_id}: {symbol} {transaction_type} {quantity}@₹{price} - Status: {status} - ❌ Reason: {rejection_reason}")
                    else:
                        logger.info(f"📝 Order {order_id}: {symbol} {transaction_type} {quantity}@₹{price} - Status: {status}")
                    
                    # Count by status
                    order_stats[status] = order_stats.get(status, 0) + 1
                
                logger.info(f" Order Summary: {order_stats}")
            else:
                preview = str(orders)[:300]
                logger.info(f" No orders found (raw preview: {preview})")
            
            return orders
            
        except Exception as e:
            logger.error(f" Error getting orders: {e}")
            return None
    
    def get_order_history(self, order_id: str = None) -> Optional[Dict]:
        """
        Get order history for specific order or all orders
        
        Args:
            order_id (str, optional): Specific order ID to get history for
            
        Returns:
            Dict: Order history data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(f"Retrieving order history{f' for order {order_id}' if order_id else ''}...")
            
            if order_id:
                order_history = client.order_history(order_id=order_id)
            else:
                # Get history for all orders
                order_history = client.order_report()
            
            if "error" in order_history:
                logger.error(" Failed to get order history: {order_history['error'][0]['message']}")
                return None
            
            # Process and display order history
            if 'data' in order_history and order_history['data']:
                history_data = order_history['data']
                logger.info(" Found {len(history_data)} order history entries")
                
                for entry in history_data:
                    order_id = entry.get('neoOrdNo', 'N/A')
                    symbol = entry.get('tradingSymbol', 'N/A')
                    status = entry.get('orderStatus', 'N/A')
                    timestamp = entry.get('orderEntryTime', 'N/A')
                    
                    logger.info(f"{timestamp}: Order {order_id} ({symbol}) - {status}")
            else:
                logger.info("No order history found")
            
            return order_history
            
        except Exception as e:
            logger.error(" Error getting order history: {e}")
            return None
    
    # GTT retrieval not supported; rely only on open orders via get_orders/get_pending_orders
    
    def get_pending_orders(self) -> Optional[List[Dict]]:
        """
        Get only pending orders (not executed/cancelled)
        
        Returns:
            List[Dict]: List of pending orders or None if failed
        """
        orders = self.get_orders()
        if not orders or 'data' not in orders:
            return None
        
        pending_statuses = ['PENDING', 'OPEN', 'PARTIALLY_FILLED', 'TRIGGER_PENDING', 'PARTIALLY FILLED']
        pending_orders = []
        
        for order in orders['data']:
            # Extract status with field name variations
            status = (
                order.get('orderStatus') or 
                order.get('ordSt') or 
                order.get('status') or 
                ''
            )
            # Convert to uppercase for case-insensitive comparison
            status_upper = str(status).upper()
            
            if any(pending_status in status_upper for pending_status in pending_statuses):
                pending_orders.append(order)
        
        if pending_orders:
            logger.warning(f" Found {len(pending_orders)} pending orders")
            for order in pending_orders:
                symbol = order.get('tradingSymbol') or order.get('trdSym') or order.get('symbol') or 'N/A'
                order_type = order.get('orderType') or order.get('ordTyp') or order.get('type') or 'N/A'
                quantity = order.get('quantity') or order.get('qty') or order.get('filledQty') or 0
                price = order.get('price') or order.get('prc') or order.get('avgPrc') or 0
                status = order.get('orderStatus') or order.get('ordSt') or order.get('status') or 'N/A'
                order_id = order.get('neoOrdNo') or order.get('nOrdNo') or order.get('orderId') or 'N/A'
                
                logger.warning(f" [{order_id}] {symbol} {order_type} {quantity}@₹{price} - {status}")
        else:
            logger.warning(" No pending orders found")
        
        return pending_orders if pending_orders else None
    
    def get_executed_orders(self) -> Optional[List[Dict]]:
        """
        Get only executed orders
        
        Returns:
            List[Dict]: List of executed orders or None if failed
        """
        orders = self.get_orders()
        if not orders or 'data' not in orders:
            return None
        
        executed_statuses = ['COMPLETE', 'FILLED', 'EXECUTED']
        executed_orders = []
        
        for order in orders['data']:
            status = order.get('orderStatus', '').upper()
            if any(executed_status in status for executed_status in executed_statuses):
                executed_orders.append(order)
        
        if executed_orders:
            logger.info(" Found {len(executed_orders)} executed orders")
        else:
            logger.info(" No executed orders found")
        
        return executed_orders if executed_orders else None
    
    def get_orders_summary(self) -> Dict:
        """
        Get complete orders summary including all types
        
        Returns:
            Dict: Complete orders data
        """
        print("\n" + "="*50)
        logger.info(" ORDERS SUMMARY")
        print("="*50)
        
        summary = {
            "all_orders": self.get_orders(),
            "pending_orders": self.get_pending_orders(),
            "executed_orders": self.get_executed_orders()
        }
        
        print("="*50)
        logger.info(" Orders summary completed")
        
        return summary
    
    def search_orders_by_symbol(self, symbol: str) -> Optional[List[Dict]]:
        """
        Search orders by trading symbol
        
        Args:
            symbol (str): Trading symbol to search for
            
        Returns:
            List[Dict]: List of orders for the symbol or None if failed
        """
        orders = self.get_orders()
        if not orders or 'data' not in orders:
            return None
        
        symbol_orders = []
        for order in orders['data']:
            if order.get('tradingSymbol', '').upper() == symbol.upper():
                symbol_orders.append(order)
        
        if symbol_orders:
            logger.info(f"Found {len(symbol_orders)} orders for {symbol}")
        else:
            logger.info(f"No orders found for {symbol}")
        
        return symbol_orders if symbol_orders else None
