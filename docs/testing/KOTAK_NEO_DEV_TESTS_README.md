# Development & Integration Tests

This directory contains development and integration test scripts for the Kotak Neo Auto Trader module. These are **manual/interactive tests** that connect to live Kotak Neo APIs and are used for development, debugging, and verification purposes.

## ⚠️ Important Notes

### NOT Unit Tests
These are **not** unit tests and are **not** part of the automated test suite in `tests/`.

### Live API Tests
- These scripts connect to **real Kotak Neo APIs**
- They may place actual orders (with low prices to prevent execution)
- They use real credentials from `kotak_neo.env`
- They may incur API rate limits

### Usage
Run these scripts individually for development/debugging:
```bash
# From project root
python modules/kotak_neo_auto_trader/dev_tests/test_order_modification.py
python modules/kotak_neo_auto_trader/dev_tests/test_ltp_kotak.py
```

---

## Test Categories

### 1. Order Management Tests
Test real order placement, modification, and cancellation flows.

- **test_order_modification.py** (9.7KB)
  - Places real BUY order (low price to prevent execution)
  - Modifies order quantity
  - Cancels order
  - **Use case**: Verify order modification API works

### 2. Price/Quote Tests
Test fetching Last Traded Price (LTP) and quotes from Kotak Neo.

- **test_ltp_kotak.py** (4.5KB)
  - Fetch LTP using instrument token
  - Test quote() method
  - **Use case**: Debug LTP retrieval

- **test_exact_quote.py** (2.4KB)
  - Test exact quote method signature
  - **Use case**: API method verification

- **test_quotes_method.py** (3.6KB)
  - Test quotes() method (plural)
  - **Use case**: Alternative quote API

### 3. WebSocket/Real-Time Tests
Test live WebSocket connections and real-time data streaming.

- **test_websocket_subscribe.py** (6KB)
  - Test WebSocket subscribe for live LTP
  - **Use case**: Verify WebSocket connectivity

- **test_realtime_position_monitor.py** (5.1KB) - DEPRECATED
  - Test real-time position monitoring (position monitor removed in Phase 3)
  - WebSocket LTP + EMA9 calculation
  - **Use case**: Verify live price streaming (no longer used)

### 4. Volume Filtering Tests
Test volume-based filtering for different stock types.

- **test_volume_filter.py** (1.2KB)
  - Low liquidity stocks (CURAA)
  - **Use case**: Verify volume filter edge cases

- **test_volume_normal.py** (2.4KB)
  - High liquidity stocks
  - **Use case**: Ensure filter doesn't break normal stocks

- **test_real_stocks.py** (3.3KB)
  - Real portfolio stocks
  - **Use case**: Test with actual holdings

- **test_tiered_volume.py** (2.5KB)
  - Price-tiered volume filtering
  - **Use case**: Verify tiered logic

- **test_position_volume_ratio.py** (2.6KB)
  - Position-to-volume ratio with real data
  - **Use case**: Verify ratio calculations

### 5. Compatibility & Bug Fix Tests
Test backward compatibility and specific bug fixes.

- **test_backward_compat.py** (1.7KB)
  - Volume filtering backward compatibility
  - **Use case**: Ensure old code still works

- **test_bom_fix.py** (2.1KB)
  - UTF-8 BOM fix verification
  - **Use case**: Verify BOM handling

### 6. Client/Connection Tests
Test client attributes and connection details.

- **test_client_attrs.py** (2.3KB)
  - Inspect client attributes (server_id/sid)
  - **Use case**: Debug client object

- **test_hsserverid.py** (2.1KB)
  - Check hsServerId after login
  - **Use case**: Verify server ID handling

---

## Running Dev Tests

### Prerequisites
1. Valid Kotak Neo credentials in `kotak_neo.env`
2. Active internet connection
3. Market hours (for some tests)

### Run Individual Test
```bash
# From project root
python modules/kotak_neo_auto_trader/dev_tests/test_order_modification.py
```

