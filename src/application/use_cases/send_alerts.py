"""
Send Alerts Use Case

Handles sending trading alerts via notifications.
"""

from typing import List
from ..dto.analysis_response import BulkAnalysisResponse, AnalysisResponse

# Bridge to legacy code
from core.telegram import send_telegram
from utils.logger import logger


class SendAlertsUseCase:
    """
    Use case for sending trading alerts

    Orchestrates:
    1. Filters buyable candidates
    2. Formats messages
    3. Sends notifications
    """

    def execute(
        self,
        bulk_response: BulkAnalysisResponse,
        min_combined_score: float = 0.0,
        use_final_verdict: bool = False,
    ) -> bool:
        """
        Send alerts for analysis results

        Args:
            bulk_response: Bulk analysis response with results
            min_combined_score: Minimum combined score threshold for filtering
            use_final_verdict: Use final_verdict (after backtest) instead of verdict

        Returns:
            True if alerts sent successfully
        """
        try:
            # Get buyable candidates with score filtering
            buy_candidates = bulk_response.get_buy_candidates(
                min_combined_score=min_combined_score, use_final_verdict=use_final_verdict
            )

            if not buy_candidates:
                logger.info("No buy candidates to alert")
                return True

            # Get strong buy candidates with score filtering
            strong_buys = bulk_response.get_strong_buy_candidates(
                min_combined_score=min_combined_score, use_final_verdict=use_final_verdict
            )

            # Format message
            message = self._format_telegram_message(buy_candidates, strong_buys)

            # Send via Telegram
            send_telegram(message)

            logger.info(
                f"Sent alerts for {len(buy_candidates)} candidates ({len(strong_buys)} strong buys)"
            )
            return True

        except Exception as e:
            logger.error(f"Error sending alerts: {e}")
            return False

    def _format_telegram_message(
        self, buy_candidates: List[AnalysisResponse], strong_buys: List[AnalysisResponse]
    ) -> str:
        """
        Format Telegram message for buy candidates

        Args:
            buy_candidates: All buyable stocks
            strong_buys: Strong buy stocks

        Returns:
            Formatted message string
        """
        msg = "*Reversal Buy Candidates (today)*\n"

        # Strong buys first
        if strong_buys:
            msg += "\n? *STRONG BUY* (Multi-timeframe confirmed):\n"
            for i, stock in enumerate(strong_buys, 1):
                msg += self._format_stock_info(stock, i)

        # Regular buys (excluding strong buys)
        strong_buy_tickers = {s.ticker for s in strong_buys}
        regular_buys = [s for s in buy_candidates if s.ticker not in strong_buy_tickers]

        if regular_buys:
            msg += "\n? *BUY* candidates:\n"
            for i, stock in enumerate(regular_buys, 1):
                msg += self._format_stock_info(stock, i)

        return msg

    def _format_stock_info(self, stock: AnalysisResponse, index: int) -> str:
        """
        Format individual stock information

        Args:
            stock: Stock analysis response
            index: Position in list

        Returns:
            Formatted stock info string
        """
        lines = [f"{index}. {stock.ticker}:"]

        # Buy range
        if stock.buy_range:
            lines.append(f"\tBuy ({stock.buy_range[0]:.2f}-{stock.buy_range[1]:.2f})")

        # Target
        if stock.target:
            gain_pct = (
                ((stock.target - stock.last_close) / stock.last_close) * 100
                if stock.last_close > 0
                else 0
            )
            lines.append(f"\tTarget {stock.target:.2f} (+{gain_pct:.1f}%)")

        # Stop loss
        if stock.stop_loss:
            loss_pct = (
                ((stock.last_close - stock.stop_loss) / stock.last_close) * 100
                if stock.last_close > 0
                else 0
            )
            lines.append(f"\tStop {stock.stop_loss:.2f} (-{loss_pct:.1f}%)")

        # RSI
        if stock.rsi:
            lines.append(f"\tRSI:{stock.rsi:.1f}")

        # MTF score
        if stock.mtf_alignment_score > 0:
            lines.append(f"\tMTF:{stock.mtf_alignment_score:.0f}/10")

        # Risk-reward
        if stock.metadata and stock.metadata.get("risk_reward_ratio"):
            rr = stock.metadata["risk_reward_ratio"]
            lines.append(f"\tRR:{rr:.1f}x")

        # PE ratio
        if stock.metadata and stock.metadata.get("pe"):
            pe = stock.metadata["pe"]
            if pe and pe > 0:
                lines.append(f"\tPE:{pe:.1f}")

        # Volume
        if stock.metadata and stock.metadata.get("volume_multiplier"):
            vol = stock.metadata["volume_multiplier"]
            lines.append(f"\tVol:{vol:.1f}x")

        # Backtest score
        if stock.backtest_score > 0:
            lines.append(f"\tBacktest:{stock.backtest_score:.0f}/100")

        # Combined score
        if stock.combined_score > 0:
            lines.append(f"\tScore:{stock.combined_score:.1f}/100")

        # Priority
        if stock.priority_score > 0:
            lines.append(f"\tPriority:{stock.priority_score:.0f}")

        return "\n".join(lines) + "\n\n"
