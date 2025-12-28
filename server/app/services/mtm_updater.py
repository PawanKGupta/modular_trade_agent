"""
MTM (Mark-to-Market) Update Service

Updates unrealized P&L for all open positions by fetching live market prices.
Runs daily at market close (3:30 PM IST) via scheduler.
"""

import logging

from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions
from src.infrastructure.db.session import SessionLocal

logger = logging.getLogger(__name__)


def get_live_price(symbol: str) -> float | None:
    """
    Fetch live price for a symbol using yfinance

    Args:
        symbol: Stock symbol (without exchange suffix)

    Returns:
        Current price or None if unavailable
    """
    try:
        import yfinance as yf

        # Add NSE suffix for Indian stocks
        ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        stock = yf.Ticker(ticker)

        # Try multiple price fields
        info = stock.info
        price = (
            info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        )

        if price:
            return float(price)

        # Fallback: use fast_info
        try:
            return float(stock.fast_info.get("lastPrice", 0))
        except Exception:
            pass

        return None

    except Exception as e:
        logger.debug(f"Failed to fetch live price for {symbol}: {e}")
        return None


def update_unrealized_pnl_for_position(db: Session, position: Positions, live_price: float) -> bool:
    """
    Update unrealized P&L for a single position

    Args:
        db: Database session
        position: Position object
        live_price: Current market price

    Returns:
        True if updated successfully
    """
    try:
        if not position.quantity or position.quantity <= 0:
            return False

        cost_basis = position.avg_price * position.quantity
        market_value = live_price * position.quantity
        unrealized_pnl = market_value - cost_basis

        position.unrealized_pnl = unrealized_pnl
        db.commit()

        logger.debug(
            f"Updated MTM for {position.symbol}: "
            f"qty={position.quantity}, "
            f"avg_price={position.avg_price:.2f}, "
            f"live_price={live_price:.2f}, "
            f"unrealized_pnl={unrealized_pnl:.2f}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to update unrealized P&L for {position.symbol}: {e}")
        db.rollback()
        return False


def update_mtm_for_user(user_id: int, db: Session | None = None) -> dict[str, int]:
    """
    Update MTM for all open positions of a user

    Args:
        user_id: User ID
        db: Optional database session (creates new if not provided)

    Returns:
        Statistics: {
            'total': total open positions,
            'updated': successfully updated,
            'failed': failed to update,
            'skipped': skipped (no price available)
        }
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Fetch all open positions
        open_positions = (
            db.query(Positions)
            .filter(
                Positions.user_id == user_id,
                Positions.closed_at.is_(None),
                Positions.quantity > 0,
            )
            .all()
        )

        stats = {
            "total": len(open_positions),
            "updated": 0,
            "failed": 0,
            "skipped": 0,
        }

        logger.info(f"Starting MTM update for user {user_id}: {stats['total']} open positions")

        for position in open_positions:
            live_price = get_live_price(position.symbol)

            if live_price is None:
                logger.warning(f"No live price available for {position.symbol}")
                stats["skipped"] += 1
                continue

            if update_unrealized_pnl_for_position(db, position, live_price):
                stats["updated"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"MTM update completed for user {user_id}: "
            f"updated={stats['updated']}, "
            f"failed={stats['failed']}, "
            f"skipped={stats['skipped']}"
        )

        return stats

    except Exception as e:
        logger.exception(f"Error in MTM update for user {user_id}: {e}")
        return {"total": 0, "updated": 0, "failed": 0, "skipped": 0, "error": str(e)}

    finally:
        if close_db:
            db.close()


def update_mtm_for_all_users() -> dict[int, dict[str, int]]:
    """
    Update MTM for all users with open positions

    Returns:
        Dict mapping user_id to their stats
    """
    db = SessionLocal()
    try:
        # Get all unique user IDs with open positions
        user_ids = (
            db.query(Positions.user_id)
            .filter(Positions.closed_at.is_(None), Positions.quantity > 0)
            .distinct()
            .all()
        )

        user_ids = [uid[0] for uid in user_ids]

        logger.info(f"Starting MTM update for {len(user_ids)} users")

        results = {}
        for user_id in user_ids:
            results[user_id] = update_mtm_for_user(user_id, db)

        logger.info("MTM update completed for all users")
        return results

    finally:
        db.close()


if __name__ == "__main__":
    # Test the MTM updater
    logging.basicConfig(level=logging.INFO)

    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        stats = update_mtm_for_user(user_id)
        print(f"\nMTM Update Stats for User {user_id}:")
        print(f"  Total: {stats['total']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Skipped: {stats['skipped']}")
    else:
        results = update_mtm_for_all_users()
        print(f"\nMTM Update completed for {len(results)} users")
        for user_id, stats in results.items():
            print(f"  User {user_id}: {stats}")
