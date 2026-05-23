#!/usr/bin/env python3
"""
Chunked, resumable bulk analysis with Postgres job checkpoints.

Example:
  .venv\\Scripts\\python.exe tools\\bulk_analysis_job.py --chunk-size 25 --chartink
  .venv\\Scripts\\python.exe tools\\bulk_analysis_job.py --resume 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import CHUNK_DELAY_SECONDS, MAX_CONCURRENT_ANALYSES  # noqa: E402
from src.application.services.ohlcv_cache_health import (  # noqa: E402
    assess_price_cache_health,
    repair_from_health_report,
    sync_corporate_actions,
)
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.bulk_analysis_job_repository import (  # noqa: E402
    BulkAnalysisJobRepository,
)
from utils.logger import logger  # noqa: E402


def _default_symbols(chartink: bool) -> list[str]:
    if chartink:
        try:
            from modules.screener import get_chartink_screener_stocks  # noqa: PLC0415

            return list(get_chartink_screener_stocks())
        except Exception as exc:
            logger.warning("Chartink list failed: %s", exc)
    path = ROOT / "data" / "system_recommended_symbols.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(s) for s in data]
    return []


def _run_symbol(symbol: str, *, dip_mode: bool) -> dict:
    """Run trade_agent analysis + backtest for one symbol."""
    from config.strategy_config import StrategyConfig  # noqa: PLC0415
    from services.analysis_service import AnalysisService  # noqa: PLC0415
    from services.backtest_service import BacktestService  # noqa: PLC0415

    config = StrategyConfig.default()
    service = AnalysisService(config=config)
    result = service.analyze_ticker(ticker=symbol, enable_multi_timeframe=True, export_to_csv=False)
    if not isinstance(result, dict):
        return {"ticker": symbol, "status": "failed"}

    bt = BacktestService(default_years_back=5, dip_mode=dip_mode)
    scored = bt.add_backtest_scores_to_results([result], config=config)
    return scored[0] if scored else result


def _env_snapshot() -> dict:
    return {
        "MAX_CONCURRENT_ANALYSES": MAX_CONCURRENT_ANALYSES,
        "API_RATE_LIMIT_DELAY": os.getenv("API_RATE_LIMIT_DELAY"),
        "OHLCV_CACHE_ENABLED": os.getenv("OHLCV_CACHE_ENABLED", "true"),
    }


def run_job(
    *,
    job_id: int | None,
    symbols: list[str],
    chunk_size: int,
    dip_mode: bool,
    repair_cache: bool,
) -> int:
    """Execute or resume a bulk job; returns process exit code."""
    db = SessionLocal()
    repo = BulkAnalysisJobRepository(db)
    try:
        if job_id is None:
            job = repo.create_job(symbols, chunk_size=chunk_size, env_snapshot=_env_snapshot())
            job_id = job.id
            logger.info("Created bulk job id=%s symbols=%s", job_id, len(symbols))
        else:
            job = repo.get_job(job_id)
            if job is None:
                logger.error("Job %s not found", job_id)
                return 1
            symbols = repo.list_symbols(job)
            chunk_size = job.chunk_size

        repo.mark_running(job_id)
        cursor = job.cursor
        out_csv = job.output_csv or str(ROOT / "analysis_results" / f"bulk_job_{job_id}.csv")

        import pandas as pd  # noqa: PLC0415

        rows: list[dict] = []
        if Path(out_csv).exists():
            existing = pd.read_csv(out_csv)
            rows = existing.to_dict(orient="records")

        end_d = date.today()
        start_d = end_d - timedelta(days=365 * 5)

        while cursor < len(symbols):
            chunk = symbols[cursor : cursor + chunk_size]
            logger.info("Job %s chunk %s-%s", job_id, cursor, cursor + len(chunk))

            for symbol in chunk:
                t0 = time.perf_counter()
                cache_health = "skipped"
                try:
                    if repair_cache:
                        sync_corporate_actions(symbol, db)
                        report = assess_price_cache_health(symbol, start_d, end_d, db)
                        cache_health = report.status
                        if report.recommended_action != "none":
                            repair_from_health_report(report, db)

                    row = _run_symbol(symbol, dip_mode=dip_mode)
                    row["cache_health_status"] = cache_health
                    from src.application.services.ohlcv_cache_service import (  # noqa: PLC0415
                        get_ohlcv_cache_stats,
                    )

                    row["yahoo_calls"] = get_ohlcv_cache_stats().get("yahoo_calls", 0)
                    rows.append(row)
                    repo.upsert_symbol_status(
                        job_id,
                        symbol,
                        "ok",
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                        backtest_mode=row.get("backtest_mode"),
                        cache_health=cache_health,
                    )
                except Exception as exc:
                    logger.exception("Symbol %s failed: %s", symbol, exc)
                    repo.upsert_symbol_status(
                        job_id,
                        symbol,
                        "failed",
                        error=str(exc)[:1000],
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                        cache_health=cache_health,
                    )

            cursor += len(chunk)
            repo.update_job(job_id, cursor=cursor, output_csv=out_csv)
            pd.DataFrame(rows).to_csv(out_csv, index=False)
            logger.info("Checkpoint job=%s cursor=%s csv=%s", job_id, cursor, out_csv)

            if cursor < len(symbols) and CHUNK_DELAY_SECONDS > 0:
                time.sleep(CHUNK_DELAY_SECONDS)

        repo.mark_completed(job_id)
        logger.info("Bulk job %s completed: %s", job_id, out_csv)
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunked bulk analysis with DB resume")
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--resume", type=int, default=None, help="Existing job id")
    parser.add_argument("--chartink", action="store_true", help="Use Chartink screener list")
    parser.add_argument("--symbols", nargs="*", help="Explicit symbol list")
    parser.add_argument("--dip-mode", action="store_true")
    parser.add_argument(
        "--repair-cache", action="store_true", help="Health check + repair per symbol"
    )
    args = parser.parse_args()

    if args.resume:
        return run_job(
            job_id=args.resume,
            symbols=[],
            chunk_size=args.chunk_size,
            dip_mode=args.dip_mode,
            repair_cache=args.repair_cache,
        )

    symbols = args.symbols or _default_symbols(args.chartink)
    if not symbols:
        logger.error("No symbols to process")
        return 1

    return run_job(
        job_id=None,
        symbols=symbols,
        chunk_size=args.chunk_size,
        dip_mode=args.dip_mode,
        repair_cache=args.repair_cache,
    )


if __name__ == "__main__":
    raise SystemExit(main())
