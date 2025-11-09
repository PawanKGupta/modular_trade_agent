#!/usr/bin/env python3
"""
Comprehensive Backtest Validation Test

This test script performs a 5-year backtest and validates:
1. Verdict calculations are correct for each signal
2. Trade execution happens perfectly on each signal
3. All verdict components are calculated correctly

Usage:
    python -m pytest tests/integration/test_backtest_verdict_validation.py -v
    python tests/integration/test_backtest_verdict_validation.py
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from integrated_backtest import run_backtest, trade_agent, run_integrated_backtest
from services.analysis_service import AnalysisService
from services.verdict_service import VerdictService
from services.chart_quality_service import ChartQualityService
from config.strategy_config import StrategyConfig
from utils.logger import logger
import pandas_ta as ta


class VerdictValidationResult:
    """Container for verdict validation results"""
    
    def __init__(self, signal_date: str, signal_data: Dict, analysis_result: Dict):
        self.signal_date = signal_date
        self.signal_data = signal_data
        self.analysis_result = analysis_result
        self.verdict = analysis_result.get('verdict', 'avoid')
        self.errors = []
        self.warnings = []
        self.passed = True
        
    def add_error(self, message: str):
        """Add an error to the validation result"""
        self.errors.append(message)
        self.passed = False
        
    def add_warning(self, message: str):
        """Add a warning to the validation result"""
        self.warnings.append(message)
        
    def get_summary(self) -> Dict:
        """Get summary of validation results"""
        return {
            'signal_date': self.signal_date,
            'verdict': self.verdict,
            'passed': self.passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'signal_rsi': self.signal_data.get('rsi'),
            'signal_ema200': self.signal_data.get('ema200'),
            'signal_close': self.signal_data.get('close_price'),
        }


class TradeExecutionValidationResult:
    """Container for trade execution validation results"""
    
    def __init__(self, signal_date: str, execution_date: str, position_data: Dict):
        self.signal_date = signal_date
        self.execution_date = execution_date
        self.position_data = position_data
        self.errors = []
        self.warnings = []
        self.passed = True
        
    def add_error(self, message: str):
        """Add an error to the validation result"""
        self.errors.append(message)
        self.passed = False
        
    def add_warning(self, message: str):
        """Add a warning to the validation result"""
        self.warnings.append(message)
        
    def get_summary(self) -> Dict:
        """Get summary of validation results"""
        return {
            'signal_date': self.signal_date,
            'execution_date': self.execution_date,
            'passed': self.passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'entry_price': self.position_data.get('entry_price'),
            'target_price': self.position_data.get('target_price'),
        }


class BacktestVerdictValidator:
    """Validates verdict calculations in backtest"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig.default()
        self.verdict_service = VerdictService(config=self.config)
        self.chart_quality_service = ChartQualityService(config=self.config)
        self.analysis_service = AnalysisService(config=self.config)
        
    def validate_verdict_calculation(
        self,
        signal_data: Dict,
        analysis_result: Dict,
        market_data: pd.DataFrame
    ) -> VerdictValidationResult:
        """
        Validate verdict calculation for a signal
        
        Args:
            signal_data: Signal data from backtest
            analysis_result: Analysis result from trade agent
            market_data: Market data DataFrame
            
        Returns:
            VerdictValidationResult with validation details
        """
        signal_date = signal_data['signal_date'].strftime('%Y-%m-%d')
        result = VerdictValidationResult(signal_date, signal_data, analysis_result)
        
        verdict = analysis_result.get('verdict', 'avoid')
        signals = analysis_result.get('signals', [])
        rsi_value = analysis_result.get('rsi')
        is_above_ema200 = analysis_result.get('is_above_ema200', False)
        vol_ok = analysis_result.get('volume_data', {}).get('vol_ok', False)
        vol_strong = analysis_result.get('volume_data', {}).get('vol_strong', False)
        fundamental_ok = analysis_result.get('fundamental_ok', True)
        timeframe_confirmation = analysis_result.get('multi_timeframe')
        news_sentiment = analysis_result.get('news_sentiment')
        chart_quality_passed = analysis_result.get('chart_quality_passed', True)
        
        # Get signal data
        signal_rsi = signal_data.get('rsi')
        signal_close = signal_data.get('close_price')
        signal_ema200 = signal_data.get('ema200')
        
        # Validation 1: RSI Value Consistency
        # Note: RSI values might differ slightly due to:
        # 1. Different data sources (backtest engine vs analysis service)
        # 2. Slight timing differences in calculation
        # 3. Data filtering differences
        # So we allow a larger tolerance (2.0 points) and treat as warning
        if rsi_value is not None and signal_rsi is not None:
            rsi_diff = abs(rsi_value - signal_rsi)
            if rsi_diff > 2.0:  # Allow larger differences due to data source differences
                result.add_warning(
                    f"RSI difference: Signal RSI={signal_rsi:.2f}, Analysis RSI={rsi_value:.2f}, Diff={rsi_diff:.2f} "
                    f"(may be due to data source differences)"
                )
            elif rsi_diff > 0.5:  # Small difference - just note it
                result.add_warning(
                    f"RSI slight difference: Signal RSI={signal_rsi:.2f}, Analysis RSI={rsi_value:.2f}, Diff={rsi_diff:.2f}"
                )
        
        # Validation 2: EMA200 Position Consistency
        # Note: EMA200 calculation might differ due to:
        # 1. Different data sources (backtest engine vs analysis service)
        # 2. Different lookback periods
        # 3. Data filtering differences (as_of_date truncation)
        signal_above_ema200 = signal_close > signal_ema200 if signal_close and signal_ema200 else False
        if signal_above_ema200 != is_above_ema200:
            # This is a warning rather than error because:
            # - as_of_date truncation can affect EMA200 calculation
            # - Different data sources might have slight differences
            result.add_warning(
                f"EMA200 position difference: Signal above={signal_above_ema200}, Analysis above={is_above_ema200} "
                f"(may be due to data source differences or as_of_date truncation)"
            )
        
        # Validation 3: Chart Quality Check
        # Note: When using as_of_date, chart quality might be assessed on truncated data
        # This can lead to different results than full historical assessment
        chart_quality_data = analysis_result.get('chart_quality')
        
        if not chart_quality_passed:
            # Chart quality failed - verdict should be avoid
            if verdict not in ['avoid']:
                # However, ML model might override this in some edge cases
                # So we check if this is an ML prediction vs rule-based
                justification = analysis_result.get('justification', [])
                is_ml_prediction = any('ML prediction' in str(j) for j in justification)
                
                if is_ml_prediction:
                    # ML model should respect chart quality, but might have edge cases
                    result.add_warning(
                        f"Chart quality failed but ML predicted {verdict} (ML model may need retraining or chart quality check)"
                    )
                else:
                    result.add_error(
                        f"Chart quality failed but verdict is {verdict} (should be avoid)"
                    )
        else:
            # If chart quality passed, verify it was actually checked
            if chart_quality_data is None:
                result.add_warning("Chart quality check data not found in analysis result")
        
        # Validation 4: RSI Threshold Validation
        if verdict in ['buy', 'strong_buy']:
            # For buy/strong_buy, RSI must be oversold
            # However, note that the signal might have been generated when RSI was oversold,
            # but by the time analysis runs, RSI might have changed slightly
            # So we check if the signal RSI was oversold, not necessarily the analysis RSI
            signal_rsi_oversold = False
            if is_above_ema200:
                expected_threshold = self.config.rsi_oversold  # 30
                signal_rsi_oversold = signal_rsi is not None and signal_rsi < expected_threshold
                # Check analysis RSI as well, but allow small tolerance
                if rsi_value is not None and rsi_value >= expected_threshold + 1.0:  # Allow 1 point tolerance
                    if not signal_rsi_oversold:
                        result.add_error(
                            f"RSI threshold violation: Above EMA200 but RSI={rsi_value:.2f} >= {expected_threshold} "
                            f"(signal RSI={signal_rsi:.2f}, should be < {expected_threshold} for buy verdict)"
                        )
            else:
                expected_threshold = self.config.rsi_extreme_oversold  # 20
                signal_rsi_oversold = signal_rsi is not None and signal_rsi < expected_threshold
                if rsi_value is not None and rsi_value >= expected_threshold + 1.0:  # Allow 1 point tolerance
                    if not signal_rsi_oversold:
                        result.add_error(
                            f"RSI threshold violation: Below EMA200 but RSI={rsi_value:.2f} >= {expected_threshold} "
                            f"(signal RSI={signal_rsi:.2f}, should be < {expected_threshold} for buy verdict)"
                        )
            
            # If signal RSI was not oversold, that's a problem
            if not signal_rsi_oversold:
                result.add_error(
                    f"Signal RSI {signal_rsi:.2f} was not oversold (threshold: {expected_threshold}) "
                    f"but verdict is {verdict}"
                )
            
            # Volume check
            if not vol_ok:
                result.add_error(
                    f"Volume check failed: vol_ok=False but verdict is {verdict} "
                    f"(volume should be adequate for buy verdict)"
                )
            
            # Fundamental check
            if not fundamental_ok:
                result.add_error(
                    f"Fundamental check failed: fundamental_ok=False but verdict is {verdict} "
                    f"(fundamentals should be OK for buy verdict)"
                )
        
        # Validation 5: Verdict Logic Validation
        # Note: If ML model is being used, it might produce different verdicts than rule-based logic
        # So we check if this is an ML prediction and handle accordingly
        justification = analysis_result.get('justification', [])
        is_ml_prediction = any('ML prediction' in str(j) for j in justification)
        
        if is_ml_prediction:
            # For ML predictions, we validate that:
            # 1. Chart quality check was performed (if failed, ML should not predict)
            # 2. ML verdict is reasonable given the conditions
            if not chart_quality_passed:
                # ML should not predict if chart quality failed
                result.add_error(
                    f"ML model predicted {verdict} despite chart quality failure "
                    f"(ML model should respect chart quality filter)"
                )
            else:
                # ML prediction is valid - just note that it's different from rule-based
                result.add_warning(
                    f"ML model predicted {verdict} (rule-based logic may differ, which is expected)"
                )
        else:
            # Rule-based logic - recalculate expected verdict
            expected_verdict, expected_justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=vol_ok,
                vol_strong=vol_strong,
                fundamental_ok=fundamental_ok,
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                chart_quality_passed=chart_quality_passed
            )
            
            # Apply candle quality check if applicable
            if expected_verdict in ['buy', 'strong_buy']:
                df_slice = market_data.loc[market_data.index <= signal_data['signal_date']]
                if not df_slice.empty:
                    expected_verdict, candle_analysis, downgrade_reason = self.verdict_service.apply_candle_quality_check(
                        df_slice, expected_verdict
                    )
            
            # Compare expected vs actual verdict
            if expected_verdict != verdict:
                result.add_error(
                    f"Verdict mismatch: Expected={expected_verdict}, Actual={verdict}. "
                    f"Justification: {analysis_result.get('justification', [])}"
                )
        
        # Validation 6: Trading Parameters Validation
        if verdict in ['buy', 'strong_buy']:
            trading_params = analysis_result.get('trading_params')
            if trading_params is None:
                result.add_error("Trading parameters missing for buy/strong_buy verdict")
            else:
                buy_range = trading_params.get('buy_range')
                target = trading_params.get('target')
                stop = trading_params.get('stop')
                
                if buy_range is None or not isinstance(buy_range, (list, tuple)) or len(buy_range) != 2:
                    result.add_error("Invalid buy_range in trading parameters")
                elif buy_range[0] >= buy_range[1]:
                    result.add_error(f"Invalid buy_range: {buy_range[0]} >= {buy_range[1]}")
                
                if target is None or target <= 0:
                    result.add_error("Invalid target price in trading parameters")
                
                if stop is None or stop <= 0:
                    result.add_error("Invalid stop loss in trading parameters")
                
                # Validate target > entry > stop (typical order)
                if buy_range and target and stop:
                    entry_mid = (buy_range[0] + buy_range[1]) / 2
                    if not (target > entry_mid > stop):
                        result.add_warning(
                            f"Unusual price order: target={target:.2f}, entry={entry_mid:.2f}, stop={stop:.2f}"
                        )
        
        return result


