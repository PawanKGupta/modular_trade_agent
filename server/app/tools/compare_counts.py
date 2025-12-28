from server.app.routers.metrics import get_dashboard_metrics
from server.app.routers.paper_trading import get_paper_trading_history
from src.infrastructure.db.session import SessionLocal


class U:
    pass


def main():
    u = U()
    u.id = 1
    s = SessionLocal()
    try:
        history = get_paper_trading_history(current=u, db=s)
        hist_profitable = sum(1 for p in history.closed_positions if p.realized_pnl > 0)
        print("[History] closed:", len(history.closed_positions), "profitable:", hist_profitable)
        metrics = get_dashboard_metrics(period_days=30, trade_mode=None, db=s, current=u)
        print(
            "[Metrics] total_trades:",
            metrics.total_trades,
            "profitable:",
            metrics.profitable_trades,
        )
    finally:
        s.close()


if __name__ == "__main__":
    main()
