"""
Unit tests for PriceService Phase 4.1 enhancements

Tests verify subscription deduplication and lifecycle management.

Phase 4.1: Centralize Live Price Subscription
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.services.price_service import (
    PriceService,
    get_price_service,
)


class TestPriceServiceSubscriptionDeduplication:
    """Test subscription deduplication in PriceService"""

    def test_subscribe_to_symbols_deduplicates(self):
        """Test that subscribing to same symbol twice doesn't create duplicate subscriptions"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Subscribe to same symbols twice from different services
        symbols = ["RELIANCE", "TATA", "INFY"]
        service.subscribe_to_symbols(symbols, service_id="service1")
        service.subscribe_to_symbols(symbols, service_id="service2")

        # Verify subscribe_to_positions was called only once (for the first subscription)
        assert broker_client.subscribe_to_positions.call_count == 1
        broker_client.subscribe_to_positions.assert_called_once_with(symbols)

        # Verify both services are tracked
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" in subscriptions
        assert "TATA" in subscriptions
        assert "INFY" in subscriptions
        assert "service1" in subscriptions["RELIANCE"]
        assert "service2" in subscriptions["RELIANCE"]

    def test_subscribe_to_symbols_tracks_multiple_services(self):
        """Test that multiple services subscribing to same symbol are tracked"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Service 1 subscribes
        service.subscribe_to_symbols(["RELIANCE"], service_id="position_monitor")
        # Service 2 subscribes to same symbol
        service.subscribe_to_symbols(["RELIANCE"], service_id="sell_monitor")

        # Verify only one subscription call (deduplication)
        assert broker_client.subscribe_to_positions.call_count == 1

        # Verify both services tracked
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" in subscriptions
        assert subscriptions["RELIANCE"] == {"position_monitor", "sell_monitor"}

    def test_subscribe_to_symbols_normalizes_symbols(self):
        """Test that symbols are normalized before subscription"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Subscribe with mixed case and whitespace
        service.subscribe_to_symbols(
            ["reliance", " TATA ", "INFY"], service_id="service1"
        )

        # Verify normalized symbols are tracked
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" in subscriptions
        assert "TATA" in subscriptions
        assert "INFY" in subscriptions

    def test_subscribe_to_symbols_handles_empty_list(self):
        """Test that empty symbol list is handled gracefully"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        result = service.subscribe_to_symbols([], service_id="service1")

        assert result is True
        assert broker_client.subscribe_to_positions.call_count == 0


class TestPriceServiceSubscriptionLifecycle:
    """Test subscription lifecycle management in PriceService"""

    def test_unsubscribe_from_symbols_only_when_no_services(self):
        """Test that unsubscribe only happens when no services need the symbol"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()
        broker_client.unsubscribe_from_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Two services subscribe
        service.subscribe_to_symbols(["RELIANCE"], service_id="service1")
        service.subscribe_to_symbols(["RELIANCE"], service_id="service2")

        # Service 1 unsubscribes - should NOT unsubscribe (service2 still needs it)
        service.unsubscribe_from_symbols(["RELIANCE"], service_id="service1")

        # Verify unsubscribe was NOT called
        broker_client.unsubscribe_from_positions.assert_not_called()

        # Verify service1 is removed from tracking
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" in subscriptions
        assert subscriptions["RELIANCE"] == {"service2"}

        # Service 2 unsubscribes - NOW should unsubscribe
        service.unsubscribe_from_symbols(["RELIANCE"], service_id="service2")

        # Verify unsubscribe WAS called
        broker_client.unsubscribe_from_positions.assert_called_once_with(["RELIANCE"])

        # Verify symbol is removed from tracking
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" not in subscriptions

    def test_get_subscribed_symbols(self):
        """Test get_subscribed_symbols() returns all subscribed symbols"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Subscribe to symbols
        service.subscribe_to_symbols(["RELIANCE", "TATA"], service_id="service1")
        service.subscribe_to_symbols(["INFY"], service_id="service2")

        subscribed = service.get_subscribed_symbols()

        assert "RELIANCE" in subscribed
        assert "TATA" in subscribed
        assert "INFY" in subscribed
        assert len(subscribed) == 3

    def test_get_subscriptions_by_service(self):
        """Test get_subscriptions_by_service() returns symbols for specific service"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Service 1 subscribes to RELIANCE, TATA
        service.subscribe_to_symbols(["RELIANCE", "TATA"], service_id="service1")
        # Service 2 subscribes to TATA, INFY
        service.subscribe_to_symbols(["TATA", "INFY"], service_id="service2")

        # Get subscriptions for service1
        service1_symbols = service.get_subscriptions_by_service("service1")
        assert "RELIANCE" in service1_symbols
        assert "TATA" in service1_symbols
        assert "INFY" not in service1_symbols

        # Get subscriptions for service2
        service2_symbols = service.get_subscriptions_by_service("service2")
        assert "TATA" in service2_symbols
        assert "INFY" in service2_symbols
        assert "RELIANCE" not in service2_symbols

    def test_get_all_subscriptions(self):
        """Test get_all_subscriptions() returns complete subscription mapping"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Subscribe from multiple services
        service.subscribe_to_symbols(["RELIANCE"], service_id="service1")
        service.subscribe_to_symbols(["RELIANCE", "TATA"], service_id="service2")

        all_subs = service.get_all_subscriptions()

        assert "RELIANCE" in all_subs
        assert "TATA" in all_subs
        assert all_subs["RELIANCE"] == {"service1", "service2"}
        assert all_subs["TATA"] == {"service2"}


class TestPriceServiceBackwardCompatibility:
    """Test backward compatibility of subscription methods"""

    def test_subscribe_to_symbols_default_service_id(self):
        """Test that default service_id works for backward compatibility"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Call without service_id (should use default)
        result = service.subscribe_to_symbols(["RELIANCE"])

        assert result is True
        broker_client.subscribe_to_positions.assert_called_once()
        
        # Verify default service_id is tracked
        subscriptions = service.get_all_subscriptions()
        assert "RELIANCE" in subscriptions
        assert "default" in subscriptions["RELIANCE"]

    def test_unsubscribe_from_symbols_default_service_id(self):
        """Test that default service_id works for unsubscribe"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()
        broker_client.unsubscribe_from_positions = Mock()

        service = PriceService(live_price_manager=broker_client)

        # Subscribe with default service_id
        service.subscribe_to_symbols(["RELIANCE"])

        # Unsubscribe with default service_id
        result = service.unsubscribe_from_symbols(["RELIANCE"])

        assert result is True
        broker_client.unsubscribe_from_positions.assert_called_once_with(["RELIANCE"])


class TestPriceServiceLivePriceCacheInterface:
    """Test subscription with LivePriceCache interface (subscribe method)"""

    def test_subscribe_to_symbols_live_price_cache_interface(self):
        """Test subscription with LivePriceCache interface (subscribe method)"""
        broker_client = Mock()
        # LivePriceCache interface: has subscribe but not subscribe_to_positions
        broker_client.subscribe = Mock()
        del broker_client.subscribe_to_positions  # Ensure it doesn't have this method

        service = PriceService(live_price_manager=broker_client)

        symbols = ["RELIANCE", "TATA"]
        service.subscribe_to_symbols(symbols, service_id="service1")

        # Verify subscribe was called for each symbol
        assert broker_client.subscribe.call_count == 2
        broker_client.subscribe.assert_any_call("RELIANCE")
        broker_client.subscribe.assert_any_call("TATA")

    def test_unsubscribe_from_symbols_live_price_cache_interface(self):
        """Test unsubscription with LivePriceCache interface (unsubscribe method)"""
        broker_client = Mock()
        # LivePriceCache interface: has subscribe/unsubscribe but not subscribe_to_positions
        broker_client.subscribe = Mock()
        broker_client.unsubscribe = Mock()
        del broker_client.subscribe_to_positions  # Ensure it doesn't have this method
        del broker_client.unsubscribe_from_positions  # Ensure it doesn't have this method

        service = PriceService(live_price_manager=broker_client)

        # Subscribe
        service.subscribe_to_symbols(["RELIANCE"], service_id="service1")

        # Unsubscribe
        service.unsubscribe_from_symbols(["RELIANCE"], service_id="service1")

        # Verify unsubscribe was called
        broker_client.unsubscribe.assert_called_once_with("RELIANCE")


class TestPriceServiceNoLivePriceManager:
    """Test subscription behavior when no live_price_manager is available"""

    def test_subscribe_to_symbols_no_manager(self):
        """Test that subscription fails gracefully when no live_price_manager"""
        service = PriceService(live_price_manager=None)

        result = service.subscribe_to_symbols(["RELIANCE"], service_id="service1")

        assert result is False

    def test_unsubscribe_from_symbols_no_manager(self):
        """Test that unsubscription fails gracefully when no live_price_manager"""
        service = PriceService(live_price_manager=None)

        result = service.unsubscribe_from_symbols(["RELIANCE"], service_id="service1")

        assert result is False


class TestPriceServiceSingletonSubscriptionTracking:
    """Test that singleton PriceService maintains subscription state"""

    def test_singleton_maintains_subscriptions(self):
        """Test that singleton PriceService maintains subscriptions across calls"""
        broker_client = Mock()
        broker_client.subscribe_to_positions = Mock()

        # Get singleton instance
        service1 = get_price_service(live_price_manager=broker_client)
        service1.subscribe_to_symbols(["RELIANCE"], service_id="service1")

        # Get same instance
        service2 = get_price_service()

        # Verify subscriptions are shared
        assert service1 is service2
        subscriptions = service2.get_subscribed_symbols()
        assert "RELIANCE" in subscriptions

