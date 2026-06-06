from __future__ import annotations

import pandas as pd

from services.ml_training_service import MLTrainingService


def test_train_dip_success_classifier_smoke(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D", "E"],
            "entry_date": ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
            "exit_date": ["2020-01-02"] * 5,
            "n_adds": [1, 2, 1, 3, 1],
            "pnl_pct": [2.0, -1.0, 1.5, 4.0, 0.5],
            "net_win": [1, 0, 1, 1, 0],
            "strong_win": [0, 0, 0, 1, 0],
            "rsi_10": [25, 28, 22, 19, 29],
            "dip_depth_from_20d_high_pct": [5, 3, 7, 10, 2],
            "volume_ratio": [1.1, 0.9, 1.5, 2.0, 0.8],
            "consecutive_red_days": [2, 1, 3, 5, 1],
        }
    )
    svc = MLTrainingService(models_dir=str(tmp_path))
    model_path, acc = svc.train_dip_success_classifier(
        df=df,
        model_save_path=tmp_path / "dip.pkl",
        calibrate=False,
        test_size=0.4,
        random_state=1,
    )
    assert model_path
    assert acc >= 0.0
