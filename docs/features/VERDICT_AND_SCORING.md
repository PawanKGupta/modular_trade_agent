# Verdict and Scoring Reference

**Source of truth:** `services/verdict_service.py`, `services/scoring_service.py`, `config/strategy_config.py`

**Related:** [Chart Quality Guide](CHART_QUALITY_USAGE_GUIDE.md) · [ML Integration Guide](../architecture/ML_COMPLETE_GUIDE.md) · [Two-Stage Chart Quality + ML](TWO_STAGE_CHART_QUALITY_ML_APPROACH.md) · [Trading Configuration](../guides/TRADING_CONFIG.md)

---

## Overview

Stock analysis uses two complementary service layers:

| Service | Role | Output |
|---------|------|--------|
| **`VerdictService`** | Classifies a setup as `strong_buy`, `buy`, `watch`, or `avoid`; computes buy range, target, and stop | Verdict + justification + trading parameters |
| **`ScoringService`** | Ranks and weights signals **after** verdict (or alongside backtest) | Strength (0–25), priority (0–100+), combined score |

**Important:** Verdict classification is **rule- and threshold-based** (RSI, volume, MTF alignment, patterns, fundamentals). It is **not** an additive point tally. Point-based tables below apply to **ScoringService** and to **`alignment_score`** (0–10 MTF metric used inside verdict rules).

---

## Purpose

- **Operators / developers:** Understand why a ticker gets a given verdict and how UI/CSV score columns are computed.
- **Integrators:** Know which fields to pass into each service and where config lives (`StrategyConfig`, env vars).

---

## Pipeline placement

Typical flow (`AnalysisService`, `DetermineVerdictStep`, `trade_agent.py`, `AnalyzeStockUseCase`):

```text
OHLCV + indicators
    → Chart quality (hard filter; may return avoid before verdict)
    → Signals + volume + fundamentals + MTF confirmation
    → VerdictService.determine_verdict()          → verdict, justification
    → VerdictService.apply_candle_quality_check() → optional downgrade buy → watch
    → VerdictService.calculate_trading_parameters() → buy_range, target, stop (buy/strong_buy only)
    → ScoringService.compute_strength_score()     → strength_score
    → [optional backtest]                           → backtest_score, combined_score, final_verdict
    → ScoringService.compute_trading_priority_score() → priority_score (ranking)
```

When ML is enabled, `AnalysisService` may use `MLVerdictService` instead of plain `VerdictService` for prediction; rule-based logic remains the fallback. See [ML Integration Guide](../architecture/ML_COMPLETE_GUIDE.md).

---

## VerdictService

**Location:** `services/verdict_service.py`

### Verdict types

| Verdict | Meaning |
|---------|---------|
| `strong_buy` | Best dip-buy setup (above EMA200 path) |
| `buy` | Valid dip-buy or confirmed reversal |
| `watch` | Partial setup, growth-stock exception, or downgraded from buy |
| `avoid` | Failed hard filters or no actionable setup |

### Hard filters (immediate `avoid`)

Applied inside `determine_verdict()` before classification:

1. **Chart quality failed** (`chart_quality_passed=False`) — see [Chart Quality Guide](CHART_QUALITY_USAGE_GUIDE.md). Default thresholds in `StrategyConfig`:
   - `chart_quality_min_score`: **50.0** (0–100)
   - `chart_quality_max_gap_frequency`: **25.0%**
   - `chart_quality_min_daily_range_pct`: **1.0%**
   - `chart_quality_max_extreme_candle_frequency`: **20.0%**

2. **Fundamental avoid** — loss-making company (negative PE) with PB ≥ `pb_max_for_growth_stock` (default **5.0**) or unknown PB.

### Fundamental assessment (`assess_fundamentals`)

| PE | PB | `fundamental_ok` | `fundamental_growth_stock` | `fundamental_avoid` | Buy allowed? |
|----|----|------------------|----------------------------|---------------------|--------------|
| ≥ 0 or missing | any | true | false | false | Yes |
| < 0 | < 5.0 (default) | false | true | false | No buy; **watch** possible |
| < 0 | ≥ 5.0 or missing | false | false | true | No — **avoid** |

### Core entry gates (buy paths)

All three required for `buy` / `strong_buy`:

| Gate | Above EMA200 | Below EMA200 |
|------|--------------|--------------|
| RSI | `< rsi_oversold` (default **30**) | `< rsi_extreme_oversold` (default **20**) |
| Volume | `vol_ok` (intelligent volume check; RSI-aware relaxation) | same |
| Fundamentals | `fundamental_ok_for_buy` (profitable / PE ≥ 0) | same |

Volume is assessed in `assess_volume()` via `assess_volume_quality_intelligent()` and `get_volume_verdict()`.

### Classification rules (threshold-based)

Uses **`alignment_score`** from MTF confirmation (0–10; computed in `core/timeframe_analysis.py` → `get_dip_buying_alignment_score()`).

**Config thresholds** (`StrategyConfig`):

