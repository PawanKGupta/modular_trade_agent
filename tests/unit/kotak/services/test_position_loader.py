"""
Unit tests for PositionLoader

Tests verify the centralized position loading service
maintains backward compatibility with existing methods.
"""

import json
import os
import tempfile
import time
from unittest.mock import patch

from modules.kotak_neo_auto_trader.services.position_loader import (
    PositionCache,
    PositionLoader,
    get_position_loader,
)


class TestPositionCache:
    """Test PositionCache functionality"""

    def test_cache_get_set(self):
        """Test basic cache get/set operations"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            json.dump({"test": "data"}, f)

        try:
            cache = PositionCache()
            cache.set(temp_path, "test_data")
            result = cache.get(temp_path)
            assert result is not None
            data, is_valid = result
            assert data == "test_data"
            assert is_valid is True
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_cache_file_change_detection(self):
        """Test cache invalidation on file changes"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            json.dump({"test": "data1"}, f)

        try:
            cache = PositionCache()
            cache.set(temp_path, "data1")

            # Verify cache is set correctly (before file change)
            result_before = cache.get(temp_path)
            assert result_before is not None
            data_before, is_valid_before = result_before
            assert data_before == "data1"
            assert is_valid_before is True

            # Modify file and force mtime update
            with open(temp_path, "w") as f:
                json.dump({"test": "data2"}, f)
            # Force mtime update to ensure change is detected
            import time as time_module

            time_module.sleep(0.1)
            os.utime(temp_path, None)  # Update mtime to current time

            # Cache should be invalidated (file changed)
            result_after = cache.get(temp_path)
            assert result_after is None, f"Expected None after file change, got {result_after}"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_cache_clear(self):
        """Test cache clearing"""
        cache = PositionCache()
        cache.set("path1", "data1")
        cache.set("path2", "data2")
        cache.clear()
        assert cache.get("path1") is None
        assert cache.get("path2") is None

    def test_cache_invalidate(self):
        """Test cache invalidation for specific path"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f1:
            temp_path1 = f1.name
            json.dump({"test": "data1"}, f1)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f2:
            temp_path2 = f2.name
            json.dump({"test": "data2"}, f2)

        try:
            cache = PositionCache()
            cache.set(temp_path1, "data1")
            cache.set(temp_path2, "data2")
            cache.invalidate(temp_path1)
            assert cache.get(temp_path1) is None
            assert cache.get(temp_path2) is not None
        finally:
            if os.path.exists(temp_path1):
                os.unlink(temp_path1)
            if os.path.exists(temp_path2):
                os.unlink(temp_path2)


class TestPositionLoaderInitialization:
    """Test PositionLoader initialization"""

    def test_init_with_history_path(self):
        """Test initialization with history path"""
        loader = PositionLoader(history_path="test_history.json", enable_caching=True)
        assert loader.history_path == "test_history.json"
        assert loader.enable_caching is True
        assert loader._cache is not None

    def test_init_without_caching(self):
        """Test initialization without caching"""
        loader = PositionLoader(history_path="test_history.json", enable_caching=False)
        assert loader.enable_caching is False
        assert loader._cache is None

    def test_singleton_pattern(self):
        """Test that get_position_loader returns singleton"""
        loader1 = get_position_loader()
        loader2 = get_position_loader()
        assert loader1 is loader2

    def test_singleton_update_history_path(self):
        """Test that singleton updates history_path when provided"""
        loader = get_position_loader(history_path="test1.json")
        assert loader.history_path == "test1.json"

        loader = get_position_loader(history_path="test2.json")
        assert loader.history_path == "test2.json"


class TestPositionLoaderLoadOpenPositions:
    """Test load_open_positions() method"""

    def test_load_open_positions_from_file(self):
        """Test loading open positions from history file"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [
                    {"symbol": "RELIANCE", "status": "open", "qty": 10},
                    {"symbol": "TCS", "status": "closed", "qty": 5},
                    {"symbol": "INFY", "status": "open", "qty": 15},
                ],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            loader = PositionLoader(history_path=temp_path, enable_caching=False)
            positions = loader.load_open_positions()

            assert len(positions) == 2
            assert positions[0]["symbol"] == "RELIANCE"
            assert positions[1]["symbol"] == "INFY"
            assert all(p["status"] == "open" for p in positions)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_open_positions_no_open(self):
        """Test loading when no open positions exist"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [
                    {"symbol": "RELIANCE", "status": "closed", "qty": 10},
                    {"symbol": "TCS", "status": "closed", "qty": 5},
                ],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            loader = PositionLoader(history_path=temp_path, enable_caching=False)
            positions = loader.load_open_positions()
            assert len(positions) == 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_open_positions_no_history_path(self):
        """Test loading when no history path is provided"""
        loader = PositionLoader(history_path=None, enable_caching=False)
        positions = loader.load_open_positions()
        assert positions == []

    def test_load_open_positions_with_custom_path(self):
        """Test loading with custom history path"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            loader = PositionLoader(history_path=None, enable_caching=False)
            positions = loader.load_open_positions(history_path=temp_path)
            assert len(positions) == 1
            assert positions[0]["symbol"] == "RELIANCE"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_load_open_positions_handles_error(self):
        """Test loading handles file errors gracefully"""
        # Reset singleton to ensure test isolation
        import modules.kotak_neo_auto_trader.services.position_loader as position_loader_module
        position_loader_module._position_loader_instance = None

        loader = PositionLoader(history_path="/nonexistent/path.json", enable_caching=False)
        positions = loader.load_open_positions()
        # Should return empty list on error, not raise exception
        assert isinstance(positions, list)
        assert len(positions) == 0


