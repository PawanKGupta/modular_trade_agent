"""
Telegram Formatter

Formats analysis results into rich Telegram messages.
Extracted from trade_agent.py for clean presentation layer.
"""

from typing import List
from ...application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


class TelegramFormatter:
    """
    Formats analysis results for Telegram messages

    Provides rich, readable formatting with all relevant metrics.
    """

    def format_bulk_response(
        self, response: BulkAnalysisResponse, include_backtest: bool = False
    ) -> str:
        """
        Format bulk analysis response for Telegram

        Args:
            response: Bulk analysis response
            include_backtest: Whether to include backtest information

        Returns:
            Formatted Telegram message
        """
        buy_candidates = response.get_buy_candidates()
        strong_buys = response.get_strong_buy_candidates()

        if not buy_candidates:
            return "*No buy candidates found today*"

        # Header
        msg = "*Reversal Buy Candidates (today)*"
        if include_backtest:
            msg += " *with Backtest Scoring*"
        msg += "\n"

        # Strong buys
        if strong_buys:
            msg += "\n? *STRONG BUY* (Multi-timeframe confirmed):\n"
            for i, stock in enumerate(strong_buys, 1):
                msg += self.format_stock_detailed(stock, i)

        # Regular buys
        strong_buy_tickers = {s.ticker for s in strong_buys}
        regular_buys = [s for s in buy_candidates if s.ticker not in strong_buy_tickers]

        if regular_buys:
            msg += "\n? *BUY* candidates:\n"
            for i, stock in enumerate(regular_buys, 1):
                msg += self.format_stock_detailed(stock, i)

        return msg

    def format_stock_detailed(self, stock: AnalysisResponse, index: int) -> str:
        """
        Format detailed stock information

        Args:
            stock: Stock analysis response
            index: Position in list

        Returns:
            Formatted stock info
        """
        lines = [f"{index}. {stock.ticker}:"]

        # Buy range
        if stock.buy_range:
            lines.append(f"\tBuy ({stock.buy_range[0]:.2f}-{stock.buy_range[1]:.2f})")

        # Target
        if stock.target and stock.last_close > 0:
            gain_pct = ((stock.target - stock.last_close) / stock.last_close) * 100
            lines.append(f"\tTarget {stock.target:.2f} (+{gain_pct:.1f}%)")

        # Stop loss
        if stock.stop_loss and stock.last_close > 0:
            loss_pct = ((stock.last_close - stock.stop_loss) / stock.last_close) * 100
            lines.append(f"\tStop {stock.stop_loss:.2f} (-{loss_pct:.1f}%)")

        # RSI
        if stock.rsi:
            lines.append(f"\tRSI:{stock.rsi:.1f}")

        # MTF score
        if stock.mtf_alignment_score > 0:
            lines.append(f"\tMTF:{stock.mtf_alignment_score:.0f}/10")

        # Risk-reward ratio
        if stock.metadata and stock.metadata.get("risk_reward_ratio"):
            rr = stock.metadata["risk_reward_ratio"]
            lines.append(f"\tRR:{rr:.1f}x")

        # Setup quality indicators
        setup_indicators = self._get_setup_indicators(stock)
        if setup_indicators:
            lines.append(f"\t{setup_indicators}")

        # PE ratio
        if stock.metadata and stock.metadata.get("pe"):
            pe = stock.metadata["pe"]
            if pe and pe > 0:
                lines.append(f"\tPE:{pe:.1f}")

        # Volume
        if stock.metadata and stock.metadata.get("volume_multiplier"):
            vol = stock.metadata["volume_multiplier"]
            lines.append(f"\tVol:{vol:.1f}x")

        # News sentiment
        sentiment_info = self._get_sentiment_info(stock)
        if sentiment_info:
            lines.append(f"\t{sentiment_info}")

        # Backtest score
        if stock.backtest_score > 0:
            lines.append(f"\tBacktest:{stock.backtest_score:.0f}/100")

        # Combined score
        if stock.combined_score > 0:
            lines.append(f"\tScore:{stock.combined_score:.1f}/100")

        # Priority
        if stock.priority_score > 0:
            priority_emoji = "? HIGHEST PRIORITY" if stock.priority_score >= 100 else ""
            lines.append(f"\tPriority:{stock.priority_score:.0f} {priority_emoji}")

        # ML Prediction (if available)
        ml_info = self._get_ml_info(stock)
        if ml_info:
            lines.append(f"\t{ml_info}")

        return "\n".join(lines) + "\n\n"

    def format_stock_simple(self, stock: AnalysisResponse) -> str:
        """
        Format simple stock information (one line)

        Args:
            stock: Stock analysis response

        Returns:
            Simple formatted string
        """
        info = f"{stock.ticker}: {stock.verdict.upper()}"

        if stock.rsi:
            info += f" (RSI:{stock.rsi:.1f}"

        if stock.priority_score > 0:
            info += f", Priority:{stock.priority_score:.0f}"

        if stock.rsi:
            info += ")"

        return info

    def format_summary(self, response: BulkAnalysisResponse) -> str:
        """
        Format summary statistics

        Args:
            response: Bulk analysis response

        Returns:
            Summary message
        """
        return (
            f"? *Analysis Summary*\n"
            f"Total: {response.total_analyzed}\n"
            f"Success: {response.successful}\n"
            f"Failed: {response.failed}\n"
            f"Buyable: {response.buyable_count}\n"
            f"Time: {response.execution_time_seconds:.2f}s"
        )

    def _get_setup_indicators(self, stock: AnalysisResponse) -> str:
        """Extract setup quality indicators from metadata"""
        if not stock.metadata or not stock.metadata.get("timeframe_analysis"):
            return ""

        tf_analysis = stock.metadata["timeframe_analysis"]
        daily_analysis = tf_analysis.get("daily_analysis", {})

        if not daily_analysis:
            return ""

        indicators = []

        # Support quality
        support = daily_analysis.get("support_analysis", {})
        support_quality = support.get("quality", "none")
        support_distance = support.get("distance_pct", 0)

        if support_quality == "strong":
            indicators.append(f"StrongSupp:{support_distance:.1f}%")
        elif support_quality == "moderate":
            indicators.append(f"ModSupp:{support_distance:.1f}%")

        # Oversold severity
        oversold = daily_analysis.get("oversold_analysis", {})
        oversold_severity = oversold.get("severity", "none")

        if oversold_severity == "extreme":
            indicators.append("ExtremeRSI")
        elif oversold_severity == "high":
            indicators.append("HighRSI")

        # Volume exhaustion
        volume_ex = daily_analysis.get("volume_exhaustion", {})
        if volume_ex.get("exhaustion_score", 0) >= 2:
            indicators.append("VolExh")

        # Support proximity
        if support_distance <= 1.0 and support_quality in ["strong", "moderate"]:
            indicators.append("NearSupport")
        elif support_distance <= 2.0 and support_quality in ["strong", "moderate"]:
            indicators.append("CloseSupport")

        return " ".join(indicators)

    def _get_sentiment_info(self, stock: AnalysisResponse) -> str:
        """Extract news sentiment info from metadata"""
        if not stock.metadata or not stock.metadata.get("news_sentiment"):
            return "News:NA"

        sentiment = stock.metadata["news_sentiment"]
        if not sentiment.get("enabled"):
            return "News:NA"

        used = int(sentiment.get("used", 0))
        label = sentiment.get("label", "neutral")
        score = float(sentiment.get("score", 0.0))

        label_short = "Pos" if label == "positive" else "Neg" if label == "negative" else "Neu"
        return f"News:{label_short} {score:+.2f} ({used})"

    def _get_ml_info(self, stock: AnalysisResponse) -> str:
        """Extract ML prediction info from metadata"""
        if not stock.metadata:
            return ""

        # Check for ML verdict in metadata or directly on stock object
        ml_verdict = stock.metadata.get("ml_verdict")
        ml_confidence = stock.metadata.get("ml_confidence")
        verdict_source = stock.metadata.get("verdict_source")
        rule_verdict = stock.metadata.get("rule_verdict")

        if not ml_verdict or ml_confidence is None:
            return ""

        # Emoji for ML verdict
        ml_emoji = {"strong_buy": "??", "buy": "??", "watch": "??", "avoid": "??"}.get(
            ml_verdict, "?"
        )

        # Build ML info string
        ml_info = f"{ml_emoji} ML:{ml_verdict.upper()} ({ml_confidence:.0%})"

        # Add comparison if ML overrode rule-based verdict
        if verdict_source == "ml" and rule_verdict and rule_verdict != ml_verdict:
            ml_info += f" [was:{rule_verdict}]"

        return ml_info
