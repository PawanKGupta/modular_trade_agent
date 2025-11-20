#!/usr/bin/env python3
"""
Manual Order Matcher Module
Detects and reconciles manual trades (placed outside system) with tracked symbols.

SOLID Principles:
- Single Responsibility: Only handles manual trade detection and matching
- Open/Closed: Extensible for different matching strategies
- Dependency Inversion: Abstract broker API interactions

Phase 2 Feature: Manual order matching during reconciliation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Use existing project logger
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

# Import Phase 1 modules
from .tracking_scope import TrackingScope, get_tracking_scope
from .order_tracker import OrderTracker, get_order_tracker


class ManualOrderMatcher:
    """
    Detects and reconciles manual trades with tracked symbols.
    Updates tracking quantities when manual buys/sells are detected.
    """

    def __init__(
        self,
        tracking_scope: Optional[TrackingScope] = None,
        order_tracker: Optional[OrderTracker] = None,
    ):
        """
        Initialize manual order matcher.

        Args:
            tracking_scope: TrackingScope instance (uses singleton if None)
            order_tracker: OrderTracker instance (uses singleton if None)
        """
        self.tracking_scope = tracking_scope or get_tracking_scope()
        self.order_tracker = order_tracker or get_order_tracker()

    def reconcile_holdings_with_tracking(
        self, broker_holdings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reconcile broker holdings with tracking scope.
        Detects manual trades for tracked symbols and updates quantities.

        Args:
            broker_holdings: List of holdings from broker (each with symbol, qty, etc.)

        Returns:
            Dict with reconciliation results: {
                'matched': int,
                'manual_buys_detected': int,
                'manual_sells_detected': int,
                'discrepancies': List[Dict],
                'updated_symbols': List[str]
            }
        """
        logger.info("Starting manual trade reconciliation")

        tracked_symbols = self.tracking_scope.get_tracked_symbols(status="active")

        if not tracked_symbols:
            logger.info("No tracked symbols to reconcile")
            return {
                "matched": 0,
                "manual_buys_detected": 0,
                "manual_sells_detected": 0,
                "discrepancies": [],
                "updated_symbols": [],
            }

        logger.info(f"Reconciling {len(tracked_symbols)} tracked symbol(s)")

        # Convert holdings to dict for easy lookup
        holdings_dict = {}
        for holding in broker_holdings:
            symbol = holding.get("symbol") or holding.get("tradingSymbol", "").replace("-EQ", "")
            if symbol:
                holdings_dict[symbol.upper()] = holding

        results = {
            "matched": 0,
            "manual_buys_detected": 0,
            "manual_sells_detected": 0,
            "discrepancies": [],
            "updated_symbols": [],
        }

        # Check each tracked symbol
        for symbol in tracked_symbols:
            tracking_entry = self.tracking_scope.get_tracking_entry(symbol)

            if not tracking_entry:
                logger.warning(f"Tracking entry not found for {symbol}")
                continue

            system_qty = tracking_entry["current_tracked_qty"]
            pre_existing_qty = tracking_entry.get("pre_existing_qty", 0)

            # Get broker quantity
            broker_holding = holdings_dict.get(symbol.upper())
            broker_qty = 0

            if broker_holding:
                broker_qty = int(
                    broker_holding.get("qty", 0) or broker_holding.get("quantity", 0) or 0
                )

            # Expected quantity = system qty + pre-existing qty
            expected_total_qty = system_qty + pre_existing_qty

            # Check for discrepancy
            if broker_qty == expected_total_qty:
                # Perfect match - no manual trades
                logger.debug(
                    f"[OK] {symbol}: Broker qty ({broker_qty}) matches expected ({expected_total_qty})"
                )
                results["matched"] += 1
                continue

            # Discrepancy detected - manual trade likely
            qty_diff = broker_qty - expected_total_qty

            logger.info(
                f"[WARN] {symbol}: Quantity mismatch detected\n"
                f"  Expected: {expected_total_qty} (system: {system_qty}, pre-existing: {pre_existing_qty})\n"
                f"  Broker:   {broker_qty}\n"
                f"  Diff:     {qty_diff:+d}"
            )

            discrepancy = {
                "symbol": symbol,
                "system_qty": system_qty,
                "pre_existing_qty": pre_existing_qty,
                "expected_total_qty": expected_total_qty,
                "broker_qty": broker_qty,
                "qty_diff": qty_diff,
                "timestamp": datetime.now().isoformat(),
            }

            # Determine if manual buy or sell
            if qty_diff > 0:
                # Manual buy detected
                logger.info(f"? Manual BUY detected for {symbol}: +{qty_diff} shares")
                results["manual_buys_detected"] += 1
                discrepancy["trade_type"] = "MANUAL_BUY"
            elif qty_diff < 0:
                # Manual sell detected
                logger.info(f"? Manual SELL detected for {symbol}: {qty_diff} shares")
                results["manual_sells_detected"] += 1
                discrepancy["trade_type"] = "MANUAL_SELL"

            results["discrepancies"].append(discrepancy)

            # Try to find manual orders in broker order book
            manual_orders = self._find_manual_orders_for_symbol(
                symbol, abs(qty_diff), tracking_entry
            )

            if manual_orders:
                logger.info(f"Found {len(manual_orders)} potential manual order(s) for {symbol}")
                discrepancy["manual_orders"] = manual_orders

                # Add to related orders
                for order in manual_orders:
                    order_id = order.get("order_id")
                    if order_id:
                        self.tracking_scope.add_related_order(symbol, order_id)

            # Update tracking quantity to match reality
            self.tracking_scope.update_tracked_qty(symbol, qty_diff)
            results["updated_symbols"].append(symbol)

            logger.info(
                f"[OK] Updated tracking for {symbol}: " f"{system_qty} -> {system_qty + qty_diff}"
            )

        # Log summary
        logger.info(
            f"Reconciliation complete: "
            f"{results['matched']} matched, "
            f"{results['manual_buys_detected']} manual buys, "
            f"{results['manual_sells_detected']} manual sells, "
            f"{len(results['updated_symbols'])} updated"
        )

        return results

    def _find_manual_orders_for_symbol(
        self, symbol: str, qty: int, tracking_entry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Search for manual orders in recent broker order book.

        Args:
            symbol: Trading symbol
            qty: Quantity to look for
            tracking_entry: Tracking entry with order history

        Returns:
            List of potential manual orders
        """
        # Get all related orders for this symbol (system orders)
        known_order_ids = set(tracking_entry.get("all_related_orders", []))

        # Try to get recent orders from broker (implementation would need broker client)
        # For now, return empty list as this requires broker API integration
        # This is a placeholder for Phase 3 enhancement

        logger.debug(
            f"Manual order search for {symbol} (qty: {qty}) - "
            f"skipping (requires broker API integration)"
        )

        return []

    def detect_position_closures(self, broker_holdings: List[Dict[str, Any]]) -> List[str]:
        """
        Detect tracked symbols that have been fully sold (position closed).

        Args:
            broker_holdings: List of holdings from broker

        Returns:
            List of symbols where position was closed
        """
        tracked_symbols = self.tracking_scope.get_tracked_symbols(status="active")

        if not tracked_symbols:
            return []

        # Convert holdings to dict
        holdings_dict = {}
        for holding in broker_holdings:
            symbol = holding.get("symbol") or holding.get("tradingSymbol", "").replace("-EQ", "")
            if symbol:
                holdings_dict[symbol.upper()] = holding

        closed_positions = []

        for symbol in tracked_symbols:
            tracking_entry = self.tracking_scope.get_tracking_entry(symbol)

            if not tracking_entry:
                continue

            # Check if symbol is no longer in holdings
            if symbol.upper() not in holdings_dict:
                # Position was closed
                logger.info(
                    f"? Position closed detected: {symbol} "
                    f"(was tracking {tracking_entry['current_tracked_qty']} shares)"
                )

                # Stop tracking
                self.tracking_scope.stop_tracking(
                    symbol, reason="Position fully closed (manual sell detected)"
                )

                closed_positions.append(symbol)

        return closed_positions

    def reconcile_partial_positions(self, broker_holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Handle partial position closures (partial manual sells).

        Args:
            broker_holdings: List of holdings from broker

        Returns:
            Dict with results: {
                'partial_sells': List[Dict],
                'total_shares_sold': int
            }
        """
        tracked_symbols = self.tracking_scope.get_tracked_symbols(status="active")

        if not tracked_symbols:
            return {"partial_sells": [], "total_shares_sold": 0}

        # Convert holdings to dict
        holdings_dict = {}
        for holding in broker_holdings:
            symbol = holding.get("symbol") or holding.get("tradingSymbol", "").replace("-EQ", "")
            if symbol:
                holdings_dict[symbol.upper()] = holding

        results = {"partial_sells": [], "total_shares_sold": 0}

        for symbol in tracked_symbols:
            tracking_entry = self.tracking_scope.get_tracking_entry(symbol)

            if not tracking_entry:
                continue

            system_qty = tracking_entry["current_tracked_qty"]
            pre_existing_qty = tracking_entry.get("pre_existing_qty", 0)

            broker_holding = holdings_dict.get(symbol.upper())

            if not broker_holding:
                # Full closure - handled by detect_position_closures
                continue

            broker_qty = int(broker_holding.get("qty", 0) or broker_holding.get("quantity", 0) or 0)
            expected_total = system_qty + pre_existing_qty

            # Check if partial sell (broker qty < expected)
            if broker_qty < expected_total:
                shares_sold = expected_total - broker_qty

                logger.info(
                    f"? Partial sell detected: {symbol} "
                    f"({shares_sold} shares sold, {broker_qty} remaining)"
                )

                results["partial_sells"].append(
                    {
                        "symbol": symbol,
                        "shares_sold": shares_sold,
                        "remaining": broker_qty,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                results["total_shares_sold"] += shares_sold

        return results

    def get_reconciliation_summary(self, reconciliation_results: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of reconciliation.

        Args:
            reconciliation_results: Results from reconcile_holdings_with_tracking

        Returns:
            Formatted summary string
        """
        summary = ["=" * 60]
        summary.append("MANUAL TRADE RECONCILIATION SUMMARY")
        summary.append("=" * 60)
        summary.append(f"Matched (no changes):     {reconciliation_results['matched']}")
        summary.append(
            f"Manual Buys Detected:     {reconciliation_results['manual_buys_detected']}"
        )
        summary.append(
            f"Manual Sells Detected:    {reconciliation_results['manual_sells_detected']}"
        )
        summary.append(
            f"Symbols Updated:          {len(reconciliation_results['updated_symbols'])}"
        )
        summary.append("=" * 60)

        if reconciliation_results["discrepancies"]:
            summary.append("\nDISCREPANCIES DETECTED:")
            for disc in reconciliation_results["discrepancies"]:
                summary.append(f"\n{disc['symbol']}:")
                summary.append(f"  Type:     {disc['trade_type']}")
                summary.append(f"  Expected: {disc['expected_total_qty']}")
                summary.append(f"  Broker:   {disc['broker_qty']}")
                summary.append(f"  Diff:     {disc['qty_diff']:+d}")

        if reconciliation_results["updated_symbols"]:
            summary.append(
                f"\nUpdated Symbols: {', '.join(reconciliation_results['updated_symbols'])}"
            )

        return "\n".join(summary)


# Singleton instance
_matcher_instance: Optional[ManualOrderMatcher] = None


def get_manual_order_matcher(
    tracking_scope: Optional[TrackingScope] = None, order_tracker: Optional[OrderTracker] = None
) -> ManualOrderMatcher:
    """
    Get or create manual order matcher singleton.

    Args:
        tracking_scope: TrackingScope instance
        order_tracker: OrderTracker instance

    Returns:
        ManualOrderMatcher instance
    """
    global _matcher_instance

    if _matcher_instance is None:
        _matcher_instance = ManualOrderMatcher(tracking_scope, order_tracker)

    return _matcher_instance
