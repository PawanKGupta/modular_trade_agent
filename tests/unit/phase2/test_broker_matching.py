"""Unit tests for FIFO matching algorithm used in broker history endpoint."""

from datetime import datetime, timedelta

import pytest

from server.app.routers.broker_history_impl import _fifo_match_orders


class TestFIFOMatchingBasic:
    """Basic FIFO matching tests."""

    def test_empty_transactions(self):
        """Empty transaction list should return empty closed positions."""
        result = _fifo_match_orders([])
        assert result == []

    def test_only_buy_orders(self):
        """Only buy orders should not generate closed positions."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 50,
                "execution_price": 151.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result == []

    def test_only_sell_orders(self):
        """Sell orders without buy orders should not generate closed positions."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-01T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result == []

    def test_simple_buy_sell_match(self):
        """Simple buy followed by sell should create one closed position."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        cp = result[0]
        assert cp["symbol"] == "AAPL"
        assert cp["quantity"] == 100.0
        assert cp["avg_price"] == 150.0
        assert cp["exit_price"] == 160.0
        assert cp["realized_pnl"] == 1000.0  # (160 - 150) * 100
        assert cp["realized_pnl_pct"] == pytest.approx(6.666666, abs=0.001)


class TestFIFOMatchingPartialFills:
    """Test FIFO matching with partial fills."""

    def test_sell_less_than_buy(self):
        """Sell less than buy quantity should create one partial closed position."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 50,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        cp = result[0]
        assert cp["quantity"] == 50.0
        assert cp["realized_pnl"] == 500.0  # (160 - 150) * 50

    def test_sell_more_than_single_buy_multiple_lots(self):
        """Sell more than single buy lot should match multiple buys (FIFO)."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 50,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 50,
                "execution_price": 151.0,
                "placed_at": "2025-01-01T11:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 2
        # First closed position: first 50 bought at 150
        assert result[0]["quantity"] == 50.0
        assert result[0]["avg_price"] == 150.0
        assert result[0]["realized_pnl"] == 500.0
        # Second closed position: next 50 bought at 151
        assert result[1]["quantity"] == 50.0
        assert result[1]["avg_price"] == 151.0
        assert result[1]["realized_pnl"] == 450.0

    def test_multiple_buys_multiple_sells(self):
        """Multiple buys and sells should match in FIFO order."""
        transactions = [
            {
                "symbol": "MSFT",
                "side": "buy",
                "quantity": 100,
                "execution_price": 300.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "MSFT",
                "side": "buy",
                "quantity": 50,
                "execution_price": 301.0,
                "placed_at": "2025-01-01T11:00:00",
            },
            {
                "symbol": "MSFT",
                "side": "sell",
                "quantity": 75,
                "execution_price": 310.0,
                "placed_at": "2025-01-02T10:00:00",
            },
            {
                "symbol": "MSFT",
                "side": "sell",
                "quantity": 75,
                "execution_price": 311.0,
                "placed_at": "2025-01-02T11:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 3
        # First sell: matches first 75 of first buy (100 @ 300)
        assert result[0]["quantity"] == 75.0
        assert result[0]["avg_price"] == 300.0
        assert result[0]["realized_pnl"] == 750.0  # (310 - 300) * 75
        # Second sell: matches remaining 25 of first buy + 50 of second buy
        assert result[1]["quantity"] == 25.0
        assert result[1]["avg_price"] == 300.0
        assert result[1]["realized_pnl"] == 275.0  # (311 - 300) * 25
        assert result[2]["quantity"] == 50.0
        assert result[2]["avg_price"] == 301.0
        assert result[2]["realized_pnl"] == 500.0  # (311 - 301) * 50


class TestFIFOMatchingMultipleSymbols:
    """Test FIFO matching with multiple symbols."""

    def test_multiple_symbols_separate_tracking(self):
        """Different symbols should be tracked separately."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "MSFT",
                "side": "buy",
                "quantity": 50,
                "execution_price": 300.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
            {
                "symbol": "MSFT",
                "side": "sell",
                "quantity": 50,
                "execution_price": 310.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 2
        # Should have one AAPL and one MSFT closed position
        symbols = [cp["symbol"] for cp in result]
        assert "AAPL" in symbols
        assert "MSFT" in symbols


class TestFIFOMatchingEdgeCases:
    """Test FIFO matching with edge cases."""

    def test_zero_quantity_ignored(self):
        """Transactions with zero or negative quantities should be ignored."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 0,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        assert result[0]["quantity"] == 100.0

    def test_none_price_handled(self):
        """Transactions with None prices should be handled gracefully."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": None,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        cp = result[0]
        assert cp["avg_price"] is None
        assert cp["realized_pnl"] is None
        assert cp["realized_pnl_pct"] is None

    def test_case_insensitive_side(self):
        """Side field should be case-insensitive (BUY, Buy, buy all work)."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 50,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "Buy",
                "quantity": 50,
                "execution_price": 151.0,
                "placed_at": "2025-01-01T11:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "SELL",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 2

    def test_timestamp_parsing_iso_format(self):
        """Timestamps in ISO format should be parsed correctly."""
        now = datetime.now()
        later = now + timedelta(days=1)
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": now.isoformat(),
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": later.isoformat(),
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        cp = result[0]
        assert cp["opened_at"] is not None
        assert cp["closed_at"] is not None

    def test_timestamp_parsing_datetime_object(self):
        """Timestamp as datetime object should be handled."""
        now = datetime.now()
        later = now + timedelta(days=1)
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": now,
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": later,
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1

    def test_invalid_timestamp_ignored(self):
        """Invalid timestamp should be ignored gracefully."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "invalid-date",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "also-invalid",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        cp = result[0]
        # Timestamps should be None due to parse failure
        assert cp["opened_at"] is None
        assert cp["closed_at"] is None

    def test_missing_fields_handled(self):
        """Missing optional fields should be handled gracefully."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                # execution_price is missing
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
            },
        ]
        result = _fifo_match_orders(transactions)
        assert len(result) == 1
        assert result[0]["avg_price"] is None


class TestFIFOMatchingProfitability:
    """Test P&L calculations in FIFO matching."""

    def test_profitable_trade_positive_pnl(self):
        """Profitable trade should have positive P&L."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result[0]["realized_pnl"] > 0
        assert result[0]["realized_pnl_pct"] > 0

    def test_losing_trade_negative_pnl(self):
        """Losing trade should have negative P&L."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result[0]["realized_pnl"] < 0
        assert result[0]["realized_pnl_pct"] < 0

    def test_breakeven_trade_zero_pnl(self):
        """Breakeven trade should have zero P&L."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result[0]["realized_pnl"] == 0.0
        assert result[0]["realized_pnl_pct"] == 0.0

    def test_pnl_calculation_precision(self):
        """P&L calculation should be accurate with decimal quantities."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 10.5,
                "execution_price": 150.25,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 10.5,
                "execution_price": 160.75,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        expected_pnl = (160.75 - 150.25) * 10.5  # 110.25
        assert result[0]["realized_pnl"] == pytest.approx(expected_pnl, abs=0.01)
        expected_pct = (160.75 - 150.25) / 150.25 * 100  # ~6.98%
        assert result[0]["realized_pnl_pct"] == pytest.approx(expected_pct, abs=0.01)

    def test_zero_entry_price_pnl_percentage(self):
        """If entry price is 0, P&L percentage should be None."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 0.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 160.0,
                "placed_at": "2025-01-02T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        assert result[0]["realized_pnl_pct"] is None


class TestFIFOMatchingOrdering:
    """Test that FIFO matching respects chronological ordering."""

    def test_transactions_matched_in_order(self):
        """Transactions should be matched in chronological order."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 100.0,
                "placed_at": "2025-01-01T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100,
                "execution_price": 200.0,
                "placed_at": "2025-01-02T10:00:00",
            },
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 100,
                "execution_price": 150.0,
                "placed_at": "2025-01-03T10:00:00",
            },
        ]
        result = _fifo_match_orders(transactions)
        # Should match with first buy (100 @ 100), not second (100 @ 200)
        assert result[0]["avg_price"] == 100.0
        assert result[0]["exit_price"] == 150.0
        assert result[0]["realized_pnl"] == 5000.0  # (150 - 100) * 100


class TestFIFOMatchingLargeDatasets:
    """Test FIFO matching with larger datasets."""

    def test_many_buy_orders(self):
        """Should handle many buy orders correctly."""
        transactions = []
        # 100 buy orders
        for i in range(100):
            transactions.append(
                {
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 1,
                    "execution_price": 100.0 + i,
                    "placed_at": f"2025-01-01T{i:02d}:00:00",
                }
            )
        # 100 sell orders (matching FIFO)
        for i in range(100):
            transactions.append(
                {
                    "symbol": "AAPL",
                    "side": "sell",
                    "quantity": 1,
                    "execution_price": 150.0 + i,
                    "placed_at": f"2025-01-02T{i:02d}:00:00",
                }
            )
        result = _fifo_match_orders(transactions)
        assert len(result) == 100
        # First closed position should be from first buy (100.0) to first sell (150.0)
        assert result[0]["avg_price"] == 100.0
        assert result[0]["exit_price"] == 150.0
        # Last closed position should be from last buy (199.0) to last sell (249.0)
        assert result[99]["avg_price"] == 199.0
        assert result[99]["exit_price"] == 249.0

    def test_many_partial_fills(self):
        """Should handle many partial fill transactions."""
        transactions = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 1000,
                "execution_price": 100.0,
                "placed_at": "2025-01-01T10:00:00",
            },
        ]
        # Sell in 10 pieces
        for i in range(10):
            transactions.append(
                {
                    "symbol": "AAPL",
                    "side": "sell",
                    "quantity": 100,
                    "execution_price": 110.0 + i,
                    "placed_at": f"2025-01-02T{i:02d}:00:00",
                }
            )
        result = _fifo_match_orders(transactions)
        assert len(result) == 10
        # All should have same entry price (100.0) but different exit prices
        for i, cp in enumerate(result):
            assert cp["avg_price"] == 100.0
            assert cp["quantity"] == 100.0
            assert cp["exit_price"] == 110.0 + i
