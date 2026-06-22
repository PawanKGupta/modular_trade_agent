# Release Plan v26.2.3.1

**Branch:** `hotfix/limit_order_fill_price`
**Version:** 26.2.3.1 (CalVer Q2 2026 hotfix patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.3.1]`

---

## Scope

Single bugfix on top of `v26.2.3`:

| Theme | Operator impact |
|-------|-----------------|
| Paper trading limit fill price | Buy/sell limit orders now fill at the actual market price when it is better than the limit, matching real NSE exchange behaviour and producing accurate P&L |

---

## Pre-release verification

| Gate | Result (2026-06-22 local) |
|------|---------------------------|
| `test_execute_limit_buy_below_market` | Passes — fills at current price (1450), not limit (1500) |
| `test_execute_limit_sell_above_market` | Passes — fills at current price (3500), not limit (3400) |
| Full `tests/paper_trading/test_order_simulator.py` suite | **23 passed** |
| Ruff + Black | Clean |

---

## Deploy steps

1. Pull `hotfix/limit_order_fill_price` or tag `v26.2.3.1`.
2. Restart the Python trading service (no frontend change, no DB migration).
3. **Post-deploy smoke:**
   - Run a paper trading cycle during pre-open (9:00–9:15 IST).
   - Confirm buy orders placed as LIMIT fill at the opening price when the stock opens below yesterday's close — not at the limit price.
   - Confirm paper P&L entries reflect the lower (actual) fill price.

---

## Rollback

- Redeploy previous tag/container image (`v26.2.3`).

---

## Deliverables checklist

- [x] Version `26.2.3.1` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.3.1]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-26231)
- [ ] Tag `v26.2.3.1` on branch tip (local; push with explicit approval)

---

## Related docs

- [Upgrading to 26.2.3.1](../deployment/DEPLOYMENT.md#upgrading-to-26231)
- [Release Plan v26.2.3](RELEASE_PLAN_V26.2.3.md)
