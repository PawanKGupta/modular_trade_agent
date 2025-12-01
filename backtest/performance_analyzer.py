"""
Performance Analyzer Module

This module provides detailed analysis and reporting of backtest results.
It generates performance metrics, trade statistics, and exportable reports.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os


class PerformanceAnalyzer:
    """Analyzes and reports backtest performance"""

    def __init__(self, backtest_engine=None):
        """
        Initialize the performance analyzer

        Args:
            backtest_engine: BacktestEngine instance with completed backtest
        """
        self.engine = backtest_engine
        self.trades_df = None
        self.performance_metrics = {}
        self.monthly_returns = None

    def analyze_performance(self) -> Dict:
        """
        Perform comprehensive performance analysis

        Returns:
            Dictionary with detailed performance metrics
        """
        if not self.engine or not self.engine.results:
            raise ValueError("No backtest results available for analysis")

        self.trades_df = self.engine.get_trades_dataframe()

        if self.trades_df.empty:
            return {"error": "No trades to analyze"}

        # Calculate detailed performance metrics
        metrics = {
            **self.engine.results,  # Include basic results
            **self._calculate_advanced_metrics(),
            **self._calculate_risk_metrics(),
            **self._calculate_trade_statistics(),
            **self._calculate_time_based_metrics(),
        }

        self.performance_metrics = metrics
        return metrics

    def _calculate_advanced_metrics(self) -> Dict:
        """Calculate advanced performance metrics"""
        trades = self.trades_df

        if trades.empty:
            return {}

        # Sharpe ratio approximation (using trade returns)
        returns = trades["pnl_pct"].values
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) != 0 else 0
        else:
            sharpe_ratio = 0

        # Maximum consecutive wins and losses
        win_streak, loss_streak = self._calculate_streaks(trades["pnl"] > 0)

        # Average holding period
        closed_trades = trades[~trades["is_open"]]
        if not closed_trades.empty:
            holding_periods = (closed_trades["exit_date"] - closed_trades["entry_date"]).dt.days
            avg_holding_period = holding_periods.mean()
        else:
            avg_holding_period = 0

        return {
            "sharpe_ratio": sharpe_ratio,
            "max_consecutive_wins": win_streak,
            "max_consecutive_losses": loss_streak,
            "avg_holding_period_days": avg_holding_period,
            "total_commission": 0,  # Placeholder for future commission calculations
            "net_profit_after_costs": self.engine.results.get("total_pnl", 0),  # Same for now
        }

    def _calculate_risk_metrics(self) -> Dict:
        """Calculate risk-related metrics"""
        trades = self.trades_df

        if trades.empty:
            return {}

        # Maximum drawdown calculation (simplified)
        returns = trades["pnl_pct"].values
        cumulative_returns = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - peak
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0

        # Volatility of returns
        return_volatility = np.std(returns) if len(returns) > 1 else 0

        # Value at Risk (5% VaR)
        var_5 = np.percentile(returns, 5) if len(returns) > 0 else 0

        return {
            "max_drawdown_pct": max_drawdown,
            "return_volatility": return_volatility,
            "var_5_percent": var_5,
            "calmar_ratio": (np.mean(returns) / abs(max_drawdown)) if max_drawdown != 0 else 0,
        }

    def _calculate_trade_statistics(self) -> Dict:
        """Calculate detailed trade statistics"""
        trades = self.trades_df

        if trades.empty:
            return {}

        # Trade size statistics
        trade_sizes = trades["capital"].values

        # Return distribution
        returns = trades["pnl_pct"].values

        # Time-based statistics
        entry_times = trades["entry_date"]
        trade_frequency = (
            len(trades) / ((entry_times.max() - entry_times.min()).days / 30)
            if len(trades) > 1
            else 0
        )

        return {
            "avg_trade_size": np.mean(trade_sizes),
            "median_trade_size": np.median(trade_sizes),
            "largest_trade_size": np.max(trade_sizes),
            "smallest_trade_size": np.min(trade_sizes),
            "avg_return_per_trade": np.mean(returns),
            "median_return_per_trade": np.median(returns),
            "best_trade_pct": np.max(returns) if len(returns) > 0 else 0,
            "worst_trade_pct": np.min(returns) if len(returns) > 0 else 0,
            "trades_per_month": trade_frequency,
            "std_dev_returns": np.std(returns) if len(returns) > 1 else 0,
        }

    def _calculate_time_based_metrics(self) -> Dict:
        """Calculate time-based performance metrics"""
        trades = self.trades_df

        if trades.empty:
            return {}

        # Monthly performance analysis
        trades["entry_month"] = trades["entry_date"].dt.to_period("M")
        monthly_stats = (
            trades.groupby("entry_month")
            .agg({"pnl": "sum", "pnl_pct": "mean", "entry_date": "count"})
            .rename(columns={"entry_date": "trade_count"})
        )

        self.monthly_returns = monthly_stats

        # Best and worst months
        if not monthly_stats.empty:
            best_month = monthly_stats["pnl"].max()
            worst_month = monthly_stats["pnl"].min()
            profitable_months = (monthly_stats["pnl"] > 0).sum()
            total_months = len(monthly_stats)
        else:
            best_month = worst_month = 0
            profitable_months = total_months = 0

        return {
            "best_month_pnl": best_month,
            "worst_month_pnl": worst_month,
            "profitable_months": profitable_months,
            "total_months": total_months,
            "monthly_win_rate": (profitable_months / total_months * 100) if total_months > 0 else 0,
        }

    def _calculate_streaks(self, win_series: pd.Series) -> Tuple[int, int]:
        """Calculate maximum consecutive wins and losses"""
        if win_series.empty:
            return 0, 0

        # Convert to numpy for easier processing
        wins = win_series.values

        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        for is_win in wins:
            if is_win:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)

        return max_win_streak, max_loss_streak

    def generate_report(self, save_to_file: bool = False, filename: str = None) -> str:
        """
        Generate a comprehensive performance report

        Args:
            save_to_file: Whether to save report to file
            filename: Custom filename for report

        Returns:
            Formatted report string
        """
        if not self.performance_metrics:
            self.analyze_performance()

        metrics = self.performance_metrics

        # Build report sections
        report_sections = [
            self._generate_header_section(),
            self._generate_summary_section(),
            self._generate_performance_section(),
            self._generate_risk_section(),
            self._generate_trade_analysis_section(),
            self._generate_time_analysis_section(),
            self._generate_recommendations_section(),
        ]

        report = "\n".join(report_sections)

        if save_to_file:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"backtest_report_{self.engine.symbol}_{timestamp}.txt"

            # Create reports directory if it doesn't exist
            os.makedirs("backtest_reports", exist_ok=True)
            filepath = os.path.join("backtest_reports", filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)

            print(f"Report saved to: {filepath}")

        return report

    def _generate_header_section(self) -> str:
        """Generate report header"""
        return f"""
{'='*80}
BACKTEST PERFORMANCE REPORT
{'='*80}
Symbol: {self.engine.symbol}
Strategy: EMA200 + RSI10 Pyramiding Strategy
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}
"""

    def _generate_summary_section(self) -> str:
        """Generate summary section"""
        m = self.performance_metrics
        return f"""
