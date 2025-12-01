"""
Example Usage of New Architecture

This file demonstrates how to use the new use case architecture.
"""

from datetime import datetime
from .analyze_stock import AnalyzeStockUseCase
from .bulk_analyze import BulkAnalyzeUseCase
from .send_alerts import SendAlertsUseCase
from ..dto.analysis_request import AnalysisRequest, BulkAnalysisRequest
from ..services.scoring_service import ScoringService
from ..services.filtering_service import FilteringService


def example_single_stock_analysis():
    """Example: Analyze a single stock"""

    # Create use case
    use_case = AnalyzeStockUseCase()

    # Create request
    request = AnalysisRequest(
        ticker="RELIANCE.NS",
        enable_multi_timeframe=True,
        enable_backtest=False,
        export_to_csv=False,
    )

    # Execute
    response = use_case.execute(request)

    # Check result
    if response.is_success():
        print(f"[OK] {response.ticker}: {response.verdict}")
        print(f"  Price: {response.last_close}")
        print(f"  RSI: {response.rsi}")
        print(f"  Priority Score: {response.priority_score}")
    else:
        print(f"[FAIL] {response.ticker}: {response.error_message}")

    return response


def example_bulk_analysis():
    """Example: Analyze multiple stocks"""

    # Create use case
    use_case = BulkAnalyzeUseCase()

    # Create request
    request = BulkAnalysisRequest(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
        enable_multi_timeframe=True,
        enable_backtest=False,
        min_combined_score=25.0,
    )

    # Execute
    response = use_case.execute(request)

    # Check results
    print(f"Analyzed {response.total_analyzed} stocks:")
    print(f"  Successful: {response.successful}")
    print(f"  Failed: {response.failed}")
    print(f"  Buyable: {response.buyable_count}")
    print(f"  Time: {response.execution_time_seconds:.2f}s")

    # Get buy candidates
    buy_candidates = response.get_buy_candidates()
    print(f"\nBuy candidates: {len(buy_candidates)}")
    for stock in buy_candidates:
        print(f"  - {stock.ticker}: {stock.verdict} (Score: {stock.priority_score:.0f})")

    return response


def example_with_alerts():
    """Example: Analyze stocks and send alerts"""

    # Create use cases
    bulk_analyze = BulkAnalyzeUseCase()
    send_alerts = SendAlertsUseCase()

    # Analyze stocks
    request = BulkAnalysisRequest(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFC.NS"], enable_multi_timeframe=True
    )

    response = bulk_analyze.execute(request)

    # Send alerts
    if response.buyable_count > 0:
        success = send_alerts.execute(response)
        if success:
            print(f"[OK] Alerts sent for {response.buyable_count} stocks")
        else:
            print("[FAIL] Failed to send alerts")
    else:
        print("No buy candidates found")

    return response


def example_with_custom_services():
    """Example: Use cases with custom service configuration"""

    # Create services
    scoring_service = ScoringService()
    filtering_service = FilteringService(min_combined_score=30.0)

    # Create use cases with custom services
    analyze_stock = AnalyzeStockUseCase(scoring_service=scoring_service)
    bulk_analyze = BulkAnalyzeUseCase(
        analyze_stock_use_case=analyze_stock,
        scoring_service=scoring_service,
        filtering_service=filtering_service,
    )

    # Use them
    request = BulkAnalysisRequest(tickers=["RELIANCE.NS", "TCS.NS"], min_combined_score=30.0)

    response = bulk_analyze.execute(request)
    print(f"Analyzed with custom services: {response.buyable_count} buyable")

    return response


if __name__ == "__main__":
    print("=== Single Stock Analysis ===")
    example_single_stock_analysis()

    print("\n=== Bulk Analysis ===")
    example_bulk_analysis()

    print("\n=== With Alerts ===")
    example_with_alerts()

    print("\n=== Custom Services ===")
    example_with_custom_services()
