from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PortfolioSnapshot, Positions, TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()


@router.get("/history")
def portfolio_history(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Return historical portfolio snapshots for the current user.

    Returns list of snapshots ordered by date descending.
    """
    try:
        qry = db.query(PortfolioSnapshot).filter(PortfolioSnapshot.user_id == current.id)
        if start:
            qry = qry.filter(PortfolioSnapshot.date >= start)
        if end:
            qry = qry.filter(PortfolioSnapshot.date <= end)

        records = qry.order_by(PortfolioSnapshot.date.desc()).limit(limit).all()

        return [
            {
                "date": r.date.isoformat(),
                "total_value": r.total_value,
                "invested_value": r.invested_value,
                "available_cash": r.available_cash,
                "unrealized_pnl": r.unrealized_pnl,
                "realized_pnl": r.realized_pnl,
                "open_positions_count": r.open_positions_count,
                "closed_positions_count": r.closed_positions_count,
                "total_return": r.total_return,
                "daily_return": r.daily_return,
                "snapshot_type": r.snapshot_type,
            }
            for r in records
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch portfolio history: {e}"
        ) from e


@router.post("/snapshot")
def create_portfolio_snapshot(
    snapshot_date: date | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Create or update a portfolio snapshot for the given date (defaults to today).

    This endpoint gathers current portfolio data (paper or broker) and stores a daily snapshot.
    """
    try:
        target_date = snapshot_date or date.today()

        settings_repo = SettingsRepository(db)
        settings = settings_repo.ensure_default(current.id)

        # Decide which portfolio source to use
        if settings.trade_mode == TradeMode.BROKER:
            # Import broker function locally to reuse logic
            from ..routers.broker import get_broker_portfolio  # noqa: PLC0415

            portfolio = get_broker_portfolio(db=db, current=current)
        else:
            from ..routers.paper_trading import get_paper_trading_portfolio  # noqa: PLC0415

            try:
                portfolio = get_paper_trading_portfolio(db=db, current=current)
            except HTTPException as e:
                # If paper trading account not initialized (404), create empty portfolio
                if e.status_code == 404:  # noqa: PLR2004
                    from ..schemas.portfolio import (  # noqa: PLC0415
                        PaperTradingAccount,
                        PaperTradingPortfolio,
                    )

                    portfolio = PaperTradingPortfolio(
                        account=PaperTradingAccount(
                            initial_capital=0.0,
                            available_cash=0.0,
                            total_pnl=0.0,
                            realized_pnl=0.0,
                            unrealized_pnl=0.0,
                            portfolio_value=0.0,
                            total_value=0.0,
                            return_percentage=0.0,
                        ),
                        holdings=[],
                        recent_orders=[],
                        order_statistics={
                            "total_orders": 0,
                            "buy_orders": 0,
                            "sell_orders": 0,
                            "completed_orders": 0,
                            "pending_orders": 0,
                            "cancelled_orders": 0,
                            "rejected_orders": 0,
                            "success_rate": 0.0,
                        },
                    )
                else:
                    raise
            except Exception:
                # Handle any other exceptions (e.g., file system errors, etc.)
                # Create empty portfolio to allow snapshot creation
                from ..schemas.portfolio import (  # noqa: PLC0415
                    PaperTradingAccount,
                    PaperTradingPortfolio,
                )

                portfolio = PaperTradingPortfolio(
                    account=PaperTradingAccount(
                        initial_capital=0.0,
                        available_cash=0.0,
                        total_pnl=0.0,
                        realized_pnl=0.0,
                        unrealized_pnl=0.0,
                        portfolio_value=0.0,
                        total_value=0.0,
                        return_percentage=0.0,
                    ),
                    holdings=[],
                    recent_orders=[],
                    order_statistics={
                        "total_orders": 0,
                        "buy_orders": 0,
                        "sell_orders": 0,
                        "completed_orders": 0,
                        "pending_orders": 0,
                        "cancelled_orders": 0,
                        "rejected_orders": 0,
                        "success_rate": 0.0,
                    },
                )

        account = getattr(portfolio, "account", None)
        holdings = getattr(portfolio, "holdings", [])

        # Count closed positions from Positions table for user
        closed_count = (
            db.query(Positions)
            .filter(Positions.user_id == current.id, Positions.closed_at != None)
            .count()
        )  # noqa: E711

        # Upsert snapshot
        existing = (
            db.query(PortfolioSnapshot)
            .filter(
                PortfolioSnapshot.user_id == current.id,
                PortfolioSnapshot.date == target_date,
                PortfolioSnapshot.snapshot_type == "eod",
            )
            .one_or_none()
        )

        total_value = (
            float(account.total_value)
            if account and getattr(account, "total_value", None) is not None
            else 0.0
        )
        invested_value = (
            float(account.initial_capital)
            if account and getattr(account, "initial_capital", None) is not None
            else 0.0
        )
        available_cash = (
            float(account.available_cash)
            if account and getattr(account, "available_cash", None) is not None
            else 0.0
        )
        unrealized = (
            float(account.unrealized_pnl)
            if account and getattr(account, "unrealized_pnl", None) is not None
            else 0.0
        )
        realized = (
            float(account.realized_pnl)
            if account and getattr(account, "realized_pnl", None) is not None
            else 0.0
        )

        open_count = len(holdings) if holdings is not None else 0

        if existing:
            existing.total_value = total_value
            existing.invested_value = invested_value
            existing.available_cash = available_cash
            existing.unrealized_pnl = unrealized
            existing.realized_pnl = realized
            existing.open_positions_count = open_count
            existing.closed_positions_count = closed_count
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return {"status": "updated", "date": target_date.isoformat()}

        snapshot = PortfolioSnapshot(
            user_id=current.id,
            date=target_date,
            total_value=total_value,
            invested_value=invested_value,
            available_cash=available_cash,
            unrealized_pnl=unrealized,
            realized_pnl=realized,
            open_positions_count=open_count,
            closed_positions_count=closed_count,
            total_return=0.0,
            daily_return=0.0,
            snapshot_type="eod",
        )

        db.add(snapshot)
        db.commit()
        return {"status": "created", "date": target_date.isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {e}") from e
