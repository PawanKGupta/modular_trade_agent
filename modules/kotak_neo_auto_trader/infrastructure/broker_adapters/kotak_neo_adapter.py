"""
Kotak Neo Broker Adapter
Adapts Kotak Neo SDK to IBrokerGateway interface
"""

import inspect
from typing import List, Optional, Dict, Any
from datetime import datetime

# Import from existing legacy modules
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...domain import (
    Order, Holding, Money, IBrokerGateway,
    OrderType, TransactionType, OrderStatus, ProductType, OrderVariety, Exchange
)


class KotakNeoBrokerAdapter(IBrokerGateway):
    """
    Adapter for Kotak Neo API
    
    Implements IBrokerGateway interface using existing auth and SDK
    Adapts between domain entities and raw SDK responses
    """
    
    def __init__(self, auth_handler):
        """
        Initialize adapter with auth handler
        
        Args:
            auth_handler: Authentication handler (from infrastructure.session)
        """
        self.auth_handler = auth_handler
        self._client = None
        self._connected = False
    
    # Connection Management
    
    def connect(self) -> bool:
        """Establish connection to broker"""
        try:
            if self.auth_handler.login():
                self._client = self.auth_handler.get_client()
                self._connected = True
                logger.info("✅ Connected to Kotak Neo broker")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from broker"""
        try:
            if self.auth_handler.logout():
                self._client = None
                self._connected = False
                logger.info("✅ Disconnected from Kotak Neo broker")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Disconnect failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self._connected and self._client is not None
    
    # Order Management
    
    def place_order(self, order: Order) -> str:
        """Place an order and return order ID"""
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")
        
        # Build payload from domain order
        payload = self._build_order_payload(order)
        
        # Try multiple SDK method names (resilience pattern from legacy code)
        for method_name in ["place_order", "order_place", "placeorder"]:
            try:
                if not hasattr(self._client, method_name):
                    continue
                
                method = getattr(self._client, method_name)
                params = self._adapt_payload_to_method(method, payload)
                
                logger.info(f"📤 Placing {order.transaction_type.value} order: {order.symbol} x{order.quantity}")
                response = method(**params)
                
                # Check for errors
                if self._is_error_response(response):
                    logger.error(f"❌ Order rejected: {response}")
                    continue
                
                # Extract order ID
                order_id = self._extract_order_id(response)
                if order_id:
                    logger.info(f"✅ Order placed: {order_id}")
                    return order_id
                    
            except Exception as e:
                logger.warning(f"⚠️ Method {method_name} failed: {e}")
                continue
        
        raise RuntimeError("Failed to place order with all available methods")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")
        
        for method_name in ["cancel_order", "order_cancel", "cancelOrder"]:
            try:
                if not hasattr(self._client, method_name):
                    continue
                
                method = getattr(self._client, method_name)
                
                # Try to determine parameter name
                try:
                    params = set(inspect.signature(method).parameters.keys())
                    payload = {}
                    for key in ["order_id", "orderId", "neoOrdNo", "ordId", "id"]:
                        if key in params:
                            payload[key] = order_id
                            break
                    if not payload:
                        # Try positional
                        response = method(order_id)
                    else:
                        response = method(**payload)
                    
                    logger.info(f"✅ Cancelled order: {order_id}")
                    return True
                except Exception:
                    continue
                    
            except Exception as e:
                logger.warning(f"⚠️ Cancel via {method_name} failed: {e}")
                continue
        
        return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order details by ID"""
        orders = self.get_all_orders()
        for order in orders:
            if order.order_id == order_id:
                return order
        return None
    
    def get_all_orders(self) -> List[Order]:
        """Get all orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")
        
        try:
            # Try multiple method names
            for method_name in ["order_report", "get_order_report", "orderBook", "orders"]:
                if hasattr(self._client, method_name):
                    response = getattr(self._client, method_name)()
                    if isinstance(response, dict) and "data" in response:
                        return self._parse_orders_response(response["data"])
            return []
        except Exception as e:
            logger.error(f"❌ Failed to get orders: {e}")
            return []
    
    def get_pending_orders(self) -> List[Order]:
        """Get pending/open orders"""
        all_orders = self.get_all_orders()
        return [order for order in all_orders if order.is_active()]
    
    # Portfolio Management
    
    def get_holdings(self) -> List[Holding]:
        """Get portfolio holdings"""
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")
        
        try:
            # Try multiple method names
            for method_name in ["holdings", "get_holdings", "portfolio_holdings"]:
                if hasattr(self._client, method_name):
                    response = getattr(self._client, method_name)()
                    if isinstance(response, dict) and "data" in response:
                        return self._parse_holdings_response(response["data"])
            return []
        except Exception as e:
            logger.error(f"❌ Failed to get holdings: {e}")
            return []
    
    def get_holding(self, symbol: str) -> Optional[Holding]:
        """Get holding for specific symbol"""
        holdings = self.get_holdings()
        for holding in holdings:
            if holding.symbol.upper() == symbol.upper():
                return holding
        return None
    
    # Account Management
    
    def get_account_limits(self) -> Dict[str, Any]:
        """Get account limits and margins"""
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")
        
        try:
            response = self._client.limits(segment="ALL", exchange="ALL")
            if isinstance(response, dict) and "data" in response:
                data = response["data"]
                return {
                    "available_cash": Money.from_float(float(data.get("cash", 0))),
                    "margin_used": Money.from_float(float(data.get("marginUsed", 0))),
                    "margin_available": Money.from_float(float(data.get("marginAvailable", 0))),
                    "collateral": Money.from_float(float(data.get("collateral", 0)))
                }
            return {}
        except Exception as e:
            logger.error(f"❌ Failed to get account limits: {e}")
            return {}
    
    def get_available_balance(self) -> Money:
        """Get available cash balance"""
        limits = self.get_account_limits()
        return limits.get("available_cash", Money.zero())
    
    # Utility Methods
    
    def search_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Search orders by symbol"""
        all_orders = self.get_all_orders()
        return [order for order in all_orders if order.symbol.upper() == symbol.upper()]
    
    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        """Cancel all pending BUY orders for a symbol"""
        pending = self.get_pending_orders()
        cancelled = 0
        
        for order in pending:
            if order.symbol.upper() == symbol.upper() and order.is_buy_order():
                if self.cancel_order(order.order_id):
                    cancelled += 1
        
        return cancelled
    
    # Helper Methods (Private)
    
    def _build_order_payload(self, order: Order) -> dict:
        """Build API payload from domain order"""
        return {
            "exchange": order.exchange.value,
            "tradingSymbol": order.symbol,
            "transactionType": "B" if order.transaction_type == TransactionType.BUY else "S",
            "quantity": str(order.quantity),
            "price": str(order.price.amount) if order.price else "0",
            "product": order.product_type.value,
            "orderType": self._map_order_type(order.order_type),
            "validity": order.validity,
            "variety": order.variety.value,
            "disclosedQuantity": 0,
            "triggerPrice": "0",
            "remarks": order.remarks,
        }
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map domain OrderType to SDK order type"""
        mapping = {
            OrderType.MARKET: "MKT",
            OrderType.LIMIT: "L",
            OrderType.STOP_LOSS: "SL",
            OrderType.STOP_LOSS_MARKET: "SL-M",
        }
        return mapping.get(order_type, "MKT")
    
    def _adapt_payload_to_method(self, method, payload: dict) -> dict:
        """Adapt payload to method signature"""
        try:
            params = set(inspect.signature(method).parameters.keys())
        except (ValueError, TypeError):
            return payload
        
        adapted = {}
        for key, value in payload.items():
            if key in params:
                adapted[key] = value
        
        # Handle exchange_segment if needed
        if "exchange_segment" in params and "exchange" in payload:
            adapted["exchange_segment"] = payload["exchange"]
        
        return adapted
    
    def _is_error_response(self, response) -> bool:
        """Check if response contains error"""
        if isinstance(response, dict):
            keys_lower = {str(k).lower() for k in response.keys()}
            return any(k in keys_lower for k in ("error", "errors"))
        resp_text = str(response).lower()
        return "error" in resp_text or "invalid" in resp_text
    
    def _extract_order_id(self, response) -> Optional[str]:
        """Extract order ID from response"""
        if isinstance(response, dict):
            for key in ["neoOrdNo", "orderId", "order_id", "ordId", "id"]:
                if key in response:
                    return str(response[key])
                if "data" in response and isinstance(response["data"], dict):
                    if key in response["data"]:
                        return str(response["data"][key])
        return None
    
    def _parse_orders_response(self, data: list) -> List[Order]:
        """Parse orders from API response"""
        orders = []
        for item in data:
            try:
                order = Order(
                    symbol=str(item.get("tradingSymbol", "")),
                    quantity=int(item.get("quantity", 0)),
                    order_type=self._parse_order_type(item.get("orderType", "MKT")),
                    transaction_type=self._parse_transaction_type(item.get("transactionType", "B")),
                    price=Money.from_float(float(item.get("price", 0))) if item.get("price") else None,
                    order_id=str(item.get("neoOrdNo", "")),
                    status=self._parse_order_status(item.get("orderStatus", "PENDING"))
                )
                orders.append(order)
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse order: {e}")
                continue
        return orders
    
    def _parse_holdings_response(self, data: list) -> List[Holding]:
        """Parse holdings from API response"""
        holdings = []
        for item in data:
            try:
                symbol = self._extract_field(item, ["tradingSymbol", "symbol", "instrumentName", "securitySymbol"])
                quantity = int(self._extract_field(item, ["quantity", "qty", "netQuantity", "holdingsQuantity"], 0))
                avg_price = float(self._extract_field(item, ["avgPrice", "averagePrice", "buyAvg", "buyAvgPrice"], 0))
                ltp = float(self._extract_field(item, ["ltp", "lastPrice", "lastTradedPrice", "ltpPrice"], 0))
                
                holding = Holding(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=Money.from_float(avg_price),
                    current_price=Money.from_float(ltp),
                    last_updated=datetime.now()
                )
                holdings.append(holding)
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse holding: {e}")
                continue
        return holdings
    
    def _extract_field(self, data: dict, keys: list, default=None):
        """Extract field from data trying multiple keys"""
        for key in keys:
            if key in data:
                return data[key]
        return default
    
    def _parse_order_type(self, value: str) -> OrderType:
        """Parse order type from string"""
        return OrderType.from_string(value)
    
    def _parse_transaction_type(self, value: str) -> TransactionType:
        """Parse transaction type from string"""
        return TransactionType.from_string(value)
    
    def _parse_order_status(self, value: str) -> OrderStatus:
        """Parse order status from string"""
        return OrderStatus.from_string(value)