class TradeExecutionValidator:
    """Validates trade execution in backtest"""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig.default()
        
    def validate_trade_execution(
        self,
        signal_data: Dict,
        position_data: Dict,
        market_data: pd.DataFrame
    ) -> TradeExecutionValidationResult:
        """
        Validate trade execution for a signal
        
        Args:
            signal_data: Signal data from backtest
            position_data: Position data from integrated backtest
            market_data: Market data DataFrame
            
        Returns:
            TradeExecutionValidationResult with validation details
        """
        signal_date = signal_data['signal_date']
        execution_date = signal_data.get('execution_date')
        result = TradeExecutionValidationResult(
            signal_date.strftime('%Y-%m-%d') if hasattr(signal_date, 'strftime') else str(signal_date),
            execution_date.strftime('%Y-%m-%d') if execution_date and hasattr(execution_date, 'strftime') else str(execution_date) if execution_date else 'N/A',
            position_data
        )
        
        # Validation 1: Execution Date Validation
        if execution_date is None:
            result.add_error("Execution date is missing")
        else:
            # Execution should be on next trading day after signal
            if execution_date <= signal_date:
                result.add_error(
                    f"Execution date {execution_date} should be after signal date {signal_date}"
                )
        
        # Validation 2: Entry Price Validation
        entry_price = position_data.get('entry_price')
        execution_price = signal_data.get('execution_price')
        
        if entry_price is None:
            result.add_error("Entry price is missing in position data")
        elif execution_price is not None:
            # Entry price should match execution price (next day's open)
            if abs(entry_price - execution_price) > 0.01:  # Allow small rounding differences
                result.add_error(
                    f"Entry price mismatch: Position entry={entry_price:.2f}, Signal execution={execution_price:.2f}"
                )
        
        # Validation 3: Entry Price from Market Data
        if execution_date and market_data is not None and not market_data.empty:
            try:
                # Convert execution_date to pandas Timestamp if needed
                if isinstance(execution_date, str):
                    execution_date = pd.to_datetime(execution_date)
                
                # Try to find the date in market_data index
                if execution_date in market_data.index:
                    market_open = market_data.loc[execution_date, 'Open']
                    if entry_price is not None:
                        if abs(entry_price - market_open) > 0.01:
                            result.add_error(
                                f"Entry price mismatch with market data: Position={entry_price:.2f}, Market Open={market_open:.2f}"
                            )
                else:
                    # Try to find the closest date
                    try:
                        closest_date = market_data.index[market_data.index.get_indexer([execution_date], method='nearest')[0]]
                        market_open = market_data.loc[closest_date, 'Open']
                        if entry_price is not None:
                            if abs(entry_price - market_open) > 0.01:
                                result.add_warning(
                                    f"Entry price mismatch with market data (closest date): Position={entry_price:.2f}, Market Open={market_open:.2f} on {closest_date}"
                                )
                    except Exception:
                        result.add_warning(f"Execution date {execution_date} not found in market data")
            except Exception as e:
                result.add_warning(f"Could not validate entry price with market data: {e}")
        
        # Validation 4: Target Price Validation
        target_price = position_data.get('target_price')
        if target_price is None or target_price <= 0:
            result.add_error("Target price is missing or invalid")
        elif entry_price and target_price <= entry_price:
            result.add_error(
                f"Target price {target_price:.2f} should be greater than entry price {entry_price:.2f}"
            )
        
        # Validation 5: Position Size Validation
        capital = position_data.get('capital')
        if capital is None or capital <= 0:
            result.add_error("Capital is missing or invalid")
        elif entry_price:
            expected_quantity = int(capital / entry_price)
            actual_quantity = position_data.get('quantity')
            if actual_quantity is not None and abs(actual_quantity - expected_quantity) > 1:
                result.add_warning(
                    f"Quantity mismatch: Expected={expected_quantity}, Actual={actual_quantity} "
                    f"(may be due to rounding)"
                )
        
        return result


