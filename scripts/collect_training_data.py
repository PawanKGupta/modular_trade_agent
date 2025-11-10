#!/usr/bin/env python3
"""
Collect Training Data from Backtest Results

Collects features and labels from backtest results for ML model training.
This script:
1. Loads backtest results
2. For each backtest entry, extracts features at entry points
3. Creates labels based on actual outcomes (P&L)
4. Saves training dataset

Usage:
    python scripts/collect_training_data.py --backtest-file data/backtest_training_data.csv --output data/ml_training_data.csv
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
    
    Args:
        ticker: Stock ticker
        entry_date: Entry date (YYYY-MM-DD)
        data_service: Data service instance
        indicator_service: Indicator service instance
        signal_service: Signal service instance
        verdict_service: Verdict service instance
        
    Returns:
        Dict with features or None if extraction fails
    """
    try:
        # Fetch data up to entry date
        df = data_service.fetch_single_timeframe(
            ticker=ticker,
            end_date=entry_date,
            add_current_day=False  # Don't include current day for historical analysis
        )
        
        if df is None or df.empty or len(df) < 50:
            return None
        
        # Calculate indicators
        df = indicator_service.compute_indicators(df)
        if df is None or df.empty:
            return None
        
        # Get latest row (entry date)
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
        
        return features
        
    except Exception as e:
        logger.debug(f"Failed to extract features for {ticker} at {entry_date}: {e}")
        return None


def create_labels_from_backtest_results(backtest_results: Dict) -> List[Dict]:
    """
    Create labeled training examples from backtest results
    
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
            
            # Create a safe namespace for eval (only allow numpy types and basic dict/list)
            safe_dict = {"__builtins__": {}, "dict": dict, "list": list, "np": np}
            
            # Clean up the string - replace np.float64 with float
            # The string might have np.float64(123.45) which needs to become 123.45
            cleaned = re.sub(r'np\.float64\(([^)]+)\)', r'\1', full_results_str)
            
            # Evaluate safely
            full_results = eval(cleaned, safe_dict)
            
            # Convert numpy types to Python types
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
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
            
        entry_date = position.get('entry_date')
        exit_date = position.get('exit_date')
        pnl_pct = position.get('pnl_pct', 0) or position.get('return_pct', 0)  # Try both keys
        
        if not entry_date:
            continue
        
        # Extract features at entry date
        logger.info(f"    Extracting features for position: {entry_date} (P&L: {pnl_pct:.2f}%)")
        try:
            features = extract_features_at_date(
                ticker=ticker,
                entry_date=entry_date,
                data_service=data_service,
                indicator_service=indicator_service,
                signal_service=signal_service,
                verdict_service=verdict_service
            )
            
            if not features:
                logger.warning(f"    âš ï¸ Failed to extract features for {ticker} at {entry_date}")
                continue
            
            logger.info(f"    âœ… Successfully extracted features for {ticker} at {entry_date}")
        except Exception as e:
            logger.warning(f"    âš ï¸ Error extracting features for {ticker} at {entry_date}: {e}")
            continue
        
        # Create label based on outcome
        # Good trades (>10% gain) = strong_buy
        # Decent trades (5-10% gain) = buy
        # Small gains (0-5% gain) = watch
        # Losses (<0%) = avoid
        # Handle numpy types
        pnl_pct_value = float(pnl_pct) if hasattr(pnl_pct, '__float__') else pnl_pct
        
        if pnl_pct_value >= 10:
            label = 'strong_buy'
        elif pnl_pct_value >= 5:
            label = 'buy'
        elif pnl_pct_value >= 0:
            label = 'watch'
        else:
            label = 'avoid'
        
        # Add label and outcome
        features['label'] = label
        features['actual_pnl_pct'] = pnl_pct_value
        features['exit_date'] = exit_date
        
        # ML ENHANCED OUTCOME FEATURES (Phase 4): Extract from backtest results
        features['exit_reason'] = position.get('exit_reason', 'Unknown')
        features['max_drawdown_pct'] = position.get('max_drawdown_pct', 0.0)
        
        # Calculate holding_days (backward compatible with days_to_exit)
        days_to_exit = position.get('days_to_exit')
        if days_to_exit is not None:
            features['holding_days'] = days_to_exit
        elif exit_date and entry_date:
            try:
                entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
                features['holding_days'] = (exit_dt - entry_dt).days
            except:
                features['holding_days'] = None
        else:
            features['holding_days'] = None
        
        labeled_examples.append(features)
    
    return labeled_examples


def collect_training_data(
    backtest_file: str,
    output_file: str = "data/ml_training_data.csv"
) -> pd.DataFrame:
    """
    Collect training data from backtest results
    
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
        
        try:
            # Convert row to dict (row is already a Series, can use to_dict())
            backtest_result = row.to_dict()
            
            # Create labeled examples
            labeled_examples = create_labels_from_backtest_results(backtest_result)
            
            if labeled_examples:
                all_training_data.extend(labeled_examples)
                logger.info(f"  âœ… {ticker}: Created {len(labeled_examples)} training examples")
            else:
                logger.warning(f"  âš ï¸ {ticker}: No valid training examples")
                # Debug why no examples
                import traceback
                logger.debug(f"Debug trace for {ticker}:")
                logger.debug(traceback.format_exc())
                
        except Exception as e:
            logger.error(f"  âŒ {ticker}: Failed - {e}")
            continue
    
    # Create DataFrame
    if all_training_data:
        df_training = pd.DataFrame(all_training_data)
        
        # Save to CSV
        os.makedirs(Path(output_file).parent, exist_ok=True)
        df_training.to_csv(output_file, index=False)
        
        logger.info(f"\nâœ… Training data collection complete!")
        logger.info(f"   Total examples: {len(df_training)}")
        logger.info(f"   Saved to: {output_file}")
        
        # Print label distribution
        if 'label' in df_training.columns:
            label_counts = df_training['label'].value_counts()
            logger.info(f"\nðŸ“Š Label Distribution:")
            for label, count in label_counts.items():
                logger.info(f"   {label}: {count} ({count/len(df_training)*100:.1f}%)")
    else:
        logger.warning("No training data collected")
        df_training = pd.DataFrame()
    
    return df_training


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Collect training data from backtest results')
    parser.add_argument('--backtest-file', '-b', default='data/backtest_training_data.csv',
                       help='Backtest results CSV file')
    parser.add_argument('--output', '-o', default='data/ml_training_data.csv',
                       help='Output CSV file for training data')
    
    args = parser.parse_args()
    
    if not Path(args.backtest_file).exists():
        logger.error(f"Backtest file not found: {args.backtest_file}")
        logger.info("Run bulk_backtest_all_stocks.py first to generate backtest results")
        return 1
    
    # Collect training data
    df = collect_training_data(
        backtest_file=args.backtest_file,
        output_file=args.output
    )
    
    return 0 if len(df) > 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
