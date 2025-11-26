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
	const { data, isLoading, error, refetch } = useQuery<PaperTradingPortfolio>({
		queryKey: ['paper-trading-portfolio'],
		queryFn: getPaperTradingPortfolio,
		refetchInterval: 5000, // Refresh every 5 seconds for live P&L
	});

	useEffect(() => {
		document.title = 'Paper Trading Portfolio';
	}, []);

	if (isLoading) {
		return (
			<div className="p-4">
				<div className="text-[var(--text)]">Loading portfolio...</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="p-4">
				<div className="text-red-400">Error loading portfolio: {String(error)}</div>
				<button
					onClick={() => refetch()}
					className="mt-2 px-4 py-2 bg-[var(--accent)] text-white rounded hover:opacity-90"
				>
					Retry
				</button>
			</div>
		);
	}

	if (!data) {
		return (
			<div className="p-4">
				<div className="text-[var(--muted)]">No portfolio data available</div>
			</div>
		);
	}

	const { account, holdings, recent_orders, order_statistics } = data;

	return (
		<div className="p-4 space-y-4">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold text-[var(--text)]">Paper Trading Portfolio</h1>
				<button
					onClick={() => refetch()}
					className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
				>
					Refresh
				</button>
			</div>

			{/* Account Summary */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Account Summary</div>
				</div>
				<div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
					<div>
						<div className="text-sm text-[var(--muted)]">Initial Capital</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.initial_capital)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Available Cash</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.available_cash)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Portfolio Value</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.portfolio_value)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Total Value</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.total_value)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Total P&L</div>
						<div
							className={`text-lg font-semibold ${
								account.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.total_pnl)} ({formatPercent(account.return_percentage)})
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Realized P&L</div>
						<div
							className={`text-lg font-semibold ${
								account.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.realized_pnl)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Unrealized P&L</div>
						<div
							className={`text-lg font-semibold ${
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
					<div className="font-medium text-[var(--text)]">
						Holdings ({holdings.length})
					</div>
				</div>
				{holdings.length === 0 ? (
					<div className="p-4 text-[var(--muted)]">No holdings</div>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2">Symbol</th>
									<th className="text-right p-2">Quantity</th>
									<th className="text-right p-2">Avg Price</th>
									<th className="text-right p-2">Current</th>
									<th className="text-right p-2">Target</th>
									<th className="text-right p-2">To Target</th>
									<th className="text-right p-2">Market Value</th>
									<th className="text-right p-2">P&L</th>
									<th className="text-right p-2">P&L %</th>
								</tr>
							</thead>
							<tbody>
								{holdings.map((h) => (
									<tr key={h.symbol} className="border-t border-[#1e293b]">
										<td className="p-2 text-[var(--text)] font-medium">{h.symbol}</td>
										<td className="p-2 text-right text-[var(--text)]">{h.quantity}</td>
										<td className="p-2 text-right text-[var(--text)]">
											{formatMoney(h.average_price)}
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											{formatMoney(h.current_price)}
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											{h.target_price ? formatMoney(h.target_price) : (
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
											{formatMoney(h.market_value)}
										</td>
										<td
											className={`p-2 text-right font-medium ${
												h.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatMoney(h.pnl)}
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
						<div className="text-sm text-[var(--muted)]">Total Orders</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{order_statistics.total_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Buy Orders</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{order_statistics.buy_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Sell Orders</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{order_statistics.sell_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Success Rate</div>
						<div className="text-lg font-semibold text-[var(--text)]">
							{order_statistics.success_rate.toFixed(2)}%
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Completed</div>
						<div className="text-lg font-semibold text-green-400">
							{order_statistics.completed_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Pending</div>
						<div className="text-lg font-semibold text-yellow-400">
							{order_statistics.pending_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Cancelled</div>
						<div className="text-lg font-semibold text-[var(--muted)]">
							{order_statistics.cancelled_orders}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Rejected</div>
						<div className="text-lg font-semibold text-red-400">
							{order_statistics.rejected_orders}
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
									<th className="text-left p-2">Type</th>
									<th className="text-right p-2">Qty</th>
									<th className="text-right p-2">Price</th>
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
										<td className="p-2 text-[var(--text)]">{order.transaction_type}</td>
										<td className="p-2 text-right text-[var(--text)]">{order.quantity}</td>
										<td className="p-2 text-right text-[var(--text)]">
											{order.execution_price
												? formatMoney(order.execution_price)
												: '-'}
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