SUMMARY
{'-'*40}
Backtest Period: {m['period']}
Total Trades: {m['total_trades']}
Total Invested: Rs {m.get('total_invested', 0):,.0f}
Total P&L: Rs {m.get('total_pnl', 0):,.0f}
Total Return: {m.get('total_return_pct', 0):+.2f}%
Strategy vs Buy & Hold: {m.get('strategy_vs_buy_hold', 0):+.2f}%
"""

    def _generate_performance_section(self) -> str:
        """Generate performance metrics section"""
        m = self.performance_metrics
        return f"""
PERFORMANCE METRICS
{'-'*40}
Win Rate: {m.get('win_rate', 0):.1f}%
Profit Factor: {m.get('profit_factor', 0):.2f}
Sharpe Ratio: {m.get('sharpe_ratio', 0):.2f}
Average Win: Rs {m.get('avg_win', 0):,.0f}
Average Loss: Rs {m.get('avg_loss', 0):,.0f}
Best Trade: {m.get('best_trade_pct', 0):+.2f}%
Worst Trade: {m.get('worst_trade_pct', 0):+.2f}%
Average Return per Trade: {m.get('avg_return_per_trade', 0):+.2f}%
"""

    def _generate_risk_section(self) -> str:
        """Generate risk analysis section"""
        m = self.performance_metrics
        return f"""
