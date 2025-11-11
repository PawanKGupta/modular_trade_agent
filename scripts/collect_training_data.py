#!/usr/bin/env python3
"""
Collect Training Data from Backtest Results - WITH RE-ENTRY EXTRACTION

This version extracts features for EACH fill (initial + re-entries), not just the initial entry.

Phase 5 Enhancement: Re-entry extraction for ML training
- Extract features at each fill date (initial entry + all re-entries)
- Use position-level P&L for all fills (Approach A)
- Add context features: is_reentry, fill_number, total_fills, position_id
- Quantity-based sample weighting (proportional to share contribution)

LOOK-AHEAD BIAS FIX (2025-11-12):
=====================================
Backtest flow:
  Day X: Signal detected → Day X+1: Execute at open → entry_date = Day X+1

Training data extraction:
  entry_date = Day X+1 (from backtest)
  Features extracted from: Day X close data (signal day - what we knew!)

This prevents look-ahead bias where the model would see Day X+1's close data
that wasn't available when the trading decision was made.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import argparse
from typing import List, Dict, Optional
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService
from core.feature_engineering import calculate_all_dip_features


def extract_features_at_date(
    ticker: str,
    entry_date: str,
    data_service: DataService,
    indicator_service: IndicatorService,
    signal_service: SignalService,
    verdict_service: VerdictService
) -> Optional[Dict]:
    """
    Extract features at a specific entry date

    LOOK-AHEAD BIAS FIX (2025-11-12):
    =====================================
    In backtest:
      - Day X: Signal detected (RSI < 30, etc.) using Day X's close data
      - Day X+1: Trade executed at open price (entry_date = Day X+1)

    In training:
      - entry_date = Day X+1 (execution day from backtest)
      - Features should use Day X's close data (signal day = what we knew when deciding!)
      - NOT Day X+1's close data (that's look-ahead bias!)

    Example:
      - Signal: Nov 10 evening (had Nov 10 close, volume, RSI)
      - Entry: Nov 11 morning open (entry_date = "2024-11-11")
      - Features: Use Nov 10 close data (signal_date = "2024-11-10")

    Args:
        ticker: Stock ticker
        entry_date: Entry date from backtest (YYYY-MM-DD) - execution day!
        data_service: Data service instance
        indicator_service: Indicator service instance
        signal_service: Signal service instance
        verdict_service: Verdict service instance

    Returns:
        Dict with features or None if extraction fails
    """
    try:
        # LOOK-AHEAD BIAS FIX: Calculate signal date (day before entry/execution)
        entry_datetime = datetime.strptime(entry_date, '%Y-%m-%d')
        signal_date = entry_datetime - timedelta(days=1)

        # Skip weekends: if signal_date falls on Saturday/Sunday, go back to Friday
        while signal_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            signal_date -= timedelta(days=1)

        signal_date_str = signal_date.strftime('%Y-%m-%d')

        logger.debug(f"{ticker}: Entry={entry_date}, Signal={signal_date_str} (using signal day for features)")

        # Fetch data up to SIGNAL date (not entry date!) to avoid look-ahead bias
        df = data_service.fetch_single_timeframe(
            ticker=ticker,
            end_date=signal_date_str,  # ← CHANGED: Use signal date, not entry date
            add_current_day=False
        )

        if df is None or df.empty or len(df) < 50:
            return None

        # Calculate indicators
        df = indicator_service.compute_indicators(df)
        if df is None or df.empty:
            return None

        # Get latest row (signal date - what we had when making decision)
        last = df.iloc[-1]

        # Extract features
        features = {
            'ticker': ticker,
            'entry_date': entry_date,

            # Technical indicators
            'rsi_10': float(last.get('rsi10', 0)) if pd.notna(last.get('rsi10')) else None,
            # REMOVED: ema200 (redundant with price_above_ema200 boolean)
            # REMOVED: price (absolute price not useful for ML)
            'price_above_ema200': bool(pd.notna(last.get('ema200')) and last['close'] > last['ema200']),

            # Volume features
            # REMOVED: volume (absolute volume redundant with volume_ratio)
            'avg_volume_20': float(df['volume'].tail(20).mean()) if len(df) >= 20 else None,
            'volume_ratio': float(last['volume'] / df['volume'].tail(20).mean()) if len(df) >= 20 and df['volume'].tail(20).mean() > 0 else 1.0,
            'vol_strong': bool(last['volume'] >= 1.5 * df['volume'].tail(20).mean()) if len(df) >= 20 else False,

            # Price action
            'recent_high_20': float(df['high'].tail(20).max()) if len(df) >= 20 else None,
            'recent_low_20': float(df['low'].tail(20).min()) if len(df) >= 20 else None,
            'support_distance_pct': float(((last['close'] - df['low'].tail(20).min()) / last['close']) * 100) if len(df) >= 20 else None,

            # Patterns (simplified)
            'has_hammer': False,  # Will be computed if needed
            'has_bullish_engulfing': False,  # Will be computed if needed
            'has_divergence': False,  # Will be computed if needed

            # Multi-timeframe (simplified - would need weekly data)
            'alignment_score': 0,  # Will be computed if needed
        }

        # Detect patterns
        if len(df) >= 2:
            prev = df.iloc[-2]
            signals = signal_service.detect_pattern_signals(df, last, prev)
            features['has_hammer'] = 'hammer' in signals
            features['has_bullish_engulfing'] = 'bullish_engulfing' in signals
            features['has_divergence'] = 'bullish_divergence' in signals
        else:
            features['has_hammer'] = False
            features['has_bullish_engulfing'] = False
            features['has_divergence'] = False

        # Get fundamentals if available
        try:
            fundamentals = verdict_service.fetch_fundamentals(ticker)
            features['pe'] = fundamentals.get('pe')
            features['pb'] = fundamentals.get('pb')
            features['fundamental_ok'] = not (fundamentals.get('pe') is not None and fundamentals.get('pe') < 0)
        except:
            features['pe'] = None
            features['pb'] = None
            features['fundamental_ok'] = True

        # ML ENHANCED DIP FEATURES (Phase 4): Add advanced dip-buying features
        try:
            dip_features = calculate_all_dip_features(df)
            features.update(dip_features)
            logger.debug(f"{ticker}: Added dip features (depth={dip_features['dip_depth_from_20d_high_pct']:.1f}%)")
        except Exception as e:
            logger.warning(f"{ticker}: Failed to calculate dip features: {e}, using defaults")
            # Add default values
            features['dip_depth_from_20d_high_pct'] = 0.0
            features['consecutive_red_days'] = 0
            features['dip_speed_pct_per_day'] = 0.0
            features['decline_rate_slowing'] = False
            features['volume_green_vs_red_ratio'] = 1.0
            features['support_hold_count'] = 0

        # MARKET REGIME FEATURES (2025-11-11): Add broader market context
        # Uses signal_date (day before entry) to match feature extraction timing
        try:
            from services.market_regime_service import get_market_regime_service
            
            market_regime_service = get_market_regime_service()
            market_features = market_regime_service.get_market_regime_features(
                date=signal_date_str  # Use signal date for consistency
            )
            
            features['nifty_trend'] = market_features['nifty_trend']
            features['nifty_vs_sma20_pct'] = market_features['nifty_vs_sma20_pct']
            features['nifty_vs_sma50_pct'] = market_features['nifty_vs_sma50_pct']
            features['india_vix'] = market_features['india_vix']
            features['sector_strength'] = market_features['sector_strength']
            
            logger.debug(f"{ticker}: Added market regime features (trend={market_features['nifty_trend']}, vix={market_features['india_vix']:.1f})")
        except Exception as e:
            logger.warning(f"{ticker}: Failed to fetch market regime features: {e}, using defaults")
            features['nifty_trend'] = 0.0  # Neutral
            features['nifty_vs_sma20_pct'] = 0.0
            features['nifty_vs_sma50_pct'] = 0.0
            features['india_vix'] = 20.0  # Average VIX
            features['sector_strength'] = 0.0

        return features

    except Exception as e:
        logger.debug(f"Failed to extract features for {ticker} at {entry_date}: {e}")
        return None


def create_labels_from_backtest_results_with_reentry(backtest_results: Dict) -> List[Dict]:
    """
    Create labeled training examples from backtest results
    WITH RE-ENTRY EXTRACTION (Phase 5)

    This function extracts features for EACH fill (initial + re-entries), not just the initial entry.

    Args:
        backtest_results: Backtest results dictionary (can be pandas Series or dict)

    Returns:
        List of labeled training examples
    """
    labeled_examples = []

    # Handle pandas Series
    if hasattr(backtest_results, 'to_dict'):
        backtest_results = backtest_results.to_dict()

    if 'full_results' not in backtest_results or not backtest_results['full_results']:
        return labeled_examples

    # Parse full_results if it's a string (from CSV)
    full_results_str = backtest_results['full_results']
    if isinstance(full_results_str, str):
        try:
            import re
            import numpy as np
            from pandas import Timestamp

            # Create a safe namespace for eval (allow numpy types, pandas Timestamp, and basic dict/list)
            safe_dict = {"__builtins__": {}, "dict": dict, "list": list, "np": np, "Timestamp": Timestamp}

            # Clean up the string - replace np.float64 with float
            cleaned = re.sub(r'np\.float64\(([^)]+)\)', r'\1', full_results_str)

            # Evaluate safely
            full_results = eval(cleaned, safe_dict)

            # Convert numpy types and Timestamps to Python types
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                elif isinstance(obj, Timestamp):
                    return obj.strftime('%Y-%m-%d')  # Convert Timestamp to string
                elif hasattr(obj, 'item'):  # numpy scalar
                    return obj.item()
                elif isinstance(obj, (np.integer, np.floating)):
                    return float(obj) if isinstance(obj, np.floating) else int(obj)
                else:
                    return obj

            full_results = convert_numpy_types(full_results)

        except Exception as e:
            logger.warning(f"Could not parse full_results for {backtest_results.get('ticker')}: {e}")
            logger.debug(f"Full results string (first 500 chars): {full_results_str[:500]}")
            return labeled_examples
    else:
        full_results = full_results_str

    if not isinstance(full_results, dict):
        logger.debug(f"full_results is not a dict: {type(full_results)}")
        return labeled_examples

    if 'positions' not in full_results:
        logger.debug(f"full_results has no 'positions' key. Keys: {list(full_results.keys())}")
        return labeled_examples

    positions = full_results['positions']

    if not positions:
        logger.info(f"  No positions found for {backtest_results.get('ticker')}")
        return labeled_examples

    logger.info(f"  Found {len(positions)} positions for {backtest_results.get('ticker')}")

    # Initialize services
    data_service = DataService()
    indicator_service = IndicatorService()
    signal_service = SignalService()
    verdict_service = VerdictService()

    ticker = backtest_results['ticker']

    for position in positions:
        if not isinstance(position, dict):
            logger.debug(f"Position is not a dict: {type(position)}")
            continue

        # Get position-level data (same for all fills)
        exit_date = position.get('exit_date')
        pnl_pct = position.get('pnl_pct', 0) or position.get('return_pct', 0)  # Try both keys
        exit_reason = position.get('exit_reason', 'Unknown')
        max_drawdown_pct = position.get('max_drawdown_pct', 0.0)

        # Calculate holding_days
        days_to_exit = position.get('days_to_exit')
        if days_to_exit is not None:
            holding_days = days_to_exit
        elif exit_date and position.get('entry_date'):
            try:
                entry_dt = datetime.strptime(position.get('entry_date'), '%Y-%m-%d')
                exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
                holding_days = (exit_dt - entry_dt).days
            except:
                holding_days = None
        else:
            holding_days = None

        # RE-ENTRY EXTRACTION (Phase 5): Extract features for EACH fill
        fills = position.get('fills', [])

        # Backward compatibility: if no fills array, create one from entry_date
        if not fills:
            entry_date = position.get('entry_date')
            entry_price = position.get('entry_price')
            if entry_date and entry_price:
                fills = [{
                    'date': pd.to_datetime(entry_date) if not isinstance(entry_date, pd.Timestamp) else entry_date,
                    'price': float(entry_price),
                    'capital': position.get('capital', 50000)
                }]

        if not fills:
            logger.debug(f"  No fills found for position in {ticker}")
            continue

        # Get initial fill info for context
        initial_fill = fills[0]
        initial_date = initial_fill['date']
        if isinstance(initial_date, pd.Timestamp):
            initial_date_str = initial_date.strftime('%Y-%m-%d')
        else:
            initial_date_str = str(initial_date)

        initial_price = float(initial_fill.get('price', 0))
        total_fills = len(fills)

        # Create position ID for cross-validation grouping
        position_id = f"{ticker}_{initial_date_str.replace('-', '')}"

        # Calculate total quantity for quantity-based weighting
        total_quantity = sum(float(f.get('quantity', 0)) for f in fills)

        logger.info(f"    Processing position: {initial_date_str} ({total_fills} fills, P&L: {pnl_pct:.2f}%)")

        # Extract features for EACH fill (initial + re-entries)
        for fill_idx, fill in enumerate(fills):
            fill_date = fill['date']
            if isinstance(fill_date, pd.Timestamp):
                fill_date_str = fill_date.strftime('%Y-%m-%d')
            else:
                fill_date_str = str(fill_date)

            fill_price = float(fill.get('price', 0))
            is_reentry = (fill_idx > 0)

            logger.info(f"      {'Re-entry' if is_reentry else 'Initial'} #{fill_idx+1}: {fill_date_str} @ {fill_price:.2f}")

            # Extract features at this fill date
            try:
                features = extract_features_at_date(
                    ticker=ticker,
                    entry_date=fill_date_str,
                    data_service=data_service,
                    indicator_service=indicator_service,
                    signal_service=signal_service,
                    verdict_service=verdict_service
                )

                if not features:
                    logger.warning(f"        Failed to extract features for {ticker} at {fill_date_str}")
                    continue

            except Exception as e:
                logger.warning(f"        Error extracting features for {ticker} at {fill_date_str}: {e}")
                continue

            # Create label based on POSITION-LEVEL outcome (Approach A)
            # Good trades (>10% gain) = strong_buy
            # Decent trades (5-10% gain) = buy
            # Small gains (0-5% gain) = watch
            # Losses (<0%) = avoid
            pnl_pct_value = float(pnl_pct) if hasattr(pnl_pct, '__float__') else pnl_pct

            if pnl_pct_value >= 10:
                label = 'strong_buy'
            elif pnl_pct_value >= 5:
                label = 'buy'
            elif pnl_pct_value >= 0:
                label = 'watch'
            else:
                label = 'avoid'

            # Add position-level outcome (same for all fills in this position)
            features['label'] = label
            features['actual_pnl_pct'] = pnl_pct_value
            features['exit_date'] = exit_date
            features['exit_reason'] = exit_reason
            features['max_drawdown_pct'] = max_drawdown_pct
            features['holding_days'] = holding_days

            # RE-ENTRY CONTEXT FEATURES (Phase 5): Help ML distinguish fills
            features['is_reentry'] = is_reentry
            features['fill_number'] = fill_idx + 1
            features['total_fills_in_position'] = total_fills
            features['position_id'] = position_id
            features['fill_price'] = fill_price
            features['initial_entry_price'] = initial_price
            features['initial_entry_date'] = initial_date_str

            # Calculate fill price vs initial entry (negative = averaged down)
            if initial_price > 0:
                features['fill_price_vs_initial_pct'] = ((fill_price - initial_price) / initial_price) * 100
            else:
                features['fill_price_vs_initial_pct'] = 0.0

            # QUANTITY-BASED SAMPLE WEIGHT (Phase 5 Enhancement)
            # Weight by quantity contribution: re-entries at lower prices buy more shares
            # and contribute more to P&L, so they get proportionally higher weight
            fill_quantity = float(fill.get('quantity', 0))
            if total_quantity > 0:
                features['sample_weight'] = fill_quantity / total_quantity
            else:
                # Fallback to simple weighting if quantity data unavailable
                features['sample_weight'] = 1.0 if not is_reentry else 0.5

            features['fill_quantity'] = fill_quantity  # Add for reference

            labeled_examples.append(features)
            logger.info(f"        Extracted features for fill #{fill_idx+1}")

    return labeled_examples


def collect_training_data(
    backtest_file: str,
    output_file: str = "data/ml_training_data_reentry.csv"
) -> pd.DataFrame:
    """
    Collect training data from backtest results
    WITH RE-ENTRY EXTRACTION (Phase 5)

    Args:
        backtest_file: Path to backtest results CSV
        output_file: Path to save training data

    Returns:
        DataFrame with training data
    """
    logger.info(f"Loading backtest results from {backtest_file}...")

    # Load backtest results
    df_backtest = pd.read_csv(backtest_file)

    logger.info(f"Found {len(df_backtest)} backtest results")

    all_training_data = []
    total = len(df_backtest)

    for i, row in df_backtest.iterrows():
        ticker = row['ticker']
        logger.info(f"[{i+1}/{total}] Processing {ticker}...")

        # Create labeled examples from this backtest result (WITH RE-ENTRY EXTRACTION)
        examples = create_labels_from_backtest_results_with_reentry(row)

        if examples:
            all_training_data.extend(examples)
            logger.info(f"  Created {len(examples)} training examples from {ticker}")
        else:
            logger.warning(f"  No valid training examples from {ticker}")

    if not all_training_data:
        logger.warning("No training data collected")
        return pd.DataFrame()

    logger.info(f"\nCollected {len(all_training_data)} total training examples")

    # Convert to DataFrame
    df_training = pd.DataFrame(all_training_data)

    # Save to CSV
    df_training.to_csv(output_file, index=False)
    logger.info(f"Saved training data to {output_file}")

    # Print summary
    logger.info(f"\nTraining Data Summary:")
    logger.info(f"  Total Examples: {len(df_training)}")
    logger.info(f"  Unique Tickers: {df_training['ticker'].nunique()}")
    logger.info(f"  Unique Positions: {df_training['position_id'].nunique()}")
    logger.info(f"  Re-entries: {df_training['is_reentry'].sum()}")
    logger.info(f"  Initial Entries: {(~df_training['is_reentry']).sum()}")
    logger.info(f"\nLabel Distribution:")
    logger.info(df_training['label'].value_counts())

    return df_training


def main():
    parser = argparse.ArgumentParser(description='Collect training data from backtest results WITH RE-ENTRY EXTRACTION')
    parser.add_argument('--backtest-file', required=True, help='Path to backtest results CSV')
    parser.add_argument('--output', default='data/ml_training_data_reentry.csv', help='Output file path')

    args = parser.parse_args()

    collect_training_data(args.backtest_file, args.output)


if __name__ == '__main__':
    main()

