#!/usr/bin/env python3
"""
Portfolio Management Module for Kotak Neo API
Handles portfolio holdings, positions, and account information
"""

from typing import Optional, Dict, List
# Import existing project logger
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .auth_handler import handle_reauth
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auth_handler import handle_reauth


class KotakNeoPortfolio:
    """
    Portfolio management for Kotak Neo API
    """
    
    def __init__(self, auth: KotakNeoAuth, price_manager=None):
        """
        Initialize portfolio manager
        
        Args:
            auth (KotakNeoAuth): Authenticated session instance
            price_manager: Optional LivePriceCache/LivePriceManager for real-time WebSocket LTP
        """
        self.auth = auth
        self.price_manager = price_manager
        logger.info("KotakNeoPortfolio initialized")
    
    @handle_reauth
    def get_holdings(self) -> Optional[Dict]:
        """
        Get portfolio holdings (stocks owned) with fallbacks and raw logging.
        """
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
            logger.info(" Retrieving portfolio holdings...")
            holdings = _call_any(["holdings", "get_holdings", "portfolio_holdings", "getPortfolioHoldings"]) or {}
            
            if isinstance(holdings, dict) and "error" in holdings:
                logger.error(f" Failed to get holdings: {holdings['error']}")
                return None
            
            # Process and display holdings
            if isinstance(holdings, dict) and 'data' in holdings and holdings['data']:
                holdings_data = holdings['data']
                logger.info(f" Found {len(holdings_data)} holdings in portfolio")
                
                # Display summary (with robust field mapping and fallbacks)
                def _num(x):
                    try:
                        return float(x)
                    except Exception:
                        return 0.0
                total_value = 0.0
                for holding in holdings_data:
                    stock_name = (
                        holding.get('tradingSymbol') or
                        holding.get('symbol') or
                        holding.get('instrumentName') or
                        holding.get('securitySymbol') or
                        holding.get('securityname') or
                        'N/A'
                    )
                    quantity = int(
                        holding.get('quantity') or
                        holding.get('qty') or
                        holding.get('netQuantity') or
                        holding.get('holdingsQuantity') or 0
                    )
                    ltp = _num(
                        holding.get('ltp') or
                        holding.get('lastPrice') or
                        holding.get('lastTradedPrice') or
                        holding.get('ltpPrice') or 0
                    )
                    avg_price = _num(
                        holding.get('avgPrice') or
                        holding.get('averagePrice') or
                        holding.get('buyAvg') or
                        holding.get('buyAvgPrice') or 0
                    )
                    market_value = _num(
                        holding.get('marketValue') or
                        holding.get('market_value') or 0
                    )
                    
                    # If LTP is 0 (market closed), try multiple sources in priority order
                    if ltp == 0 and quantity > 0:
                        # Priority 1: Try WebSocket LTP (real-time, most accurate)
                        if self.price_manager:
                            try:
                                from .utils.price_manager_utils import get_ltp_from_manager
                                from .utils.symbol_utils import extract_ticker_base, get_lookup_symbol
                                
                                base_symbol = stock_name.replace('-EQ', '').replace('-BE', '').replace('-BL', '').replace('-BZ', '').strip()
                                ticker = f"{base_symbol}.NS"
                                lookup_symbol = get_lookup_symbol(stock_name, base_symbol)
                                
                                websocket_ltp = get_ltp_from_manager(self.price_manager, lookup_symbol, ticker)
                                if websocket_ltp and websocket_ltp > 0:
                                    ltp = websocket_ltp
                                    logger.debug(f"{stock_name}: Fetched LTP from WebSocket: ₹{ltp:.2f}")
                            except Exception as e:
                                logger.debug(f"{stock_name}: WebSocket LTP fetch failed: {e}")
                        
                        # Priority 2: Use market_value to calculate effective price (reliable when API provides it)
                        if ltp == 0 and market_value > 0:
                            ltp = market_value / quantity
                            logger.debug(f"{stock_name}: Using market_value/quantity as LTP: ₹{ltp:.2f}")
                        
                        # Priority 3: Fallback to yfinance (simple call, no validation)
                        if ltp == 0:
                            try:
                                import yfinance as yf
                                base_symbol = stock_name.replace('-EQ', '').replace('-BE', '').replace('-BL', '').replace('-BZ', '').strip()
                                ticker = f"{base_symbol}.NS"
                                stock = yf.Ticker(ticker)
                                info = stock.info
                                # Try to get current price or previous close
                                yf_ltp = info.get('currentPrice') or info.get('previousClose') or 0
                                if yf_ltp > 0:
                                    ltp = yf_ltp
                                    logger.debug(f"{stock_name}: Fetched LTP from yfinance: ₹{ltp:.2f}")
                            except Exception as e:
                                logger.debug(f"{stock_name}: Could not fetch LTP from yfinance: {e}")
                    
                    if market_value == 0 and quantity > 0:
                        # Compute value when missing using LTP, else avg_price
                        ref = ltp if ltp > 0 else avg_price
                        market_value = ref * quantity
                    
                    pnl = _num(
                        holding.get('pnl') or
                        holding.get('unrealizedPnl') or
                        holding.get('unrealisedPNL') or 0
                    )
                    
                    # Calculate P&L if not provided by API
                    if pnl == 0 and quantity > 0 and avg_price > 0:
                        # Use LTP if available, otherwise use market_value
                        if ltp > 0:
                            pnl = (ltp - avg_price) * quantity
                        elif market_value > 0:
                            # Calculate P&L from market value (most reliable when API provides it)
                            pnl = market_value - (avg_price * quantity)
                    logger.info(f"{stock_name}: Qty={quantity}, LTP=₹{ltp:.2f}, Value=₹{market_value:.2f}, P&L=₹{pnl:.2f}")
                    total_value += market_value
                logger.info(f"Total Portfolio Value: ₹{total_value:.2f}")
            else:
                preview = str(holdings)[:300]
                logger.info(f" No holdings found in portfolio (raw preview: {preview})")
            
            return holdings
            
        except Exception as e:
            logger.error(f" Error getting holdings: {e}")
            return None
    
    @handle_reauth
    def get_positions(self) -> Optional[Dict]:
        """
        Get current positions (open trades for the day)
        
        Returns:
            Dict: Positions data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(" Retrieving current positions...")
            positions = client.positions()
            
            if "error" in positions:
                logger.error(" Failed to get positions: {positions['error'][0]['message']}")
                return None
            
            # Process and display positions
            if 'data' in positions and positions['data']:
                positions_data = positions['data']
                logger.info(" Found {len(positions_data)} positions")
                
                active_positions = 0
                for position in positions_data:
                    symbol = position.get('tradingSymbol', 'N/A')
                    net_quantity = position.get('netQuantity', 0)
                    buy_quantity = position.get('buyQuantity', 0)
                    sell_quantity = position.get('sellQuantity', 0)
                    pnl = position.get('pnl', 0)
                    ltp = position.get('ltp', 0)
                    
                    if net_quantity != 0:  # Only show positions with non-zero quantity
                        logger.info(" {symbol}: Net={net_quantity} (Buy={buy_quantity}, Sell={sell_quantity}), P&L=₹{pnl}, LTP=₹{ltp}")
                        active_positions += 1
                
                if active_positions == 0:
                    logger.info(" No active positions found")
            else:
                logger.info(" No positions found")
            
            return positions
            
        except Exception as e:
            logger.error(" Error getting positions: {e}")
            return None
    
    @handle_reauth
    def get_limits(self) -> Optional[Dict]:
        """
        Get account limits and margins
        
        Returns:
            Dict: Limits data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(" Retrieving account limits...")
            limits = client.limits(segment="ALL", exchange="ALL")
            
            if isinstance(limits, dict) and "error" in limits:
                try:
                    msg = limits['error'][0]['message'] if isinstance(limits.get('error'), list) else limits.get('error')
                except Exception:
                    msg = limits.get('error')
                logger.error(f" Failed to get limits: {msg}")
                return None
            
            # Normalize response: ensure a {'data': {...}} shape for downstream consumers
            normalized = None
            if isinstance(limits, dict) and 'data' in limits and isinstance(limits['data'], dict):
                normalized = limits
                data = limits['data']
            elif isinstance(limits, dict):
                # Some environments return flat dict without 'data'
                data = limits
                normalized = {'data': data}
            else:
                # Unknown shape
                logger.info(f" Limits API returned non-dict payload: {type(limits)}")
                return None

            # Display limits summary with comprehensive field checking
            try:
                logger.info(f" Limits API response keys: {list(data.keys())}")
            except Exception:
                pass
            
            # Try multiple field name variants
            cash = data.get('cash') or data.get('availableCash') or data.get('available_cash') or 0
            margin_used = data.get('marginUsed') or data.get('margin_used') or data.get('usedMargin') or 0
            margin_available = (
                data.get('marginAvailable') or 
                data.get('margin_available') or 
                data.get('availableMargin') or 
                data.get('available_margin') or 0
            )
            
            logger.info(f"Cash: ₹{cash}")
            logger.info(f" Margin Used: ₹{margin_used}")
            logger.info(f" Margin Available: ₹{margin_available}")
            
            return normalized
            
        except Exception as e:
            logger.error(f" Error getting limits: {e}")
            return None
    
    def get_portfolio_summary(self) -> Dict:
        """
        Get complete portfolio summary
        
        Returns:
            Dict: Complete portfolio data
        """
        print("\n" + "="*50)
        logger.info(" PORTFOLIO SUMMARY")
        print("="*50)
        
        summary = {
            "holdings": self.get_holdings(),
            "positions": self.get_positions(),
            "limits": self.get_limits()
        }
        
        print("="*50)
        logger.info(" Portfolio summary completed")
        
        return summary
    
    def calculate_portfolio_value(self) -> Optional[float]:
        """
        Calculate total portfolio value
        
        Returns:
            float: Total portfolio value or None if failed
        """
        holdings = self.get_holdings()
        if not holdings or 'data' not in holdings:
            return None
        
        total_value = 0
        for holding in holdings['data']:
            market_value = holding.get('marketValue', 0)
            total_value += market_value
        
        return total_value
    
    def get_stock_details(self, symbol: str) -> Optional[Dict]:
        """
        Get details for a specific stock in portfolio
        
        Args:
            symbol (str): Stock symbol to search for
            
        Returns:
            Dict: Stock details or None if not found
        """
        holdings = self.get_holdings()
        if not holdings or 'data' not in holdings:
            return None
        
        for holding in holdings['data']:
            if holding.get('tradingSymbol', '').upper() == symbol.upper():
                return holding
        
        logger.error(" Stock {symbol} not found in portfolio")
        return None