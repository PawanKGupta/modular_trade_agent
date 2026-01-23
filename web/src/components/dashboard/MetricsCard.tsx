import { useQuery } from '@tanstack/react-query';
import { getDashboardMetrics, type TradeMetrics } from '@/api/metrics';

interface MetricsCardProps {
	periodDays?: number;
	tradeMode?: string;
}

export function MetricsCard({ periodDays = 30, tradeMode }: MetricsCardProps) {
	const { data, isLoading, isError } = useQuery<TradeMetrics>({
		queryKey: ['metrics', 'dashboard', periodDays, tradeMode],
		queryFn: () => getDashboardMetrics(periodDays, tradeMode),
		refetchInterval: 60000, // Refresh every minute
	});

	const formatMoney = (amount: number) => {
		return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
	};

	if (isLoading) {
		return (
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
				<div className="text-sm text-[var(--muted)]">Loading metrics...</div>
			</div>
		);
	}

	if (isError || !data) {
		return (
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
				<div className="text-sm text-red-400">Failed to load metrics</div>
			</div>
		);
	}

	const bestTradeColor = data.best_trade_profit && data.best_trade_profit > 0 ? 'text-green-400' : 'text-gray-400';
	const worstTradeColor = data.worst_trade_loss && data.worst_trade_loss < 0 ? 'text-red-400' : 'text-gray-400';

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
			<div className="px-4 py-3 border-b border-[#1e293b]">
				<h3 className="font-medium text-[var(--text)]">Trading Metrics ({periodDays}d)</h3>
			</div>
			<div className="p-4 space-y-4">
				{/* First Row: Key Metrics */}
				<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Total Trades</div>
						<div className="text-lg font-semibold text-[var(--text)]">{data.total_trades}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Win Rate</div>
						<div
							className={`text-lg font-semibold ${
								data.win_rate >= 50 ? 'text-green-400' : data.win_rate > 0 ? 'text-yellow-400' : 'text-red-400'
							}`}
						>
							{data.win_rate.toFixed(1)}%
						</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Total P&L</div>
						<div
							className={`text-lg font-semibold ${
								data.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(data.total_realized_pnl)}
						</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Days Traded</div>
						<div className="text-lg font-semibold text-[var(--text)]">{data.days_traded}</div>
					</div>
				</div>

				{/* Second Row: Trade Breakdown */}
				<div className="grid grid-cols-3 gap-3">
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Profitable</div>
						<div className="text-lg font-semibold text-green-400">{data.profitable_trades}</div>
						<div className="text-xs text-[var(--muted)] mt-1">{formatMoney(data.average_profit_per_trade)} avg</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Losing</div>
						<div className="text-lg font-semibold text-red-400">{data.losing_trades}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Avg Hold</div>
						<div className="text-lg font-semibold text-[var(--text)]">{data.avg_holding_period_days}d</div>
					</div>
				</div>

				{/* Third Row: Best/Worst Trades */}
				<div className="grid grid-cols-2 gap-3">
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Best Trade</div>
						<div className={`text-lg font-semibold ${bestTradeColor}`}>
							{data.best_trade_profit !== null ? formatMoney(data.best_trade_profit) : 'N/A'}
						</div>
						<div className="text-xs text-[var(--muted)] mt-1">{data.best_trade_symbol || '-'}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-3 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Worst Trade</div>
						<div className={`text-lg font-semibold ${worstTradeColor}`}>
							{data.worst_trade_loss !== null ? formatMoney(data.worst_trade_loss) : 'N/A'}
						</div>
						<div className="text-xs text-[var(--muted)] mt-1">{data.worst_trade_symbol || '-'}</div>
					</div>
				</div>
			</div>
		</div>
	);
}
