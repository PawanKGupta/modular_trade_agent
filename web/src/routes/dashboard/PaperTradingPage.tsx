import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPaperTradingPortfolio } from '@/api/paper-trading';
import type { PaperTradingPortfolio } from '@/api/paper-trading';

function formatMoney(amount: number): string {
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
	return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function PaperTradingPage() {
	const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<PaperTradingPortfolio>({
		queryKey: ['paper-trading-portfolio'],
		queryFn: getPaperTradingPortfolio,
		refetchInterval: 5000, // Refresh every 5 seconds for live P&L
	});

	useEffect(() => {
		document.title = 'Paper Trading Portfolio';
	}, []);

	// Format last update time
	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

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

	const { account, holdings, recent_orders, order_statistics } = data;

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
					<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Paper Trading Portfolio</h1>
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
						<div className="text-xs sm:text-sm text-[var(--muted)]">Initial Capital</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.initial_capital)}
						</div>
					</div>
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
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Target</th>
									<th className="text-right p-2 whitespace-nowrap hidden lg:table-cell">To Target</th>
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
											{h.target_price ? (
												<span className="font-mono">
													{h.target_price.toLocaleString('en-IN', {
														minimumFractionDigits: 2,
														maximumFractionDigits: 2,
													})}
												</span>
											) : (
												<span className="text-[var(--muted)]">-</span>
											)}
										</td>
										<td className={`p-2 text-right ${
											h.distance_to_target !== null
												? h.distance_to_target >= 0
													? 'text-yellow-400'
													: 'text-blue-400'
												: 'text-[var(--muted)]'
										}`}>
											{h.distance_to_target !== null ? (
												<span title={h.distance_to_target >= 0 ? 'Below target' : 'Above target'}>
													{formatPercent(Math.abs(h.distance_to_target))}
													{h.distance_to_target >= 0 ? ' ↑' : ' ✓'}
												</span>
											) : (
												<span>-</span>
											)}
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

			{/* Order Statistics */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Order Statistics</div>
				</div>
				<div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Total Orders</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{order_statistics.total_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Buy Orders</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{order_statistics.buy_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Sell Orders</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{order_statistics.sell_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Success Rate</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{order_statistics.success_rate.toFixed(2)}%
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Completed</div>
						<div className="text-base sm:text-lg font-semibold text-green-400">
							{order_statistics.completed_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Pending</div>
						<div className="text-base sm:text-lg font-semibold text-yellow-400">
							{order_statistics.pending_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Cancelled</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--muted)]">
							{order_statistics.cancelled_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Rejected</div>
						<div className="text-base sm:text-lg font-semibold text-red-400">
							{order_statistics.rejected_orders}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Re-entries</div>
						<div className="text-base sm:text-lg font-semibold text-yellow-400">
							{order_statistics.reentry_orders}
						</div>
					</div>
				</div>
			</div>

			{/* Recent Orders */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">
						Recent Orders (Last 50)
					</div>
				</div>
				{recent_orders.length === 0 ? (
					<div className="p-4 text-[var(--muted)]">No orders</div>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2">Time</th>
									<th className="text-left p-2">Symbol</th>
									<th className="text-left p-2">Side</th>
									<th className="text-left p-2">Type</th>
									<th className="text-right p-2">Qty</th>
									<th className="text-right p-2">Price (Rs)</th>
									<th className="text-left p-2">Status</th>
								</tr>
							</thead>
							<tbody>
								{recent_orders.map((order) => (
									<tr key={order.order_id} className="border-t border-[#1e293b]">
										<td className="p-2 text-[var(--text)]">
											{new Date(order.created_at).toLocaleString()}
										</td>
										<td className="p-2 text-[var(--text)] font-medium">{order.symbol}</td>
										<td className="p-2">
											<div className="flex items-center gap-2">
												<span
													className={`px-2 py-0.5 rounded text-xs font-medium ${
														order.transaction_type === 'BUY'
															? 'bg-green-500/20 text-green-400'
															: 'bg-red-500/20 text-red-400'
													}`}
												>
													{order.transaction_type}
												</span>
												{order.metadata?.entry_type === 'REENTRY' && (
													<span
														className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400 cursor-help"
														title={`Re-entry at RSI ${order.metadata.rsi_value} (Level ${order.metadata.rsi_level})`}
													>
														Re-entry
													</span>
												)}
											</div>
										</td>
										<td className="p-2">
											<span className="px-2 py-0.5 rounded text-xs bg-blue-500/20 text-blue-400">
												{order.order_type}
											</span>
										</td>
										<td className="p-2 text-right text-[var(--text)]">{order.quantity}</td>
										<td className="p-2 text-right text-[var(--text)]">
											{order.execution_price ? (
												<span className="font-mono">
													{order.execution_price.toLocaleString('en-IN', {
														minimumFractionDigits: 2,
														maximumFractionDigits: 2,
													})}
												</span>
											) : (
												'-'
											)}
										</td>
										<td className="p-2">
											<span
												className={`px-2 py-1 rounded text-xs ${
													order.status === 'COMPLETE'
														? 'bg-green-500/20 text-green-400'
														: order.status === 'REJECTED'
															? 'bg-red-500/20 text-red-400'
															: order.status === 'CANCELLED'
																? 'bg-gray-500/20 text-gray-400'
																: 'bg-yellow-500/20 text-yellow-400'
												}`}
											>
												{order.status}
											</span>
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