| Setting | Default | Used when |
|---------|---------|-----------|
| `mtf_alignment_excellent` | 8.0 | Above EMA200 → `strong_buy` |
| `mtf_alignment_fair` | 4.0 | Above EMA200 → `buy` |
| `mtf_alignment_good` | 6.0 | Below EMA200 → `buy` |

#### Above EMA200 (RSI < 30)

| Result | Condition |
|--------|-----------|
| `strong_buy` | `alignment_score >= 8` **or** signal `excellent_uptrend_dip` |
| `buy` | `alignment_score >= 4` **or** signals `good_uptrend_dip`, `fair_uptrend_dip`, `hammer`, `bullish_engulfing` **or** `vol_strong` **or** default if core gates met |

#### Below EMA200 (RSI < 20)

| Result | Condition |
|--------|-----------|
| `buy` | `alignment_score >= 6` **or** `hammer`, `bullish_engulfing`, `bullish_divergence` **or** `vol_strong` |
| `watch` | Core gates met but insufficient confirmation |

#### Partial signals (`watch` / `avoid`)

- Some signals + `vol_ok` but core reversal not met → `watch` (or `watch` for growth stocks; `avoid` for bad fundamentals).
- Growth stock with `rsi_oversold` or `vol_strong` but no other signals → `watch`.
- Otherwise → `avoid`.

### MTF alignment score (0–10)

Built in `MultiTimeframeAnalysis.get_dip_buying_alignment_score()`:

| Component | Max points |
|-----------|------------|
| Daily oversold severity | 3 |
| Weekly uptrend + support context | 2 |
| Daily support confluence | 2 |
| Volume exhaustion (daily + weekly) | 2 |
| Selling-pressure exhaustion | 1 |
| Reversion setup quality bonus | 1 |

**Confirmation labels** (when weekly data present): `excellent_uptrend_dip` (≥8), `good_uptrend_dip` (≥6), `fair_uptrend_dip` (≥4), `weak_uptrend_dip` (≥2), `poor_uptrend_dip` (<2).

### Post-verdict downgrades

1. **News sentiment** — `buy` / `strong_buy` → `watch` when all hold:
   - `news_sentiment.enabled`
   - `used >= NEWS_SENTIMENT_MIN_ARTICLES` (from `StrategyConfig`, default 2)
   - `confidence >= NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE` (default **0.35**, `config/settings.py`)
   - `score <= NEWS_SENTIMENT_DOWNGRADE_SCORE_THRESHOLD` (default **-0.52**)

2. **Candle quality** — `apply_candle_quality_check()` may downgrade `buy` / `strong_buy` → `watch` based on last 3 candles (`core/candle_analysis.py`).

### Trading parameters (`calculate_trading_parameters`)

Only for `buy` / `strong_buy` **and** when RSI is below the adaptive threshold (same as entry gates). Returns `buy_range`, `target`, `stop` via `calculate_smart_buy_range`, `calculate_smart_stop_loss`, `calculate_smart_target`.

### Justification strings

Examples stored in `justification` list: `rsi:28.5(above_ema200)`, `pattern:hammer`, `excellent_uptrend_dip_confirmation`, `volume_strong`, `news_negative`, `growth_stock(pb=2.10<5.0)`.

---

## ScoringService

**Location:** `services/scoring_service.py`

Scoring runs **after** verdict. Non-buy verdicts get **strength score -1** (no strength ranking).

### 1. Strength score (`compute_strength_score`)

**Range:** 0–25 (capped). **Only** `buy` and `strong_buy`.

| Step | Points |
|------|--------|
| Base: `strong_buy` | 10 |
| Base: `buy` | 5 |
| Each pattern in `pattern:…` justification | +2 per pattern |
| `volume_strong` | +1 |
| RSI in `rsi:…` justification | +1 if &lt; 30; +1 if &lt; 20 |
| `excellent_uptrend_dip_confirmation` | +8 |
| `good_uptrend_dip_confirmation` | +5 |
| `fair_uptrend_dip_confirmation` | +3 |

**Timeframe analysis bonuses** (if `timeframe_analysis` present):

| Condition | Points |
|-----------|--------|
| `alignment_score >= 8` | +4 |
| `alignment_score >= 6` | +3 |
| `alignment_score >= 4` | +2 |
| `alignment_score >= 2` | +1 |
| Daily oversold severity `extreme` | +3 |
| Daily oversold severity `high` | +2 |
| Daily support `strong` | +2 |
| Daily support `moderate` | +1 |
| Volume exhaustion score ≥ 2 | +2 |
| Volume exhaustion score ≥ 1 | +1 |

**Chart quality bonus** (if passed hard filter):

| Status | Score | Points |
|--------|-------|--------|
| `clean` | ≥ 80 | +3 |
| `acceptable` | ≥ 70 | +2 |
| `acceptable` | ≥ 60 | +1 |

### 2. Priority score (`compute_trading_priority_score`)

**Range:** 0–100+ (uncapped except MTF slice). Used to **sort** buy candidates (`trade_agent.py`, order placement). Higher = trade first.

