"""
Data Validation Module

Validates data quality and detects potential issues with volume and price data.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.logger import logger


def validate_volume_data(df: pd.DataFrame, ticker: str) -> Dict[str, any]:
    """
    Validate volume data quality and detect potential issues

    Args:
        df: DataFrame with OHLCV data
        ticker: Stock ticker symbol

    Returns:
        Dict with validation results
    """
    validation_result = {
        "ticker": ticker,
        "is_valid": True,
        "warnings": [],
        "errors": [],
        "data_quality_score": 0,  # 0-100 score
        "latest_date": None,
        "data_age_days": None,
        "volume_issues": [],
    }

    try:
        if df is None or df.empty:
            validation_result["is_valid"] = False
            validation_result["errors"].append("No data available")
            return validation_result

        # Check required columns
        required_cols = ["date", "volume", "close", "open", "high", "low"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Missing required columns: {missing_cols}")
            return validation_result

        # Date validation
        latest_date = pd.to_datetime(df["date"].iloc[-1]).date()
        validation_result["latest_date"] = latest_date.strftime("%Y-%m-%d")

        today = datetime.now().date()
        data_age = (today - latest_date).days
        validation_result["data_age_days"] = data_age

        # Check data freshness
        if data_age > 0:
            validation_result["warnings"].append(
                f"Data is {data_age} day(s) old (latest: {latest_date})"
            )
            if data_age > 2:
                validation_result["volume_issues"].append(f"Stale data: {data_age} days old")

        # Volume-specific validation
        volumes = df["volume"].dropna()
        if volumes.empty:
            validation_result["is_valid"] = False
            validation_result["errors"].append("No volume data available")
            return validation_result

        # Check for zero or negative volumes
        zero_volumes = (volumes <= 0).sum()
        if zero_volumes > 0:
            validation_result["warnings"].append(f"{zero_volumes} days with zero/negative volume")
            validation_result["volume_issues"].append(
                f"Zero/negative volumes: {zero_volumes} occurrences"
            )

        # Check for suspiciously low volumes (compared to median)
        median_volume = volumes.median()
        recent_volume = volumes.iloc[-1]

        if recent_volume < median_volume * 0.01:  # Less than 1% of median
            validation_result["volume_issues"].append(
                f"Extremely low recent volume: {recent_volume:,.0f} vs median {median_volume:,.0f}"
            )

        # Check volume pattern consistency
        volume_std = volumes.std()
        volume_mean = volumes.mean()
        cv = volume_std / volume_mean if volume_mean > 0 else 0  # Coefficient of variation

        if cv > 3.0:  # Very high volatility in volume
            validation_result["warnings"].append(f"Highly volatile volume pattern (CV: {cv:.2f})")

        # Price validation for context
        prices = df["close"].dropna()
        if not prices.empty:
            recent_price = prices.iloc[-1]
            if recent_price <= 0:
                validation_result["errors"].append("Invalid price data (zero or negative)")

            # Check for extreme price movements that might indicate data issues
            if len(prices) > 1:
                price_change = abs(recent_price - prices.iloc[-2]) / prices.iloc[-2]
                if price_change > 0.2:  # 20% single-day change
                    validation_result["warnings"].append(
                        f"Large price movement: {price_change:.1%} - verify data accuracy"
                    )

        # Calculate data quality score
        score = 100
        score -= min(data_age * 10, 30)  # Reduce score for old data
        score -= len(validation_result["warnings"]) * 5
        score -= len(validation_result["errors"]) * 20
        score -= len(validation_result["volume_issues"]) * 10

        validation_result["data_quality_score"] = max(0, score)

        # Final validation status
        if validation_result["errors"] or data_age > 3:
            validation_result["is_valid"] = False

        return validation_result

    except Exception as e:
        validation_result["is_valid"] = False
        validation_result["errors"].append(f"Validation error: {str(e)}")
        return validation_result


def validate_batch_data(data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
    """
    Validate data for multiple tickers

    Args:
        data_dict: Dict mapping ticker -> DataFrame

    Returns:
        Dict mapping ticker -> validation_result
    """
    results = {}

    for ticker, df in data_dict.items():
        try:
            results[ticker] = validate_volume_data(df, ticker)
        except Exception as e:
            logger.error(f"Error validating data for {ticker}: {e}")
            results[ticker] = {
                "ticker": ticker,
                "is_valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "data_quality_score": 0,
            }

    return results


def get_data_quality_summary(validation_results: Dict[str, Dict]) -> Dict[str, any]:
    """
    Get summary of data quality across multiple stocks

    Args:
        validation_results: Results from validate_batch_data

    Returns:
        Summary statistics
    """
    if not validation_results:
        return {"total_stocks": 0, "valid_stocks": 0, "avg_quality_score": 0}

    total_stocks = len(validation_results)
    valid_stocks = sum(1 for r in validation_results.values() if r["is_valid"])

    quality_scores = [r.get("data_quality_score", 0) for r in validation_results.values()]
    avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    # Count common issues
    stale_data_count = sum(1 for r in validation_results.values() if r.get("data_age_days", 0) > 0)

    volume_issues_count = sum(1 for r in validation_results.values() if r.get("volume_issues"))

    return {
        "total_stocks": total_stocks,
        "valid_stocks": valid_stocks,
        "invalid_stocks": total_stocks - valid_stocks,
        "avg_quality_score": round(avg_quality_score, 1),
        "stale_data_count": stale_data_count,
        "volume_issues_count": volume_issues_count,
        "validation_success_rate": (
            round(valid_stocks / total_stocks * 100, 1) if total_stocks > 0 else 0
        ),
    }


def recommend_data_actions(validation_result: Dict) -> List[str]:
    """
    Recommend actions based on data validation results

    Args:
        validation_result: Result from validate_volume_data

    Returns:
        List of recommended actions
    """
    recommendations = []

    if not validation_result.get("is_valid", False):
        recommendations.append("[WARN]?  Data validation failed - avoid trading this stock")

    data_age = validation_result.get("data_age_days", 0)
    if data_age > 0:
        if data_age == 1:
            recommendations.append("? Data is 1 day old - use with caution for intraday analysis")
        elif data_age > 1:
            recommendations.append(f"? Data is {data_age} days old - find alternative data source")

    volume_issues = validation_result.get("volume_issues", [])
    if volume_issues:
        recommendations.append("? Volume data issues detected - verify with external source")

    quality_score = validation_result.get("data_quality_score", 0)
    if quality_score < 70:
        recommendations.append(
            f"? Low data quality score ({quality_score}/100) - use alternative data"
        )
    elif quality_score < 85:
        recommendations.append(
            f"? Moderate data quality ({quality_score}/100) - proceed with caution"
        )

    if not recommendations:
        recommendations.append("? Data quality looks good - proceed with analysis")

    return recommendations
