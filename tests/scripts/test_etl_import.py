import json
import os
import sys

import pytest


@pytest.mark.unit
def test_etl_imports_files_into_db(tmp_path):
    # Ensure root path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)
    # point DB to a temp sqlite file
    db_file = tmp_path / "app.db"
    os.environ["DB_URL"] = f"sqlite:///{db_file}"
    # create input files
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    # pending_orders.json
    (data_dir / "pending_orders.json").write_text(
        json.dumps(
            [
                {
                    "user_id": 1,
                    "symbol": "TCS",
                    "side": "buy",
                    "order_type": "limit",
                    "quantity": 10,
                    "price": 100,
                    "status": "amo",
                }
            ]
        ),
        encoding="utf-8",
    )
    # trades_history.json
    (data_dir / "trades_history.json").write_text(
        json.dumps(
            [
                {
                    "timestamp": "2025-01-01T00:00:00",
                    "order_id": "abc",
                    "ticker": "TCS",
                    "side": "buy",
                    "quantity": 10,
                    "price": 100,
                }
            ]
        ),
        encoding="utf-8",
    )
    # pnl_daily.csv
    (data_dir / "pnl_daily.csv").write_text(
        "date,realized_pnl,unrealized_pnl,fees\n2025-01-01,10,2,0.5\n", encoding="utf-8"
    )
    # signals file
    (data_dir / "system_recommended_symbols.json").write_text(
        json.dumps(
            [
                {
                    "symbol": "INFY",
                    "rsi10": 28.5,
                    "ema9": 200.0,
                    "ema200": 190.0,
                    "distance_to_ema9": 5.5,
                }
            ]
        ),
        encoding="utf-8",
    )
    # chdir to repo root so script finds ./data
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # copy scripts/etl_import_files.py accessible via module import
        from scripts.etl_import_files import main  # noqa: PLC0415

        main()
        # verify counts
        from src.infrastructure.db.models import (  # noqa: PLC0415
            Activity,
            Orders,
            PnlDaily,
            Signals,
        )
        from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

        sess = SessionLocal()
        assert sess.query(Orders).count() >= 1
        assert sess.query(Activity).count() >= 1
        assert sess.query(PnlDaily).count() >= 1
        assert sess.query(Signals).count() >= 1
        sess.close()
    finally:
        os.chdir(cwd)