| Factor | Thresholds | Points |
|--------|------------|--------|
| Risk/reward ratio | ≥ 4.0 / 3.0 / 2.0 / 1.5 | 40 / 30 / 20 / 10 |
| RSI | ≤ 15 / 20 / 25 / 30 | 25 / 20 / 15 / 10 |
| Volume multiplier | ≥ 4.0 / 2.0 / 1.5 / 1.2 | 20 / 15 / 10 / 5 |
| MTF `alignment_score` | min(score, 10) | up to 10 |
| PE (positive) | ≤ 15 / 25 / 35; ≥ 50 penalty | +10 / +5 / +2 / **-5** |
| Backtest score | ≥ 40 / 30 / 20 | 15 / 10 / 5 |
| Chart quality | clean ≥80 / acceptable ≥70 / ≥60 | 10 / 7 / 5 |

On error, falls back to `combined_score` or `strength_score`.

**ML confidence boost** (order engine only, not in `ScoringService`): see [ML Configuration doc](../development/ML_CONFIGURATION_AND_QUALITY_FILTERING_ENHANCEMENTS.md) — +20 / +10 / +5 for high/medium/low ML confidence when loading recommendations.

### 3. Combined score (`compute_combined_score`)

```text
combined = (current_score × current_weight) + (backtest_score × backtest_weight)
```

Defaults: **50% / 50%** (`StrategyConfig.backtest_weight` = 0.5). Used when `--backtest` is enabled.

**`final_verdict`** (backtest path) reclassifies using `backtest_score`, `combined_score`, trade count, and RSI adjustments in `core/backtest_scoring.py` / `AnalyzeStockUseCase._compute_final_verdict`. Filtering for auto-trade often requires `final_verdict ∈ {buy, strong_buy}` and `combined_score >= min_combined_score` (see [Kotak Neo README](../kotak_neo_trader/README.md)).

---

## Configuration reference

Primary: `config/strategy_config.py` (overridable via env — see file for names).

| Area | Key settings |
|------|----------------|
| RSI | `rsi_oversold`, `rsi_extreme_oversold` |
| MTF verdict thresholds | `MTF_ALIGNMENT_EXCELLENT`, `MTF_ALIGNMENT_GOOD`, `MTF_ALIGNMENT_FAIR` |
| Chart quality | `CHART_QUALITY_*` |
| Growth-stock PB cap | `pb_max_for_growth_stock` |
| Backtest blend | `backtest_weight` |
| ML overlay | `ml_enabled`, `ml_confidence_threshold`, `ml_combine_with_rules` |

User-facing trading config UI maps into `StrategyConfig` via the config converter — see [Trading Configuration](../guides/TRADING_CONFIG.md).

---

## UI and API fields

Common columns (see [UI Guide](../guides/UI_GUIDE.md)):

| Field | Service / stage |
|-------|-----------------|
| `verdict` | VerdictService (rule or ML) |
| `ml_verdict`, `ml_confidence` | MLVerdictService (optional) |
| `strength_score` | ScoringService |
| `priority_score` | ScoringService |
| `backtest_score`, `combined_score`, `final_verdict` | Backtest + ScoringService |
| `justification` | VerdictService |

---

## Edge cases and notes

- **Verdict vs scores:** A stock can be `buy` with a low strength score if justification bonuses are minimal; conversely, strength score is only computed for buy-class verdicts.
- **Chart quality vs strength bonus:** Hard filter uses `chart_quality_min_score`; strength/priority bonuses use higher bars (60–80).
- **Below EMA200:** Stricter RSI (20) and MTF (good ≥ 6); default partial match is `watch`, not `buy`.
- **Deprecated path:** `core/scoring.py` delegates to `ScoringService`; prefer the service import for new code.
- **Historical docs:** Older verdict write-ups under `archive/documents/VERDICT_*.md` may use stale MTF thresholds (e.g. 60/80 on a 0–100 scale). This page reflects current code.

---

## Example (conceptual)

```python
from services import VerdictService, ScoringService

verdict_svc = VerdictService()
scoring_svc = ScoringService()

verdict, justification = verdict_svc.determine_verdict(
    signals=["hammer", "good_uptrend_dip"],
    rsi_value=27.5,
    is_above_ema200=True,
    vol_ok=True,
    vol_strong=False,
    fundamental_ok=True,
    timeframe_confirmation={"alignment_score": 7, "confirmation": "good_uptrend_dip"},
    news_sentiment=None,
    chart_quality_passed=True,
)

analysis = {
    "verdict": verdict,
    "justification": justification,
    "timeframe_analysis": {"alignment_score": 7, "daily_analysis": {...}, "weekly_analysis": {...}},
    "rsi": 27.5,
    "risk_reward_ratio": 3.2,
}

strength = scoring_svc.compute_strength_score(analysis)      # e.g. 5 + bonuses → capped at 25
priority = scoring_svc.compute_trading_priority_score(analysis)  # e.g. 30 + 10 + 7 + ...
```

---

## Maintenance

When changing verdict or scoring logic, update **this file** and any affected config docs (`TRADING_CONFIG.md`, chart quality guide). Do not duplicate full scoring tables elsewhere — link here instead.
