"""
Tests for OrderFieldExtractor changes (Edge Case #8)

Tests verify that:
1. get_quantity() returns order quantity (qty), not filled quantity
2. get_filled_quantity() returns filled quantity (fldQty)
3. Both methods handle various field name variations
"""

from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor


class TestGetQuantity:
    """Test get_quantity() method - should return order quantity"""

    def test_get_quantity_from_qty_field(self):
        """Test extracting quantity from 'qty' field"""
        order = {"qty": 35}
        assert OrderFieldExtractor.get_quantity(order) == 35

    def test_get_quantity_from_quantity_field(self):
        """Test extracting quantity from 'quantity' field"""
        order = {"quantity": 35}
        assert OrderFieldExtractor.get_quantity(order) == 35

    def test_get_quantity_from_orderQty_field(self):
        """Test extracting quantity from 'orderQty' field"""
        order = {"orderQty": 35}
        assert OrderFieldExtractor.get_quantity(order) == 35

    def test_get_quantity_prefers_qty_over_quantity(self):
        """Test that 'qty' is preferred over 'quantity'"""
        order = {"qty": 35, "quantity": 40}
        assert OrderFieldExtractor.get_quantity(order) == 35

    def test_get_quantity_returns_zero_if_not_found(self):
        """Test that get_quantity() returns 0 if no quantity field found"""
        order = {}
        assert OrderFieldExtractor.get_quantity(order) == 0

    def test_get_quantity_ignores_fldQty(self):
        """Test that get_quantity() does NOT return fldQty (filled quantity)"""
        order = {"qty": 35, "fldQty": 20}  # Order qty: 35, Filled: 20
        assert OrderFieldExtractor.get_quantity(order) == 35  # Should return order qty, not filled


class TestGetFilledQuantity:
    """Test get_filled_quantity() method - should return filled quantity"""

    def test_get_filled_quantity_from_fldQty_field(self):
        """Test extracting filled quantity from 'fldQty' field"""
        order = {"fldQty": 20}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_from_filledQty_field(self):
        """Test extracting filled quantity from 'filledQty' field"""
        order = {"filledQty": 20}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_from_filled_quantity_field(self):
        """Test extracting filled quantity from 'filled_quantity' field"""
        order = {"filled_quantity": 20}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_from_executedQty_field(self):
        """Test extracting filled quantity from 'executedQty' field"""
        order = {"executedQty": 20}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_from_executed_qty_field(self):
        """Test extracting filled quantity from 'executed_qty' field"""
        order = {"executed_qty": 20}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_prefers_fldQty(self):
        """Test that 'fldQty' is preferred over other fields"""
        order = {"fldQty": 20, "filledQty": 15, "executedQty": 10}
        assert OrderFieldExtractor.get_filled_quantity(order) == 20

    def test_get_filled_quantity_returns_zero_if_not_found(self):
        """Test that get_filled_quantity() returns 0 if no filled quantity field found"""
        order = {}
        assert OrderFieldExtractor.get_filled_quantity(order) == 0

    def test_get_filled_quantity_ignores_qty(self):
        """Test that get_filled_quantity() does NOT return qty (order quantity)"""
        order = {"qty": 35, "fldQty": 20}  # Order qty: 35, Filled: 20
        assert OrderFieldExtractor.get_filled_quantity(order) == 20  # Should return filled qty


class TestQuantityVsFilledQuantity:
    """Test that get_quantity() and get_filled_quantity() return different values"""

    def test_partial_execution_different_values(self):
        """Test that partial execution shows different order qty vs filled qty"""
        order = {
            "qty": 35,  # Order quantity
            "fldQty": 20,  # Filled quantity (partial)
        }

        order_qty = OrderFieldExtractor.get_quantity(order)
        filled_qty = OrderFieldExtractor.get_filled_quantity(order)

        assert order_qty == 35
        assert filled_qty == 20
        assert order_qty != filled_qty  # Should be different for partial execution

    def test_full_execution_same_values(self):
        """Test that full execution can have same order qty and filled qty"""
        order = {
            "qty": 35,  # Order quantity
            "fldQty": 35,  # Filled quantity (full)
        }

        order_qty = OrderFieldExtractor.get_quantity(order)
        filled_qty = OrderFieldExtractor.get_filled_quantity(order)

        assert order_qty == 35
        assert filled_qty == 35
        assert order_qty == filled_qty  # Should be same for full execution

    def test_real_broker_response_format(self):
        """Test with real broker API response format"""
        # Sample from Kotak Neo API order_report()
        order = {
            "qty": 35,  # Order quantity
            "fldQty": 20,  # Filled quantity
            "avgPrc": "9.50",  # Average price
            "stat": "open",  # Status (partial fill)
        }

        order_qty = OrderFieldExtractor.get_quantity(order)
        filled_qty = OrderFieldExtractor.get_filled_quantity(order)

        assert order_qty == 35
        assert filled_qty == 20

    def test_missing_filled_quantity_returns_zero(self):
        """Test that missing filled quantity returns 0, but order quantity still works"""
        order = {
            "qty": 35,  # Order quantity exists
            # fldQty missing (order not executed yet)
        }

        order_qty = OrderFieldExtractor.get_quantity(order)
        filled_qty = OrderFieldExtractor.get_filled_quantity(order)

        assert order_qty == 35
        assert filled_qty == 0  # No filled quantity yet
