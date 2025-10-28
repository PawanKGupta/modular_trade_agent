#!/usr/bin/env python3
"""
Tracking Scope Module
Manages which symbols are actively tracked by the system.
Only system-recommended symbols are tracked.

SOLID Principles:
- Single Responsibility: Only manages tracking scope
- Open/Closed: Extensible for different tracking criteria
- Dependency Inversion: Uses abstract file operations from storage
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# Use existing project logger
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger


class TrackingScope:
    """
    Manages the scope of symbols being tracked by the system.
    Enforces that only system-recommended symbols are monitored.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize tracking scope manager.
        
        Args:
            data_dir: Directory for storing tracking data
        """
        self.data_dir = data_dir
        self.tracking_file = os.path.join(data_dir, "system_recommended_symbols.json")
        self._ensure_data_file()
    
    def _ensure_data_file(self) -> None:
        """Create tracking file if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.tracking_file):
            self._save_tracking_data({"symbols": []})
    
    def _load_tracking_data(self) -> Dict[str, Any]:
        """Load tracking data from file."""
        try:
            with open(self.tracking_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tracking data: {e}")
            return {"symbols": []}
    
    def _save_tracking_data(self, data: Dict[str, Any]) -> None:
        """Save tracking data to file."""
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save tracking data: {e}")
    
    def add_tracked_symbol(
        self,
        symbol: str,
        ticker: str,
        initial_order_id: str,
        initial_qty: int,
        pre_existing_qty: int = 0,
        recommendation_source: Optional[str] = None,
        recommendation_verdict: Optional[str] = None
    ) -> str:
        """
        Add a symbol to tracking scope.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            ticker: Full ticker (e.g., 'RELIANCE.NS')
            initial_order_id: Order ID from broker
            initial_qty: Quantity from system order
            pre_existing_qty: Quantity already owned (not tracked)
            recommendation_source: CSV file or source
            recommendation_verdict: Buy/Strong Buy verdict
        
        Returns:
            tracking_id: Unique tracking identifier
        """
        data = self._load_tracking_data()
        
        # Generate unique tracking ID
        tracking_id = f"track-{symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        tracking_entry = {
            "id": tracking_id,
            "symbol": symbol,
            "ticker": ticker,
            "tracking_started_at": datetime.now().isoformat(),
            "tracking_ended_at": None,
            "tracking_status": "active",
            "system_qty": initial_qty,
            "current_tracked_qty": initial_qty,
            "pre_existing_qty": pre_existing_qty,
            "initial_order_id": initial_order_id,
            "all_related_orders": [initial_order_id],
            "recommendation_source": recommendation_source,
            "recommendation_verdict": recommendation_verdict
        }
        
        data["symbols"].append(tracking_entry)
        self._save_tracking_data(data)
        
        logger.info(
            f"Added to tracking scope: {symbol} "
            f"(qty: {initial_qty}, tracking_id: {tracking_id})"
        )
        
        return tracking_id
    
    def is_tracked(self, symbol: str) -> bool:
        """
        Check if a symbol is actively tracked.
        
        Args:
            symbol: Trading symbol to check
        
        Returns:
            True if symbol is actively tracked, False otherwise
        """
        data = self._load_tracking_data()
        
        for entry in data["symbols"]:
            if entry["symbol"] == symbol and entry["tracking_status"] == "active":
                return True
        
        return False
    
    def get_tracking_entry(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get tracking entry for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Tracking entry dict or None if not found
        """
        data = self._load_tracking_data()
        
        for entry in data["symbols"]:
            if entry["symbol"] == symbol and entry["tracking_status"] == "active":
                return entry
        
        return None
    
    def get_tracked_symbols(self, status: str = "active") -> List[str]:
        """
        Get list of tracked symbols.
        
        Args:
            status: Filter by status (active/completed/all)
        
        Returns:
            List of symbol strings
        """
        data = self._load_tracking_data()
        
        if status == "all":
            return [entry["symbol"] for entry in data["symbols"]]
        else:
            return [
                entry["symbol"]
                for entry in data["symbols"]
                if entry["tracking_status"] == status
            ]
    
    def update_tracked_qty(self, symbol: str, qty_change: int) -> None:
        """
        Update the tracked quantity for a symbol.
        
        Args:
            symbol: Trading symbol
            qty_change: Change in quantity (positive for buy, negative for sell)
        """
        data = self._load_tracking_data()
        
        for entry in data["symbols"]:
            if entry["symbol"] == symbol and entry["tracking_status"] == "active":
                old_qty = entry["current_tracked_qty"]
                entry["current_tracked_qty"] = max(0, old_qty + qty_change)
                
                logger.debug(
                    f"Updated tracked qty for {symbol}: "
                    f"{old_qty} -> {entry['current_tracked_qty']}"
                )
                
                # Check if position closed
                if entry["current_tracked_qty"] == 0:
                    self._stop_tracking_internal(entry)
                
                self._save_tracking_data(data)
                return
        
        logger.warning(f"Symbol {symbol} not found in active tracking")
    
    def _stop_tracking_internal(self, entry: Dict[str, Any]) -> None:
        """Internal method to stop tracking (called when qty = 0)."""
        entry["tracking_status"] = "completed"
        entry["tracking_ended_at"] = datetime.now().isoformat()
        
        logger.info(
            f"Stopped tracking {entry['symbol']} - position closed "
            f"(tracking_id: {entry['id']})"
        )
    
    def stop_tracking(self, symbol: str, reason: str = "Position closed") -> None:
        """
        Manually stop tracking a symbol.
        
        Args:
            symbol: Trading symbol
            reason: Reason for stopping tracking
        """
        data = self._load_tracking_data()
        
        for entry in data["symbols"]:
            if entry["symbol"] == symbol and entry["tracking_status"] == "active":
                entry["tracking_status"] = "completed"
                entry["tracking_ended_at"] = datetime.now().isoformat()
                entry["stop_reason"] = reason
                
                self._save_tracking_data(data)
                
                logger.info(f"Stopped tracking {symbol}: {reason}")
                return
        
        logger.warning(f"Symbol {symbol} not found in active tracking")
    
    def add_related_order(self, symbol: str, order_id: str) -> None:
        """
        Add a related order ID to tracking entry (for manual orders).
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to add
        """
        data = self._load_tracking_data()
        
        for entry in data["symbols"]:
            if entry["symbol"] == symbol and entry["tracking_status"] == "active":
                if order_id not in entry["all_related_orders"]:
                    entry["all_related_orders"].append(order_id)
                    self._save_tracking_data(data)
                    logger.debug(f"Added related order {order_id} for {symbol}")
                return


# Singleton instance for easy access
_tracking_scope_instance: Optional[TrackingScope] = None


def get_tracking_scope(data_dir: str = "data") -> TrackingScope:
    """
    Get or create tracking scope singleton instance.
    
    Args:
        data_dir: Directory for tracking data
    
    Returns:
        TrackingScope instance
    """
    global _tracking_scope_instance
    
    if _tracking_scope_instance is None:
        _tracking_scope_instance = TrackingScope(data_dir)
    
    return _tracking_scope_instance


# Convenience functions for external use
def add_tracked_symbol(*args, **kwargs) -> str:
    """Add symbol to tracking scope."""
    return get_tracking_scope().add_tracked_symbol(*args, **kwargs)


def is_tracked(symbol: str) -> bool:
    """Check if symbol is actively tracked."""
    return get_tracking_scope().is_tracked(symbol)


def get_tracking_entry(symbol: str) -> Optional[Dict[str, Any]]:
    """Get tracking entry for symbol."""
    return get_tracking_scope().get_tracking_entry(symbol)


def get_tracked_symbols(status: str = "active") -> List[str]:
    """Get list of tracked symbols."""
    return get_tracking_scope().get_tracked_symbols(status)


def update_tracked_qty(symbol: str, qty_change: int) -> None:
    """Update tracked quantity."""
    return get_tracking_scope().update_tracked_qty(symbol, qty_change)


def stop_tracking(symbol: str, reason: str = "Position closed") -> None:
    """Stop tracking symbol."""
    return get_tracking_scope().stop_tracking(symbol, reason)


def add_related_order(symbol: str, order_id: str) -> None:
    """Add related order to tracking."""
    return get_tracking_scope().add_related_order(symbol, order_id)
