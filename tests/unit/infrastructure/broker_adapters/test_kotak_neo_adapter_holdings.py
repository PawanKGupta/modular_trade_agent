"""
Tests for KotakNeoBrokerAdapter holdings retrieval and parsing

Tests cover:
1. Kotak Neo API response format with displaySymbol, averagePrice, closingPrice, etc.
2. Holdings parsing with various field formats
3. Field name variations and fallbacks
4. Error handling in holdings conversion
"""

from unittest.mock import MagicMock

import pytest

from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (
    KotakNeoBrokerAdapter,
)


@pytest.fixture
def mock_client():
    """Create a mock Kotak Neo client"""
    return MagicMock()


@pytest.fixture
def adapter(mock_client):
    """Create a KotakNeoBrokerAdapter instance"""
    adapter = KotakNeoBrokerAdapter(auth_handler=MagicMock())
    adapter._client = mock_client
    adapter._connected = True
    return adapter


class TestGetHoldingsResponseFormats:
    """Test get_holdings() handles different response formats"""

    def test_response_with_data_key(self, adapter, mock_client):
        """Test response format: {"data": [...]}"""
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "symbol": "IDEA",
                    "averagePrice": 9.5699,
                    "quantity": 35,
                    "closingPrice": 9.36,
                    "mktValue": 327.6,
                    "holdingCost": 334.9475,
                }
            ]
        }

        holdings = adapter.get_holdings()

        assert len(holdings) == 1
        assert holdings[0].symbol == "IDEA"
        assert holdings[0].quantity == 35
        mock_client.holdings.assert_called_once()

    def test_response_direct_list(self, adapter, mock_client):
        """Test response format: [...] (direct list)"""
        mock_client.holdings.return_value = [
            {
                "displaySymbol": "TCS",
                "averagePrice": 3500.0,
                "quantity": 10,
                "closingPrice": 3600.0,
            }
        ]

        holdings = adapter.get_holdings()

        assert len(holdings) == 0  # Should return empty if not in {"data": [...]} format
        # The adapter expects {"data": [...]} format

    def test_response_empty_data(self, adapter, mock_client):
        """Test response with empty data array"""
        mock_client.holdings.return_value = {"data": []}

        holdings = adapter.get_holdings()

        assert len(holdings) == 0