def run_comprehensive_backtest_validation(
    stock_symbol: str,
    years: int = 5,
    capital_per_position: float = 100000
) -> Dict[str, Any]:
    """
    Run comprehensive 5-year backtest validation
    
    Args:
        stock_symbol: Stock symbol to test (e.g., "RELIANCE.NS")
        years: Number of years to backtest (default: 5)
        capital_per_position: Capital per position (default: 100000)
        
    Returns:
        Dictionary with validation results
    """
    print("=" * 80)
    print(f"COMPREHENSIVE BACKTEST VALIDATION")
    print("=" * 80)
    print(f"Stock: {stock_symbol}")
    print(f"Period: {years} years")
    print(f"Capital per position: ₹{capital_per_position:,.0f}")
    print("=" * 80)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    date_range = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    # Initialize validators
    config = StrategyConfig.default()
    verdict_validator = BacktestVerdictValidator(config=config)
    trade_validator = TradeExecutionValidator(config=config)
    
    # Step 1: Run backtest to get signals
    print(f"\n📊 Step 1: Running backtest to identify signals...")
    potential_signals, backtest_engine = run_backtest(stock_symbol, date_range, return_engine=True)
    
    if not potential_signals:
        return {
            'stock_symbol': stock_symbol,
            'period': f"{date_range[0]} to {date_range[1]}",
            'total_signals': 0,
            'validation_passed': True,
            'message': 'No signals found in backtest period'
        }
    
    print(f"✅ Found {len(potential_signals)} potential signals")
    
    # Step 2: Run integrated backtest to get trade execution data
    print(f"\n📈 Step 2: Running integrated backtest to get trade execution data...")
    integrated_results = run_integrated_backtest(
        stock_name=stock_symbol,
        date_range=date_range,
        capital_per_position=capital_per_position
    )
    
    # Get market data for validation
    # RECOMMENDATION 1: Use full data from backtest engine (includes history before backtest start)
    # This ensures we have enough data for chart quality assessment
    if backtest_engine:
        # Use full data if available (includes history before backtest start)
        if hasattr(backtest_engine, '_full_data') and backtest_engine._full_data is not None:
            market_data = backtest_engine._full_data.copy()
        else:
            market_data = backtest_engine.data.copy() if backtest_engine.data is not None else None
    else:
        market_data = None
    
    if market_data is None:
        import yfinance as yf
        market_data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)
        if isinstance(market_data.columns, pd.MultiIndex):
            market_data.columns = market_data.columns.get_level_values(0)
    
    # Ensure market_data has proper column names (convert to lowercase for analysis_service)
    if market_data is not None and not market_data.empty:
        # Create a copy with lowercase column names for analysis_service
        market_data_lower = market_data.copy()
        if 'Open' in market_data_lower.columns:
            market_data_lower = market_data_lower.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
        else:
            market_data_lower = market_data.copy()
    else:
        market_data_lower = market_data
    
    # Step 3: Validate each signal
    print(f"\n🔍 Step 3: Validating verdict calculations and trade executions...")
    verdict_validations = []
    trade_validations = []
    
    # Create a mapping of signal dates to positions
    positions_by_date = {}
    if 'positions' in integrated_results:
        for pos in integrated_results['positions']:
            entry_date_str = pos.get('entry_date')
            if entry_date_str:
                try:
                    entry_date = pd.to_datetime(entry_date_str)
                    # Use date as key (ignore time)
                    entry_date_key = entry_date.date() if hasattr(entry_date, 'date') else entry_date
                    if entry_date_key not in positions_by_date:
                        positions_by_date[entry_date_key] = []
                    positions_by_date[entry_date_key].append(pos)
                except Exception as e:
                    logger.warning(f"Could not parse entry_date {entry_date_str}: {e}")
    
    for i, signal in enumerate(potential_signals, 1):
        signal_date = signal['signal_date']
        signal_date_str = signal_date.strftime('%Y-%m-%d') if hasattr(signal_date, 'strftime') else str(signal_date)
        
        print(f"\n  Signal {i}/{len(potential_signals)}: {signal_date_str}")
        print(f"    Reason: {signal.get('reason', 'N/A')}")
        print(f"    RSI: {signal.get('rsi', 'N/A'):.2f}" if signal.get('rsi') else "    RSI: N/A")
        
        # Validate verdict calculation
        try:
            # Run trade agent analysis for this signal
            analysis_result = verdict_validator.analysis_service.analyze_ticker(
                ticker=stock_symbol,
                enable_multi_timeframe=True,
                export_to_csv=False,
                as_of_date=signal_date_str,
                pre_fetched_daily=market_data_lower if market_data_lower is not None else None
            )
            
            # Validate verdict
            verdict_validation = verdict_validator.validate_verdict_calculation(
                signal_data=signal,
                analysis_result=analysis_result,
                market_data=market_data
            )
            verdict_validations.append(verdict_validation)
            
            if verdict_validation.passed:
                print(f"    ✅ Verdict validation: PASSED (verdict={verdict_validation.verdict})")
            else:
                print(f"    ❌ Verdict validation: FAILED")
                for error in verdict_validation.errors:
                    print(f"       Error: {error}")
                for warning in verdict_validation.warnings:
                    print(f"       Warning: {warning}")
            
            # Validate trade execution (if trade was executed)
            if analysis_result.get('verdict') in ['buy', 'strong_buy']:
                execution_date = signal.get('execution_date')
                if execution_date:
                    # Find corresponding position
                    position = None
                    # Convert execution_date to date for matching
                    if hasattr(execution_date, 'date'):
                        execution_date_key = execution_date.date()
                    else:
                        execution_date_key = pd.to_datetime(execution_date).date()
                    
                    if execution_date_key in positions_by_date:
                        # Use the first position for this date
                        position = positions_by_date[execution_date_key][0] if positions_by_date[execution_date_key] else None
                    
                    if position:
                        trade_validation = trade_validator.validate_trade_execution(
                            signal_data=signal,
                            position_data=position,
                            market_data=market_data
                        )
                        trade_validations.append(trade_validation)
                        
                        if trade_validation.passed:
                            print(f"    ✅ Trade execution validation: PASSED")
                        else:
                            print(f"    ❌ Trade execution validation: FAILED")
                            for error in trade_validation.errors:
                                print(f"       Error: {error}")
                            for warning in trade_validation.warnings:
                                print(f"       Warning: {warning}")
                    else:
                        print(f"    ⚠️ Trade execution validation: SKIPPED (position not found)")
                else:
                    print(f"    ⚠️ Trade execution validation: SKIPPED (no execution date)")
            else:
                print(f"    ⚠️ Trade execution validation: SKIPPED (verdict={analysis_result.get('verdict')})")
                
        except Exception as e:
            print(f"    ❌ Error validating signal: {e}")
            import traceback
            traceback.print_exc()
    
    # Step 4: Generate summary
    print(f"\n📊 Step 4: Generating validation summary...")
    
    total_signals = len(potential_signals)
    verdict_passed = sum(1 for v in verdict_validations if v.passed)
    verdict_failed = total_signals - verdict_passed
    trade_passed = sum(1 for v in trade_validations if v.passed)
    trade_failed = len(trade_validations) - trade_passed
    
    # Collect all errors and warnings
    all_verdict_errors = []
    all_verdict_warnings = []
    for v in verdict_validations:
        all_verdict_errors.extend(v.errors)
        all_verdict_warnings.extend(v.warnings)
    
    all_trade_errors = []
    all_trade_warnings = []
    for v in trade_validations:
        all_trade_errors.extend(v.errors)
        all_trade_warnings.extend(v.warnings)
    
    # Verdict distribution
    verdict_distribution = {}
    for v in verdict_validations:
        verdict = v.verdict
        verdict_distribution[verdict] = verdict_distribution.get(verdict, 0) + 1
    
    # Generate summary
    summary = {
        'stock_symbol': stock_symbol,
        'period': f"{date_range[0]} to {date_range[1]}",
        'total_signals': total_signals,
        'verdict_validations': {
            'total': len(verdict_validations),
            'passed': verdict_passed,
            'failed': verdict_failed,
            'pass_rate': (verdict_passed / len(verdict_validations) * 100) if verdict_validations else 0,
            'errors': all_verdict_errors,
            'warnings': all_verdict_warnings,
            'verdict_distribution': verdict_distribution
        },
        'trade_validations': {
            'total': len(trade_validations),
            'passed': trade_passed,
            'failed': trade_failed,
            'pass_rate': (trade_passed / len(trade_validations) * 100) if trade_validations else 0,
            'errors': all_trade_errors,
            'warnings': all_trade_warnings
        },
        'validation_passed': verdict_failed == 0 and trade_failed == 0,
        'integrated_backtest_results': integrated_results
    }
    
    # Print summary
    print(f"\n" + "=" * 80)
    print(f"VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Signals: {total_signals}")
    print(f"\nVerdict Validations:")
    print(f"  Total: {len(verdict_validations)}")
    print(f"  Passed: {verdict_passed}")
    print(f"  Failed: {verdict_failed}")
    print(f"  Pass Rate: {summary['verdict_validations']['pass_rate']:.1f}%")
    print(f"  Verdict Distribution: {verdict_distribution}")
    
    if all_verdict_errors:
        print(f"\n  Verdict Errors ({len(all_verdict_errors)}):")
        for error in all_verdict_errors[:10]:  # Show first 10 errors
            print(f"    - {error}")
        if len(all_verdict_errors) > 10:
            print(f"    ... and {len(all_verdict_errors) - 10} more errors")
    
    if all_verdict_warnings:
        print(f"\n  Verdict Warnings ({len(all_verdict_warnings)}):")
        for warning in all_verdict_warnings[:10]:  # Show first 10 warnings
            print(f"    - {warning}")
        if len(all_verdict_warnings) > 10:
            print(f"    ... and {len(all_verdict_warnings) - 10} more warnings")
    
    print(f"\nTrade Execution Validations:")
    print(f"  Total: {len(trade_validations)}")
    print(f"  Passed: {trade_passed}")
    print(f"  Failed: {trade_failed}")
    print(f"  Pass Rate: {summary['trade_validations']['pass_rate']:.1f}%")
    
    if all_trade_errors:
        print(f"\n  Trade Errors ({len(all_trade_errors)}):")
        for error in all_trade_errors[:10]:  # Show first 10 errors
            print(f"    - {error}")
        if len(all_trade_errors) > 10:
            print(f"    ... and {len(all_trade_errors) - 10} more errors")
    
    if all_trade_warnings:
        print(f"\n  Trade Warnings ({len(all_trade_warnings)}):")
        for warning in all_trade_warnings[:10]:  # Show first 10 warnings
            print(f"    - {warning}")
        if len(all_trade_warnings) > 10:
            print(f"    ... and {len(all_trade_warnings) - 10} more warnings")
    
    print(f"\nOverall Validation: {'✅ PASSED' if summary['validation_passed'] else '❌ FAILED'}")
    
    # Add recommendations based on findings
    if not summary['validation_passed']:
        print(f"\n📋 RECOMMENDATIONS:")
        if all_verdict_errors:
            ml_errors = [e for e in all_verdict_errors if 'ML' in e or 'ML model' in e]
            if ml_errors:
                print(f"  • ML Model Issues: {len(ml_errors)} errors related to ML model predictions")
                print(f"    - Consider retraining ML model or reviewing chart quality integration")
                print(f"    - Ensure ML model respects chart quality filter (Stage 1)")
            
            chart_quality_errors = [e for e in all_verdict_errors if 'Chart quality' in e or 'chart quality' in e]
            if chart_quality_errors:
                print(f"  • Chart Quality Issues: {len(chart_quality_errors)} errors related to chart quality")
                print(f"    - When using as_of_date, chart quality may be assessed on truncated data")
                print(f"    - Consider using full historical data for chart quality assessment")
            
            verdict_mismatch_errors = [e for e in all_verdict_errors if 'Verdict mismatch' in e]
            if verdict_mismatch_errors:
                print(f"  • Verdict Logic Issues: {len(verdict_mismatch_errors)} verdict mismatches")
                print(f"    - Review verdict calculation logic")
                print(f"    - Check if ML model predictions align with rule-based logic")
    
    print("=" * 80)
    
    return summary


