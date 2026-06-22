# Release Plan v26.2.3.1

**Branch:** `hotfix/limit_order_fill_price`
**Version:** 26.2.3.1 (CalVer Q2 2026 hotfix patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.3.1]`

---

## Scope

Two commits on top of `v26.2.3`:

| Theme | Operator impact |
|-------|-----------------|
| Paper trading buy limit fill price | Buy limit orders now fill at `current_price` (market price) rather than `order.price` (limit price) when `current_price ≤ limit` — matches real NSE exchange price improvement; lower entry costs and accurate P&L |
| Sell limit fill price scoped correctly | Sell limit orders (EMA9 targets) continue to fill at `order.price` — realistic fills for sells go through the daily-high touch path, not a live price snapshot |

---

## Pre-release verification

| Gate | Result (2026-06-22 local) |
|------|---------------------------|
| `test_execute_limit_buy_below_market` | Passes — buy fills at current price (1450), not limit (1500) |
| `test_execute_limit_sell_above_market` | Passes — sell fills at limit price (3400), not current price (3500) |
| Full `tests/paper_trading/test_order_simulator.py` suite | **23 passed** |
| Ruff + Black | Clean |

---

## Deploy steps

1. Pull `hotfix/limit_order_fill_price` or tag `v26.2.3.1`.
2. Restart the Python trading service (no frontend change, no DB migration).
3. **Post-deploy smoke:**
   - Run a paper trading cycle during pre-open (9:00–9:15 IST).
   - Confirm buy LIMIT orders fill at the opening price when the stock opens below yesterday's close — not at the limit price.
   - Confirm sell LIMIT orders still fill at the EMA9 target price.
   - Confirm paper P&L entries reflect the corrected (lower) buy entry price.

---

## Rollback

- Redeploy previous tag/container image (`v26.2.3`).

---

## Deliverables checklist

- [x] Version `26.2.3.1` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.3.1]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-26231)
- [x] Tag `v26.2.3.1` on branch tip

---

## Related docs

- [Upgrading to 26.2.3.1](../deployment/DEPLOYMENT.md#upgrading-to-26231)
- [Release Plan v26.2.3](RELEASE_PLAN_V26.2.3.md)