class TestParseHoldingsResponse:
    """Test _parse_holdings_response() with Kotak Neo API format"""

    def test_parse_holding_with_kotak_format(self, adapter):
        """Test parsing holding with exact Kotak Neo API format"""
        data = [
            {
                "displaySymbol": "IDEA",
                "symbol": "IDEA",
                "averagePrice": 9.5699,
                "quantity": 35,
                "exchangeSegment": "nse_cm",
                "exchangeIdentifier": "14366",
                "holdingCost": 334.9475,
                "mktValue": 327.6,
                "scripId": "746a0ebbc6295a002ab27e42a3e06a6792baeba1",
                "instrumentToken": 8658,
                "instrumentType": "Equity",
                "isAlternateScrip": False,
                "closingPrice": 9.36,
                "sellableQuantity": 35,
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        holding = holdings[0]
        assert holding.symbol == "IDEA"
        assert holding.quantity == 35
        # Money.from_float() rounds to 2 decimal places, so 9.5699 becomes 9.57
        assert float(holding.average_price.amount) == pytest.approx(9.57, abs=0.001)
        assert float(holding.current_price.amount) == 9.36  # Uses closingPrice

    def test_parse_holding_with_fallback_symbol(self, adapter):
        """Test parsing holding when displaySymbol is missing, uses symbol"""
        data = [
            {
                "symbol": "RELIANCE",
                "averagePrice": 2450.50,
                "quantity": 10,
                "closingPrice": 2500.0,
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].symbol == "RELIANCE"

    def test_parse_holding_with_fallback_current_price(self, adapter):
        """Test parsing holding when closingPrice is missing, uses ltp"""
        data = [
            {
                "displaySymbol": "TCS",
                "averagePrice": 3500.0,
                "quantity": 5,
                "ltp": 3600.0,  # Fallback to ltp
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].current_price.amount == 3600.0

    def test_parse_holding_calculates_price_from_mkt_value(self, adapter):
        """Test parsing holding calculates current_price from mktValue when closingPrice is 0"""
        data = [
            {
                "displaySymbol": "INFY",
                "averagePrice": 1500.0,
                "quantity": 20,
                "closingPrice": 0,  # Missing/zero
                "mktValue": 30000.0,  # Should calculate: 30000 / 20 = 1500
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].current_price.amount == 1500.0  # Calculated from mktValue

    def test_parse_holding_with_zero_quantity(self, adapter):
        """Test parsing holding with zero quantity"""
        data = [
            {
                "displaySymbol": "WIPRO",
                "averagePrice": 500.0,
                "quantity": 0,
                "closingPrice": 510.0,
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].quantity == 0

    def test_parse_holding_skips_empty_symbol(self, adapter):
        """Test parsing skips holdings with empty symbol"""
        data = [
            {
                "displaySymbol": "",
                "symbol": "",
                "averagePrice": 100.0,
                "quantity": 5,
                "closingPrice": 105.0,
            },
            {
                "displaySymbol": "VALID",
                "averagePrice": 200.0,
                "quantity": 10,
                "closingPrice": 210.0,
            },
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].symbol == "VALID"

    def test_parse_multiple_holdings(self, adapter):
        """Test parsing multiple holdings"""
        data = [
            {
                "displaySymbol": "IDEA",
                "averagePrice": 9.5699,
                "quantity": 35,
                "closingPrice": 9.36,
            },
            {
                "displaySymbol": "TCS",
                "averagePrice": 3500.0,
                "quantity": 10,
                "closingPrice": 3600.0,
            },
            {
                "displaySymbol": "RELIANCE",
                "averagePrice": 2450.50,
                "quantity": 5,
                "closingPrice": 2500.0,
            },
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 3
        assert holdings[0].symbol == "IDEA"
        assert holdings[1].symbol == "TCS"
        assert holdings[2].symbol == "RELIANCE"

    def test_parse_holding_with_legacy_field_names(self, adapter):
        """Test parsing holding with legacy field names (backward compatibility)"""
        data = [
            {
                "tradingSymbol": "INFY-EQ",  # Legacy field
                "avgPrice": 1500.0,  # Legacy field
                "qty": 20,  # Legacy field
                "ltp": 1550.0,  # Legacy field
            }
        ]

        holdings = adapter._parse_holdings_response(data)

        assert len(holdings) == 1
        assert holdings[0].symbol == "INFY-EQ"
        assert holdings[0].quantity == 20
        assert holdings[0].average_price.amount == 1500.0
        assert holdings[0].current_price.amount == 1550.0

    def test_parse_holding_error_handling(self, adapter):
        """Test parsing handles errors gracefully"""
        data = [
            {
                "displaySymbol": "VALID",
                "averagePrice": 100.0,
                "quantity": 5,
                "closingPrice": 105.0,
            },
            {
                # Invalid data - missing required fields
                "someInvalidField": "value",
            },
            {
                "displaySymbol": "ANOTHER",
                "averagePrice": 200.0,
                "quantity": 10,
                "closingPrice": 210.0,
            },
        ]

        holdings = adapter._parse_holdings_response(data)

        # Should parse valid holdings and skip invalid ones
        assert len(holdings) == 2
        assert holdings[0].symbol == "VALID"
        assert holdings[1].symbol == "ANOTHER"


class TestGetHolding:
    """Test get_holding() for specific symbol"""

    def test_get_holding_found(self, adapter, mock_client):
        """Test getting holding for existing symbol"""
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.5699,
                    "quantity": 35,
                    "closingPrice": 9.36,
                },
                {
                    "displaySymbol": "TCS",
                    "averagePrice": 3500.0,
                    "quantity": 10,
                    "closingPrice": 3600.0,
                },
            ]
        }

        holding = adapter.get_holding("IDEA")

        assert holding is not None
        assert holding.symbol == "IDEA"
        assert holding.quantity == 35

    def test_get_holding_not_found(self, adapter, mock_client):
        """Test getting holding for non-existent symbol"""
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.5699,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }

        holding = adapter.get_holding("NONEXISTENT")

        assert holding is None

    def test_get_holding_case_insensitive(self, adapter, mock_client):
        """Test getting holding is case-insensitive"""
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.5699,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }

        holding = adapter.get_holding("idea")

        assert holding is not None
        assert holding.symbol == "IDEA"