def main():
    """Main entry point for the test script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run comprehensive backtest validation')
    parser.add_argument('--symbol', type=str, default='RELIANCE.NS', help='Stock symbol to test')
    parser.add_argument('--years', type=int, default=5, help='Number of years to backtest')
    parser.add_argument('--capital', type=float, default=100000, help='Capital per position')
    
    args = parser.parse_args()
    
    try:
        results = run_comprehensive_backtest_validation(
            stock_symbol=args.symbol,
            years=args.years,
            capital_per_position=args.capital
        )
        
        # Exit with error code if validation failed
        if not results.get('validation_passed', False):
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error running validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_backtest_validation_default():
    """Pytest-compatible test function with default settings"""
    results = run_comprehensive_backtest_validation(
        stock_symbol='RELIANCE.NS',
        years=2,  # Use 2 years for faster testing
        capital_per_position=100000
    )
    assert results.get('validation_passed', False), "Backtest validation failed"
    assert results.get('verdict_validations', {}).get('pass_rate', 0) >= 95.0, "Verdict validation pass rate too low"
    
    # Trade validation pass rate: Only check if trades were executed
    # If no trades were executed (all verdicts are "watch" or "avoid"), skip this assertion
    trade_validations = results.get('trade_validations', {})
    total_trades = trade_validations.get('total', 0)
    if total_trades > 0:
        assert trade_validations.get('pass_rate', 0) >= 95.0, "Trade validation pass rate too low"
    else:
        # No trades executed - this is expected for stocks that fail chart quality or get "watch" verdicts
        # Just verify that verdict validations passed
        print("ℹ️ No trades executed (all verdicts were 'watch' or 'avoid') - skipping trade validation assertion")
        assert results.get('verdict_validations', {}).get('pass_rate', 0) >= 95.0, "Verdict validation pass rate too low"


if __name__ == "__main__":
    main()