### Common Issues
- **Login failures**: Check credentials in `kotak_neo.env`
- **2FA required**: Some tests may need manual OTP entry
- **Rate limits**: Don't run too many tests consecutively
- **Market hours**: Some tests work better during market hours

---

## Test File Summary

| Test File | Size | Purpose | API Calls |
|-----------|------|---------|-----------|
| test_order_modification.py | 9.7KB | Order modify/cancel | Place, Modify, Cancel orders |
| test_websocket_subscribe.py | 6.0KB | WebSocket streaming | WebSocket subscribe |
| test_realtime_position_monitor.py | 5.1KB | Real-time monitoring (DEPRECATED) | WebSocket + positions |
| test_ltp_kotak.py | 4.5KB | LTP retrieval | Quote API |
| test_quotes_method.py | 3.6KB | Quotes API | Quotes (plural) |
| test_real_stocks.py | 3.3KB | Portfolio stocks | Volume filtering |
| test_position_volume_ratio.py | 2.6KB | Volume ratio | Position data |
| test_tiered_volume.py | 2.5KB | Tiered filtering | Volume data |
| test_exact_quote.py | 2.4KB | Quote method | Quote API |
| test_volume_normal.py | 2.4KB | Normal stocks | Volume filtering |
| test_client_attrs.py | 2.3KB | Client inspection | Login |
| test_hsserverid.py | 2.1KB | Server ID check | Login |
| test_bom_fix.py | 2.1KB | BOM handling | File operations |
| test_backward_compat.py | 1.7KB | Compatibility | None (offline) |
| test_volume_filter.py | 1.2KB | Low liquidity | Volume filtering |

**Total**: 15 test files, ~55KB

---

## Differences from Unit Tests

| Aspect | Unit Tests (`tests/`) | Dev Tests (here) |
|--------|----------------------|------------------|
| **Purpose** | Automated regression | Manual development/debugging |
| **API Calls** | Mocked | Real Kotak Neo APIs |
| **Credentials** | Not needed | Required |
| **Execution** | `pytest tests/` | Run individually |
| **CI/CD** | Yes, automated | No, manual only |
| **Speed** | Fast (seconds) | Slow (API calls) |
| **Coverage** | Tracked | Not tracked |

---

## Maintenance

### When to Add Tests Here
- Debugging a specific API issue
- Verifying a new Kotak Neo API feature
- Testing edge cases with real data
- Reproducing a bug with live API

### When to Use Unit Tests Instead
- Automated regression testing
- Fast feedback during development
- CI/CD pipeline
- Testing logic without API calls

### Cleanup
Review and remove obsolete dev tests periodically:
- Tests for fixed bugs that now have unit tests
- Tests for deprecated APIs
- Tests that no longer provide value

---

## Security Notes

### Credentials
- These tests use real credentials from `kotak_neo.env`
- **NEVER** hardcode credentials in test files
- Ensure `kotak_neo.env` is in `.gitignore`

### Orders
- Order tests use low prices to prevent execution
- Always cancel orders after testing
- Monitor your Kotak Neo account for accidental orders

### Rate Limits
- Kotak Neo APIs have rate limits
- Don't run tests in a loop
- Space out test runs

---

## Future Improvements

### Potential Enhancements
- [ ] Add command-line arguments for test configuration
- [ ] Create test runner script for multiple tests
- [ ] Add result logging/reporting
- [ ] Mock mode for offline testing
- [ ] Integration with pytest (optional)

### Potential Migrations
Consider moving stable tests to unit tests:
- Mock external APIs
- Add to automated test suite
- Track coverage

---

## Documentation

### Related Documentation
- `tests/` - Automated unit/integration tests
- `tests/regression/` - Regression tests
- `COMMANDS.md` - Production commands
- `UNIFIED_TRADING_SERVICE.md` - Service documentation

### Getting Help
If a dev test fails:
1. Check credentials in `kotak_neo.env`
2. Verify internet connectivity
3. Check Kotak Neo API status
4. Review test output for error details
5. Check logs in `logs/` directory

---

**Directory Created**: January 2025
**Purpose**: Development & Integration Testing
**Test Count**: 15 files
**Status**: Active development tests