RISK ANALYSIS
{'-'*40}
Maximum Drawdown: {m.get('max_drawdown_pct', 0):.2f}%
Return Volatility: {m.get('return_volatility', 0):.2f}%
Value at Risk (5%): {m.get('var_5_percent', 0):.2f}%
Calmar Ratio: {m.get('calmar_ratio', 0):.2f}
Max Consecutive Wins: {m.get('max_consecutive_wins', 0)}
Max Consecutive Losses: {m.get('max_consecutive_losses', 0)}
"""

    def _generate_trade_analysis_section(self) -> str:
        """Generate trade analysis section"""
        m = self.performance_metrics
        return f"""
TRADE ANALYSIS
{'-'*40}
Average Holding Period: {m.get('avg_holding_period_days', 0):.1f} days
Trades per Month: {m.get('trades_per_month', 0):.1f}
Average Trade Size: Rs {m.get('avg_trade_size', 0):,.0f}
Largest Position: Rs {m.get('largest_trade_size', 0):,.0f}
Smallest Position: Rs {m.get('smallest_trade_size', 0):,.0f}
Open Positions: {m.get('open_positions', 0)}
Closed Positions: {m.get('closed_positions', 0)}
"""

    def _generate_time_analysis_section(self) -> str:
        """Generate time-based analysis section"""
        m = self.performance_metrics
        return f"""
TIME-BASED ANALYSIS
{'-'*40}
Total Months Analyzed: {m.get('total_months', 0)}
Profitable Months: {m.get('profitable_months', 0)}
Monthly Win Rate: {m.get('monthly_win_rate', 0):.1f}%
Best Month P&L: Rs {m.get('best_month_pnl', 0):,.0f}
Worst Month P&L: Rs {m.get('worst_month_pnl', 0):,.0f}
"""

    def _generate_recommendations_section(self) -> str:
        """Generate recommendations based on performance"""
        m = self.performance_metrics
        recommendations = []

        # Performance-based recommendations
        if m.get("win_rate", 0) < 50:
            recommendations.append("- Consider tightening entry criteria - win rate below 50%")

        if m.get("profit_factor", 0) < 1.5:
            recommendations.append(
                "- Strategy profitability is marginal - consider risk management improvements"
            )

        if m.get("max_drawdown_pct", 0) < -20:
            recommendations.append(
                "- High drawdown detected - implement stop-loss or position sizing rules"
            )

        if m.get("strategy_vs_buy_hold", 0) < 0:
            recommendations.append(
                "- Strategy underperforming buy & hold - review entry/exit timing"
            )

        if m.get("max_consecutive_losses", 0) > 5:
            recommendations.append(
                "- High consecutive losses - consider trend filtering or market regime detection"
            )

        if not recommendations:
            recommendations.append("- Strategy shows good performance characteristics")
            recommendations.append(
                "- Consider optimizing position sizing for better risk-adjusted returns"
            )

        recs_text = "\n".join(recommendations)

        return f"""
RECOMMENDATIONS
{'-'*40}
{recs_text}

Note: This analysis is based on historical data and past performance
does not guarantee future results. Always consider current market
conditions and risk tolerance when implementing any strategy.

{'='*80}
"""

    def export_trades_to_csv(self, filename: str = None) -> str:
        """
        Export detailed trades to CSV file

        Args:
            filename: Custom filename for export

        Returns:
            Path to exported file
        """
        if self.trades_df is None or self.trades_df.empty:
            self.trades_df = self.engine.get_trades_dataframe()

        if self.trades_df.empty:
            raise ValueError("No trades to export")

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_trades_{self.engine.symbol}_{timestamp}.csv"

        # Create exports directory if it doesn't exist
        os.makedirs("backtest_exports", exist_ok=True)
        filepath = os.path.join("backtest_exports", filename)

        # Export with additional calculated columns
        export_df = self.trades_df.copy()
        if not export_df.empty:
            export_df["holding_period_days"] = (
                export_df["exit_date"] - export_df["entry_date"]
            ).dt.days.fillna(0)

        export_df.to_csv(filepath, index=False)
        print(f"Trades exported to: {filepath}")

        return filepath

    def get_monthly_performance(self) -> pd.DataFrame:
        """
        Get monthly performance breakdown

        Returns:
            DataFrame with monthly performance data
        """
        if self.monthly_returns is None:
            self.analyze_performance()

        return self.monthly_returns if self.monthly_returns is not None else pd.DataFrame()
