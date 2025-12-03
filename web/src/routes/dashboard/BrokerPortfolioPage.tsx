import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortfolio, type PaperTradingPortfolio } from '@/api/user';
import { useSettings } from '@/hooks/useSettings';

function formatMoney(amount: number): string {
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
	return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function BrokerPortfolioPage() {
	const { isBrokerMode, isBrokerConnected, broker } = useSettings();

	const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<PaperTradingPortfolio>({
		queryKey: ['portfolio', 'broker'],
		queryFn: getPortfolio,
		refetchInterval: 5000, // Refresh every 5 seconds for live P&L
		enabled: isBrokerMode && isBrokerConnected, // Only fetch if in broker mode and connected
	});

	useEffect(() => {
		document.title = 'Broker Portfolio';
	}, []);

	// Format last update time
	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

	if (!isBrokerMode) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-yellow-400">
					Broker portfolio is only available in broker mode. Please switch to broker mode in settings.
				</div>
			</div>
		);
	}

	if (!isBrokerConnected) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-yellow-400">
					Broker is not connected. Please configure and connect your broker in settings.
				</div>
			</div>
		);
	}

	if (isLoading) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-[var(--text)]">Loading portfolio...</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-red-400">Error loading portfolio: {String(error)}</div>
				<button
					onClick={() => refetch()}
					className="mt-2 px-4 py-3 sm:py-2 bg-[var(--accent)] text-white rounded hover:opacity-90 text-sm sm:text-base min-h-[44px] sm:min-h-0"
				>
					Retry
				</button>
			</div>
		);
	}

	if (!data) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-[var(--muted)]">No portfolio data available</div>
			</div>
		);
	}

	const { account, holdings } = data;

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
					<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">
						Broker Portfolio {broker ? `(${broker.toUpperCase()})` : ''}
					</h1>
					<div className="flex items-center gap-2">
						<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
						<span className="text-xs text-[var(--muted)]">
							Live • Last update: {lastUpdate}
						</span>
					</div>
				</div>
				<button
					onClick={() => refetch()}
					className="px-3 py-2 sm:py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90 min-h-[44px] sm:min-h-0 w-full sm:w-auto"
				>
					Refresh
				</button>
			</div>

			{/* Account Summary */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">Account Summary</div>
				</div>
				<div className="p-3 sm:p-4 grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Available Cash</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.available_cash)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Portfolio Value</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.portfolio_value)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Total Value</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.total_value)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Total P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.total_pnl)} ({formatPercent(account.return_percentage)})
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Realized P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.realized_pnl)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Unrealized P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.unrealized_pnl)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Return</div>
						<div
							className={`text-lg font-semibold ${
								account.return_percentage >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatPercent(account.return_percentage)}
						</div>
					</div>
				</div>
			</div>

			{/* Holdings */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">
						Holdings ({holdings.length})
					</div>
				</div>
				{holdings.length === 0 ? (
					<div className="p-3 sm:p-4 text-xs sm:text-sm text-[var(--muted)]">No holdings</div>
				) : (
					<div className="overflow-x-auto -mx-2 sm:mx-0">
						<table className="w-full text-xs sm:text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2 whitespace-nowrap">Symbol</th>
									<th className="text-right p-2 whitespace-nowrap">Qty</th>
									<th className="text-right p-2 whitespace-nowrap hidden sm:table-cell">Avg Price</th>
									<th className="text-right p-2 whitespace-nowrap">Current</th>
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Market Value</th>
									<th className="text-right p-2 whitespace-nowrap">P&L</th>
									<th className="text-right p-2 whitespace-nowrap">P&L %</th>
								</tr>
							</thead>
							<tbody>
								{holdings.map((h) => (
									<tr key={h.symbol} className="border-t border-[#1e293b]">
										<td className="p-2 text-[var(--text)] font-medium">{h.symbol}</td>
										<td className="p-2 text-right text-[var(--text)]">{h.quantity}</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.average_price.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.current_price.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.market_value.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td
											className={`p-2 text-right font-medium ${
												h.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											<span className="font-mono">
												{h.pnl.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td
											className={`p-2 text-right font-medium ${
												h.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatPercent(h.pnl_percentage)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</div>
		</div>
	);
}
