"""
Async Analysis Service

Provides async versions of analysis operations for parallel processing.
Expected to reduce analysis time by 80% for batch operations.
"""

import asyncio
from typing import Any

from config.strategy_config import StrategyConfig
from core.csv_exporter import CSVExporter
from services.analysis_service import AnalysisService
from services.async_data_service import AsyncDataService
from services.cache_service import CacheService
from src.infrastructure.db.timezone_utils import ist_now_naive
from utils.logger import logger


class AsyncAnalysisService:
    """
    Async version of AnalysisService for parallel stock analysis

    Provides async methods that can analyze multiple stocks concurrently,
    significantly reducing total analysis time.

    Expected improvement: 80% reduction in analysis time
    (25min -> 5min for 50 stocks)
    """

    def __init__(
        self,
        analysis_service: AnalysisService | None = None,
        async_data_service: AsyncDataService | None = None,
        cache_service: CacheService | None = None,
        max_concurrent: int = 10,
        config: StrategyConfig | None = None,
    ):
        """
        Initialize async analysis service

        Args:
            analysis_service: Underlying AnalysisService (creates default if None)
            async_data_service: AsyncDataService for parallel fetching (default if None)
            cache_service: CacheService for caching (creates default if None)
            max_concurrent: Maximum concurrent analyses
            config: Strategy configuration (uses default if None)
        """
        self.config = config or StrategyConfig.default()
        # Debug logging to trace config
        logger.debug(
            "AsyncAnalysisService init: ml_enabled=%s, config type=%s",
            self.config.ml_enabled,
            type(self.config),
        )
        self.analysis_service = analysis_service or AnalysisService(config=self.config)
        self.cache_service = cache_service or CacheService()
        self.async_data_service = async_data_service or AsyncDataService(
            cache_service=self.cache_service, max_concurrent=max_concurrent
        )
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_ticker_async(
        self,
        ticker: str,
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        csv_exporter: CSVExporter | None = None,
        as_of_date: str | None = None,
        news_profile: str | None = None,
    ) -> dict[str, Any]:
        """
        Async analyze a single ticker

        This method runs the analysis in an executor to avoid blocking,
        but can be used with asyncio.gather() for parallel processing.

        Args:
            ticker: Stock ticker symbol
            enable_multi_timeframe: Enable multi-timeframe analysis
            export_to_csv: Export results to CSV
            csv_exporter: CSV exporter instance
            as_of_date: Date for analysis (YYYY-MM-DD format)

        Returns:
            Dict with analysis results
        """
        async with self.semaphore:
            loop = asyncio.get_event_loop()

            try:
                from src.application.services.ohlcv_bulk_ops import (  # noqa: PLC0415
                    record_analysis_yahoo_calls,
                    reset_symbol_yahoo_counter,
                )

                reset_symbol_yahoo_counter()
                # Run blocking analysis in executor (kwargs not supported by run_in_executor)
                def _run_analysis() -> dict:
                    return self.analysis_service.analyze_ticker(
                        ticker=ticker,
                        enable_multi_timeframe=enable_multi_timeframe,
                        export_to_csv=export_to_csv,
                        csv_exporter=csv_exporter,
                        as_of_date=as_of_date,
                        news_profile=news_profile,
                    )

                result = await loop.run_in_executor(None, _run_analysis)

                record_analysis_yahoo_calls(result)
                logger.debug(
                    f"Async analysis completed for {ticker}: {result.get('verdict', 'unknown')}"
                )
                return result
            except Exception as e:
                logger.error(f"Error in async analysis for {ticker}: {e}")
                return {"ticker": ticker, "status": "analysis_error", "error": str(e)}

    async def analyze_batch_async(
        self,
        tickers: list[str],
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        as_of_date: str | None = None,
        news_profile: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Analyze multiple tickers in parallel

        This method analyzes all tickers concurrently, significantly
        reducing total analysis time.

        Args:
            tickers: List of ticker symbols
            enable_multi_timeframe: Enable multi-timeframe analysis
            export_to_csv: Export results to CSV
            as_of_date: Date for analysis (YYYY-MM-DD format)
            news_profile: News API profile (defaults to ``NEWS_UNIVERSE_PROFILE`` / ``cheap``)

        Returns:
            List of analysis results
        """
        import os

        if news_profile is None:
            news_profile = os.getenv("NEWS_UNIVERSE_PROFILE", "cheap").strip().lower() or "cheap"

        start_time = ist_now_naive()
        logger.info(
            f"Starting async batch analysis for {len(tickers)} tickers "
            f"(max {self.max_concurrent} concurrent)"
        )

        # Create CSV exporter if needed
        csv_exporter = CSVExporter() if export_to_csv else None

        # Create analysis tasks
        tasks = [
            self.analyze_ticker_async(
                ticker=ticker,
                enable_multi_timeframe=enable_multi_timeframe,
                export_to_csv=False,  # We'll handle bulk export separately
                csv_exporter=None,
                as_of_date=as_of_date,
                news_profile=news_profile,
            )
            for ticker in tickers
        ]

        # Run all analyses concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle exceptions
        processed_results = []
        for ticker, result in zip(tickers, results, strict=True):
            if isinstance(result, Exception):
                logger.error(f"Exception in async analysis for {ticker}: {result}")
                processed_results.append(
                    {"ticker": ticker, "status": "analysis_error", "error": str(result)}
                )
            else:
                processed_results.append(result)

                # Append to master CSV if requested
                if csv_exporter and result.get("status") == "success":
                    csv_exporter.append_to_master_csv(result)

        # Export bulk results to single CSV if requested
        if export_to_csv and csv_exporter:
            csv_filepath = csv_exporter.export_multiple_stocks(processed_results)
            logger.info(f"Batch analysis results exported to: {csv_filepath}")

        # Calculate statistics
        end_time = ist_now_naive()
        duration = (end_time - start_time).total_seconds()

        successful = sum(1 for r in processed_results if r.get("status") == "success")
        buyable = sum(1 for r in processed_results if r.get("verdict") in ["buy", "strong_buy"])

        logger.info(
            f"Async batch analysis complete: {successful}/{len(tickers)} successful, "
            f"{buyable} buyable, took {duration:.2f}s "
            f"({duration / len(tickers):.2f}s per ticker on average)"
        )

        return processed_results

    async def analyze_batch_with_data_prefetch(
        self,
        tickers: list[str],
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        as_of_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Analyze multiple tickers with data prefetching

        This method first fetches all data in parallel, then analyzes
        stocks sequentially (but data is already cached).

        This can be faster for very large batches where data fetching
        is the bottleneck.

        Args:
            tickers: List of ticker symbols
            enable_multi_timeframe: Enable multi-timeframe analysis
            export_to_csv: Export results to CSV
            as_of_date: Date for analysis (YYYY-MM-DD format)

        Returns:
            List of analysis results
        """
        start_time = ist_now_naive()
        logger.info(
            f"Starting prefetch batch analysis for {len(tickers)} tickers "
            f"(prefetching data, then analyzing)"
        )

        # Step 1: Prefetch all data in parallel
        logger.info("Step 1: Prefetching data...")
        data_map = await self.async_data_service.fetch_batch_async(
            tickers=tickers,
            enable_multi_timeframe=enable_multi_timeframe,
            end_date=as_of_date,
            add_current_day=as_of_date is None,
        )

        prefetch_time = ist_now_naive()
        prefetch_duration = (prefetch_time - start_time).total_seconds()
        successful_prefetch = sum(1 for v in data_map.values() if v is not None)
        logger.info(
            f"Prefetch complete: {successful_prefetch}/{len(tickers)} successful, "
            f"took {prefetch_duration:.2f}s"
        )

        # Step 2: Analyze stocks (data is already cached)
        logger.info("Step 2: Analyzing stocks with cached data...")
        csv_exporter = CSVExporter() if export_to_csv else None
        results = []

        for i, ticker in enumerate(tickers, 1):
            if data_map.get(ticker) is None:
                logger.warning(f"Skipping {ticker}: data fetch failed")
                results.append({"ticker": ticker, "status": "no_data"})
                continue

            try:
                result = await self.analyze_ticker_async(
                    ticker=ticker,
                    enable_multi_timeframe=enable_multi_timeframe,
                    export_to_csv=False,
                    csv_exporter=None,
                    as_of_date=as_of_date,
                )
                results.append(result)

                # Append to master CSV if requested
                if csv_exporter and result.get("status") == "success":
                    csv_exporter.append_to_master_csv(result)

                if i % 10 == 0:
                    logger.info(f"Analyzed {i}/{len(tickers)} stocks...")
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                results.append({"ticker": ticker, "status": "analysis_error", "error": str(e)})

        # Export bulk results if requested
        if export_to_csv and csv_exporter:
            csv_filepath = csv_exporter.export_multiple_stocks(results)
            logger.info(f"Batch analysis results exported to: {csv_filepath}")

        # Calculate statistics
        end_time = ist_now_naive()
        total_duration = (end_time - start_time).total_seconds()
        analysis_duration = (end_time - prefetch_time).total_seconds()

        successful = sum(1 for r in results if r.get("status") == "success")
        buyable = sum(1 for r in results if r.get("verdict") in ["buy", "strong_buy"])

        logger.info(
            f"Prefetch batch analysis complete: {successful}/{len(tickers)} successful, "
            f"{buyable} buyable, total {total_duration:.2f}s "
            f"(prefetch: {prefetch_duration:.2f}s, analysis: {analysis_duration:.2f}s)"
        )

        return results
