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

# Use existing project logger
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger  # noqa: E402

from .order_tracker import OrderTracker, get_order_tracker  # noqa: E402

# Import Phase 1 modules
from .tracking_scope import TrackingScope, get_tracking_scope  # noqa: E402


class ManualOrderMatcher:
    """
    Detects and reconciles manual trades with tracked symbols.
    Updates tracking quantities when manual buys/sells are detected.
    """

    def __init__(
        self,
        tracking_scope: TrackingScope | None = None,
        order_tracker: OrderTracker | None = None,
    ):
        """
        Initialize manual order matcher.

        Args:
            tracking_scope: TrackingScope instance (uses singleton if None)
            order_tracker: OrderTracker instance (uses singleton if None)
        """
        self.tracking_scope = tracking_scope or get_tracking_scope()
        self.order_tracker = order_tracker or get_order_tracker()

    def validate_and_clean_pre_existing_qty(
        self, symbol: str, broker_qty: int, system_qty: int, pre_existing_qty: int
    ) -> int:
        """
        Validate and clean up stale pre_existing_qty values.

        Args:
            symbol: Symbol being checked
            broker_qty: Current broker holding quantity
            system_qty: System tracked quantity
            pre_existing_qty: Pre-existing quantity from tracking entry

        Returns:
            Validated pre_existing_qty (may be reset to 0 if stale)
        """
        # If broker_qty is 0 and pre_existing_qty is large, likely stale
        if broker_qty == 0 and pre_existing_qty > 0:
            if system_qty == 0:
                # Both are 0, pre_existing_qty is definitely stale
                logger.warning(
                    f"[CLEANUP] {symbol}: Resetting stale pre_existing_qty "
                    f"from {pre_existing_qty} to 0 (broker_qty=0, system_qty=0)"
                )
                return 0
            elif pre_existing_qty > system_qty * 2:
                # Pre-existing is more than 2x system qty, likely stale
                logger.warning(
                    f"[CLEANUP] {symbol}: Pre_existing_qty ({pre_existing_qty}) "
                    f"seems suspiciously large compared to system_qty ({system_qty}). "
                    f"Consider manual review."
                )

        return pre_existing_qty

    def reconcile_holdings_with_tracking(  # noqa: PLR0912, PLR0915
        self, broker_holdings: list[dict[str, Any]]
    ) -> dict[str, Any]:
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

        # Extract holdings symbols for comparison
        holdings_symbols = []
        holdings_dict = {}
        for holding in broker_holdings:
            # Try multiple field names for symbol extraction
            symbol = (
                holding.get("symbol")
                or holding.get("tradingSymbol")
                or holding.get("displaySymbol")
                or holding.get("securitySymbol")
                or ""
            )
            if symbol:
                # Extract base symbol using utility function for consistency
                # After migration, holdings may have full symbols (e.g., "RELIANCE-EQ")
                # We extract base symbol for matching with tracking scope (which uses base symbols)
                from .utils.symbol_utils import extract_base_symbol  # noqa: PLC0415

                base_symbol = extract_base_symbol(symbol)
                if base_symbol:
                    holdings_symbols.append(base_symbol.upper())
                    holdings_dict[base_symbol.upper()] = holding

        logger.info(
            f"Found {len(holdings_symbols)} holdings in portfolio: {', '.join(holdings_symbols)}"
        )

        tracked_symbols = self.tracking_scope.get_tracked_symbols(status="active")
        all_tracked_symbols = self.tracking_scope.get_tracked_symbols(status="all")
        completed_tracked_symbols = self.tracking_scope.get_tracked_symbols(status="completed")

        logger.info(
            f"Tracking scope status: {len(tracked_symbols)} active, "
            f"{len(completed_tracked_symbols)} completed, "
            f"{len(all_tracked_symbols)} total tracked symbols"
        )

        if tracked_symbols:
            logger.info(f"Active tracked symbols: {', '.join(tracked_symbols)}")
        if completed_tracked_symbols:
            logger.info(f"Completed tracked symbols: {', '.join(completed_tracked_symbols)}")
            # Log detailed information about completed entries to diagnose issues
            # Wrap in try-catch to handle corrupted data gracefully
            try:
                logger.info("Completed tracking entries details:")
                for completed_symbol in completed_tracked_symbols:
                    try:
                        entry = self.tracking_scope.get_tracking_entry(
                            completed_symbol, status="completed"
                        )
                        if entry:
                            completed_at = entry.get("tracking_ended_at", "unknown")
                            tracked_qty = entry.get("current_tracked_qty", 0)
                            system_qty = entry.get("system_qty", 0)
                            initial_order_id = entry.get("initial_order_id", "unknown")
                            ticker = entry.get("ticker", "unknown")
                            logger.info(
                                f"  Symbol: {completed_symbol}, Ticker: {ticker}, "
                                f"System Qty: {system_qty}, Final Tracked Qty: {tracked_qty}, "
                                f"Initial Order ID: {initial_order_id}, "
                                f"Completed At: {completed_at}"
                            )
                        else:
                            logger.warning(
                                f"  Could not retrieve tracking entry for {completed_symbol}"
                            )
                    except Exception as e:
                        logger.warning(f"  Error retrieving entry for {completed_symbol}: {e}")
            except Exception as e:
                logger.warning(f"Error logging completed entries details: {e}")

        # Log all tracking entries for debugging (to detect data corruption)
        # Wrap in try-catch to handle corrupted data gracefully
        try:
            logger.info("All tracking entries (for debugging):")
            data = self.tracking_scope._load_tracking_data()
            for idx, entry in enumerate(data.get("symbols", [])):
                try:
                    logger.info(
                        f"  Entry #{idx + 1}: symbol={entry.get('symbol')}, "
                        f"status={entry.get('tracking_status')}, "
                        f"qty={entry.get('current_tracked_qty')}, "
                        f"ticker={entry.get('ticker')}, "
                        f"order_id={entry.get('initial_order_id')}"
                    )
                except Exception as e:
                    logger.warning(f"  Error logging entry #{idx + 1}: {e}")
        except Exception as e:
            logger.warning(f"Error loading tracking data for debugging: {e}")

        # Identify holdings that are not tracked
        untracked_holdings = []
        previously_tracked_holdings = []
        for holding_symbol in holdings_symbols:
            # Check if it's in active, completed, or all tracked symbols
            is_tracked_completed = holding_symbol in [s.upper() for s in completed_tracked_symbols]
            is_tracked_any = holding_symbol in [s.upper() for s in all_tracked_symbols]

            holding_info = holdings_dict.get(holding_symbol, {})
            qty = int(
                holding_info.get("qty", 0)
                or holding_info.get("quantity", 0)
                or holding_info.get("netQuantity", 0)
                or 0
            )

            if is_tracked_completed:
                # Previously tracked but now completed - get details
                # Wrap in try-catch to handle corrupted data gracefully
                try:
                    entry = self.tracking_scope.get_tracking_entry(
                        holding_symbol, status="completed"
                    )
                    if entry:
                        completed_at = entry.get("tracking_ended_at", "unknown")
                        final_qty = entry.get("current_tracked_qty", 0)
                        previously_tracked_holdings.append(
                            f"{holding_symbol} (qty: {qty}, completed at: {completed_at}, "
                            f"final tracked qty: {final_qty})"
                        )
                except Exception as e:
                    logger.debug(f"Error retrieving tracking entry for {holding_symbol}: {e}")
                    # Still add to previously_tracked_holdings even if we can't get details
                    previously_tracked_holdings.append(
                        f"{holding_symbol} (qty: {qty}, details unavailable)"
                    )
            elif not is_tracked_any:
                untracked_holdings.append(f"{holding_symbol} (qty: {qty})")

        if previously_tracked_holdings:
            logger.info(
                f"Found {len(previously_tracked_holdings)} holdings that were previously tracked "
                f"but are now completed: {', '.join(previously_tracked_holdings)}. "
                f"These positions may have been sold or tracking was archived."
            )

        # Detect potential data corruption: if all completed entries have the same symbol
        # Note: This is logged as WARNING, not ERROR, so EOD cleanup continues normally
        if completed_tracked_symbols and len(set(completed_tracked_symbols)) == 1:
            duplicate_symbol = completed_tracked_symbols[0]
            if duplicate_symbol.upper() not in holdings_symbols:
                logger.warning(
                    f"DATA CORRUPTION DETECTED (non-fatal): "
                    f"All {len(completed_tracked_symbols)} completed tracking entries "
                    f"have the same symbol '{duplicate_symbol}', "
                    f"but this symbol is NOT in current holdings. "
                    f"This suggests tracking data corruption. "
                    f"Holdings: {', '.join(holdings_symbols)}. "
                    f"EOD cleanup will continue normally. "
                    f"Consider fixing tracking file when convenient."
                )

        if untracked_holdings:
            logger.warning(
                f"Found {len(untracked_holdings)} holdings that are NOT tracked by the system: "
                f"{', '.join(untracked_holdings)}. "
                f"These may be manual buys or positions that lost tracking. "
                f"Manual trade detection will not work for these symbols."
            )
        elif not previously_tracked_holdings:
            logger.info("All holdings are tracked (active or completed)")

        # Identify tracked symbols that are not in holdings
        tracked_not_in_holdings = []
        for tracked_symbol in tracked_symbols:
            if tracked_symbol.upper() not in holdings_symbols:
                # Wrap in try-catch to handle corrupted data gracefully
                try:
                    tracking_entry = self.tracking_scope.get_tracking_entry(
                        tracked_symbol, status="active"
                    )
                    tracked_qty = (
                        tracking_entry.get("current_tracked_qty", 0) if tracking_entry else 0
                    )
                    tracked_not_in_holdings.append(f"{tracked_symbol} (tracked qty: {tracked_qty})")
                except Exception as e:
                    logger.debug(f"Error retrieving tracking entry for {tracked_symbol}: {e}")
                    tracked_not_in_holdings.append(f"{tracked_symbol} (tracked qty: unknown)")

        if tracked_not_in_holdings:
            logger.warning(
                f"Found {len(tracked_not_in_holdings)} tracked symbols NOT in holdings: "
                f"{', '.join(tracked_not_in_holdings)}. "
                f"These may have been sold manually or tracking is stale."
            )

        if not tracked_symbols:
            logger.warning(
                f"No active tracked symbols to reconcile. "
                f"This means manual trade detection cannot work for "
                f"{len(holdings_symbols)} holdings. "
                f"Consider initializing tracking for existing holdings "
                f"or investigate why tracking was lost."
            )
            return {
                "matched": 0,
                "manual_buys_detected": 0,
                "manual_sells_detected": 0,
                "discrepancies": [],
                "updated_symbols": [],
            }

        logger.info(f"Reconciling {len(tracked_symbols)} tracked symbol(s)")

        # Log symbol normalization for debugging
        if tracked_symbols:
            from .utils.symbol_utils import extract_base_symbol  # noqa: PLC0415

            normalized_examples = []
            for sym in tracked_symbols[:5]:  # Show first 5 examples
                normalized = extract_base_symbol(sym).upper()
                if normalized != sym.upper():
                    normalized_examples.append(f"{sym} -> {normalized}")
            if normalized_examples:
                logger.debug(f"Symbol normalization examples: {', '.join(normalized_examples)}")

        results = {
            "matched": 0,
            "manual_buys_detected": 0,
            "manual_sells_detected": 0,
            "discrepancies": [],
            "updated_symbols": [],
        }

        # Check each tracked symbol
        # Wrap entire loop in try-catch to handle corrupted data gracefully
        for symbol in tracked_symbols:
            try:
                # IMPORTANT: request active entry explicitly; `status="any"` can
                # return stale completed rows for symbols that were re-tracked.
                tracking_entry = self.tracking_scope.get_tracking_entry(
                    symbol, status="active"
                )

                if not tracking_entry:
                    logger.warning(f"Tracking entry not found for {symbol}")
                    continue

                system_qty = tracking_entry.get("current_tracked_qty", 0)
                pre_existing_qty = tracking_entry.get("pre_existing_qty", 0)

                # Normalize tracked symbol for lookup (same as holdings normalization)
                # This handles cases where tracked symbol is "MIRZAINT-EQ"
                # but holdings has "MIRZAINT"
                from .utils.symbol_utils import extract_base_symbol  # noqa: PLC0415

                normalized_symbol = extract_base_symbol(symbol).upper()
                original_symbol_upper = symbol.upper()

                # Try normalized symbol first (matches how holdings are stored)
                broker_holding = holdings_dict.get(normalized_symbol)

                # Fallback: try original symbol if normalized lookup fails
                if not broker_holding and normalized_symbol != original_symbol_upper:
                    broker_holding = holdings_dict.get(original_symbol_upper)
                    if broker_holding:
                        logger.debug(
                            f"Found holding using original symbol format: {original_symbol_upper} "
                            f"(normalized: {normalized_symbol})"
                        )

                broker_qty = 0
                if broker_holding:
                    broker_qty = int(
                        broker_holding.get("qty", 0) or broker_holding.get("quantity", 0) or 0
                    )

                # Validate pre_existing_qty before using it
                pre_existing_qty = self.validate_and_clean_pre_existing_qty(
                    symbol, broker_qty, system_qty, pre_existing_qty
                )

                # Expected quantity = system qty + pre-existing qty
                expected_total_qty = system_qty + pre_existing_qty

                # Check for discrepancy
                if broker_qty == expected_total_qty:
                    # Perfect match - no manual trades
                    logger.debug(
                        f"[OK] {symbol}: Broker qty ({broker_qty}) "
                        f"matches expected ({expected_total_qty})"
                    )
                    results["matched"] += 1
                    continue

                # Discrepancy detected - manual trade likely
                qty_diff = broker_qty - expected_total_qty

                logger.info(
                    f"[WARN] {symbol}: Quantity mismatch detected\n"
                    f"  Expected: {expected_total_qty} "
                    f"(system: {system_qty}, pre-existing: {pre_existing_qty})\n"
                    f"  Broker:   {broker_qty}\n"
                    f"  Diff:     {qty_diff:+d}\n"
                    f"  Symbol normalization: {original_symbol_upper} -> {normalized_symbol}"
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
                    logger.info(
                        f"Found {len(manual_orders)} potential manual order(s) for {symbol}"
                    )
                    discrepancy["manual_orders"] = manual_orders

                    # Add to related orders
                    for order in manual_orders:
                        order_id = order.get("order_id")
                        if order_id:
                            self.tracking_scope.add_related_order(symbol, order_id)

                # Update tracking quantity to match reality
                try:
                    self.tracking_scope.update_tracked_qty(symbol, qty_diff)
                    results["updated_symbols"].append(symbol)
                    logger.info(
                        f"[OK] Updated tracking for {symbol}: "
                        f"{system_qty} -> {system_qty + qty_diff}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to update tracking for {symbol}: {e}")

            except Exception as e:
                logger.warning(f"Error reconciling symbol {symbol}: {e}. Skipping this symbol.")
                continue

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
        self, symbol: str, qty: int, tracking_entry: dict[str, Any]
    ) -> list[dict[str, Any]]:
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
        # known_order_ids = set(tracking_entry.get("all_related_orders", []))

        # Try to get recent orders from broker (implementation would need broker client)
        # For now, return empty list as this requires broker API integration
        # This is a placeholder for Phase 3 enhancement

        logger.debug(
            f"Manual order search for {symbol} (qty: {qty}) - "
            f"skipping (requires broker API integration)"
        )

        return []

    def detect_position_closures(self, broker_holdings: list[dict[str, Any]]) -> list[str]:
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
            try:
                tracking_entry = self.tracking_scope.get_tracking_entry(
                    symbol, status="active"
                )

                if not tracking_entry:
                    continue

                # Check if symbol is no longer in holdings
                if symbol.upper() not in holdings_dict:
                    # Position was closed
                    tracked_qty = tracking_entry.get("current_tracked_qty", 0)
                    logger.info(
                        f"? Position closed detected: {symbol} (was tracking {tracked_qty} shares)"
                    )

                    # Stop tracking - wrap in try-catch to handle errors gracefully
                    try:
                        self.tracking_scope.stop_tracking(
                            symbol, reason="Position fully closed (manual sell detected)"
                        )
                        closed_positions.append(symbol)
                    except Exception as e:
                        logger.warning(f"Failed to stop tracking for {symbol}: {e}")

            except Exception as e:
                logger.warning(f"Error checking position closure for {symbol}: {e}. Skipping.")
                continue

        return closed_positions

    def reconcile_partial_positions(self, broker_holdings: list[dict[str, Any]]) -> dict[str, Any]:
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
            tracking_entry = self.tracking_scope.get_tracking_entry(
                symbol, status="active"
            )

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

    def get_reconciliation_summary(self, reconciliation_results: dict[str, Any]) -> str:
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
_matcher_instance: ManualOrderMatcher | None = None


def get_manual_order_matcher(
    tracking_scope: TrackingScope | None = None, order_tracker: OrderTracker | None = None
) -> ManualOrderMatcher:
    """
    Get or create manual order matcher singleton.

    Args:
        tracking_scope: TrackingScope instance
        order_tracker: OrderTracker instance

    Returns:
        ManualOrderMatcher instance
    """
    global _matcher_instance  # noqa: PLW0603

    if _matcher_instance is None:
        _matcher_instance = ManualOrderMatcher(tracking_scope, order_tracker)

    return _matcher_instance