class TestPositionLoaderGetPositionsBySymbol:
    """Test get_positions_by_symbol() method"""

    def test_get_positions_by_symbol(self):
        """Test loading positions grouped by symbol"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [
                    {"symbol": "RELIANCE", "status": "open", "qty": 10, "entry_price": 2500.0},
                    {"symbol": "RELIANCE", "status": "open", "qty": 5, "entry_price": 2400.0},
                    {"symbol": "TCS", "status": "open", "qty": 15, "entry_price": 3500.0},
                    {"symbol": "INFY", "status": "closed", "qty": 20, "entry_price": 1500.0},
                ],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            loader = PositionLoader(history_path=temp_path, enable_caching=False)
            positions = loader.get_positions_by_symbol()

            assert "RELIANCE" in positions
            assert "TCS" in positions
            assert "INFY" not in positions  # Closed position excluded

            assert len(positions["RELIANCE"]) == 2  # Two open positions
            assert len(positions["TCS"]) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_get_positions_by_symbol_no_open(self):
        """Test grouping when no open positions exist"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [
                    {"symbol": "RELIANCE", "status": "closed", "qty": 10},
                ],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            loader = PositionLoader(history_path=temp_path, enable_caching=False)
            positions = loader.get_positions_by_symbol()
            assert len(positions) == 0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_get_positions_by_symbol_no_history_path(self):
        """Test grouping when no history path is provided"""
        loader = PositionLoader(history_path=None, enable_caching=False)
        positions = loader.get_positions_by_symbol()
        assert positions == {}


class TestPositionLoaderCaching:
    """Test caching functionality"""

    def test_caching_enabled(self):
        """Test that caching works when enabled"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            with patch(
                "modules.kotak_neo_auto_trader.services.position_loader.load_history"
            ) as mock_load:
                mock_load.return_value = history

                loader = PositionLoader(history_path=temp_path, enable_caching=True)
                # First call
                positions1 = loader.load_open_positions()
                # Second call should use cache
                positions2 = loader.load_open_positions()

                # Should only be called once due to caching
                assert mock_load.call_count == 1
                assert positions1 == positions2
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_caching_disabled(self):
        """Test that caching doesn't work when disabled"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            with patch(
                "modules.kotak_neo_auto_trader.services.position_loader.load_history"
            ) as mock_load:
                mock_load.return_value = history

                loader = PositionLoader(history_path=temp_path, enable_caching=False)
                # First call
                loader.load_open_positions()
                # Second call
                loader.load_open_positions()

                # Should be called twice (no caching)
                assert mock_load.call_count == 2
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_cache_invalidation_on_file_change(self):
        """Test that cache is invalidated when file changes"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history1 = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history1, f)

        try:
            loader = PositionLoader(history_path=temp_path, enable_caching=True)
            # First call
            positions1 = loader.load_open_positions()
            assert positions1[0]["symbol"] == "RELIANCE"

            # Wait a bit to ensure file mtime changes
            time.sleep(0.1)

            # Modify file
            history2 = {
                "trades": [{"symbol": "TCS", "status": "open", "qty": 15}],
                "failed_orders": [],
            }
            with open(temp_path, "w") as f:
                json.dump(history2, f)

            # Second call should reload due to file change
            positions2 = loader.load_open_positions()
            assert positions2[0]["symbol"] == "TCS"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_clear_cache(self):
        """Test clear_cache() method"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            with patch(
                "modules.kotak_neo_auto_trader.services.position_loader.load_history"
            ) as mock_load:
                mock_load.return_value = history

                loader = PositionLoader(history_path=temp_path, enable_caching=True)
                loader.load_open_positions()  # Populate cache
                loader.clear_cache()
                loader.load_open_positions()  # Should reload

                assert mock_load.call_count == 2
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_invalidate_cache(self):
        """Test invalidate_cache() method"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
            history = {
                "trades": [{"symbol": "RELIANCE", "status": "open", "qty": 10}],
                "failed_orders": [],
            }
            json.dump(history, f)

        try:
            with patch(
                "modules.kotak_neo_auto_trader.services.position_loader.load_history"
            ) as mock_load:
                mock_load.return_value = history

                loader = PositionLoader(history_path=temp_path, enable_caching=True)
                loader.load_open_positions()  # Populate cache
                loader.invalidate_cache()  # Invalidate
                loader.load_open_positions()  # Should reload

                assert mock_load.call_count == 2
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
