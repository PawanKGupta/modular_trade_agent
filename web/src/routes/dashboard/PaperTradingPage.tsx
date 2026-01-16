import { useEffect, useState } from 'react';
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
	const [ordersPage, setOrdersPage] = useState(1);
	const [ordersPageSize, setOrdersPageSize] = useState(10);

	const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<PaperTradingPortfolio>({
		queryKey: ['paper-trading-portfolio', ordersPage, ordersPageSize],
		queryFn: () => getPaperTradingPortfolio({ page: ordersPage, page_size: ordersPageSize }),
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
	// Ensure recent_orders has items array for backward compatibility
	const recentOrdersItems = recent_orders.items || [];

	// Debug: Log holdings with reentry data
	if (holdings.length > 0) {
		console.log('Holdings with reentry data:', holdings.map(h => ({
			symbol: h.symbol,
			reentry_count: h.reentry_count,
			reentries: h.reentries,
			entry_rsi: h.entry_rsi
		})));
	}

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
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Re-entries</th>
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
										<td className="p-2 text-right text-[var(--text)] hidden md:table-cell">
											{(h.reentry_count && h.reentry_count > 0) || (h.reentries && h.reentries.length > 0) ? (
												<div className="flex flex-col items-end gap-1">
													{h.reentry_count && h.reentry_count > 0 && (
														<span className="text-xs font-medium text-yellow-400">
															{h.reentry_count} re-entry{h.reentry_count !== 1 ? 's' : ''}
														</span>
													)}
													{h.entry_rsi !== null && h.entry_rsi !== undefined && (
														<span className="text-xs text-[var(--muted)]">
															Entry RSI: {h.entry_rsi.toFixed(1)}
														</span>
													)}
													{h.reentries && h.reentries.length > 0 && (
														<details className="text-xs">
															<summary className="cursor-pointer text-yellow-400 hover:text-yellow-300">
																View details
															</summary>
															<div className="mt-1 space-y-1 text-left max-w-xs">
																{h.reentries.map((re, idx) => (
																	<div key={idx} className="text-[var(--muted)] border-b border-[#1e293b]/50 pb-1 mb-1 last:border-0 last:mb-0">
																		<div className="font-medium">
																			Re-entry {idx + 1}: {re.qty} @ Rs {typeof re.price === 'number' ? re.price.toFixed(2) : re.price}
																		</div>
																		{re.level && (
																			<div className="text-xs">
																				Level: {re.level} {re.rsi && `(RSI: ${typeof re.rsi === 'number' ? re.rsi.toFixed(1) : re.rsi})`}
																			</div>
																		)}
																		{re.time && (
																			<div className="text-xs">
																				{new Date(re.time).toLocaleDateString()}
																			</div>
																		)}
																	</div>
																))}
															</div>
														</details>
													)}
												</div>
											) : (
												<span className="text-[var(--muted)]">-</span>
											)}
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
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">
						Recent Orders ({recent_orders.total || 0})
					</div>
					<div className="flex items-center gap-2 text-xs sm:text-sm">
						<select
							value={ordersPageSize}
							onChange={(e) => {
								setOrdersPageSize(Number(e.target.value));
								setOrdersPage(1);
							}}
							className="bg-[var(--bg)] border border-[#1e293b] rounded px-2 py-1 text-[var(--text)]"
						>
							<option value={10}>10 per page</option>
							<option value={25}>25 per page</option>
							<option value={50}>50 per page</option>
							<option value={100}>100 per page</option>
						</select>
					</div>
				</div>
				{recentOrdersItems.length === 0 ? (
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
								{recentOrdersItems.map((order) => (
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
				{recent_orders.total_pages > 1 && (
					<div className="flex flex-col sm:flex-row items-center justify-between gap-2 p-3 border-t border-[#1e293b]">
						<div className="text-xs sm:text-sm text-[var(--muted)]">
							Showing {((ordersPage - 1) * ordersPageSize) + 1} to{' '}
							{Math.min(ordersPage * ordersPageSize, recent_orders.total)} of{' '}
							{recent_orders.total} orders
						</div>
						<div className="flex items-center gap-1">
							<button
								onClick={() => setOrdersPage(1)}
								disabled={ordersPage === 1}
								className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
							>
								First
							</button>
							<button
								onClick={() => setOrdersPage((p) => Math.max(1, p - 1))}
								disabled={ordersPage === 1}
								className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
							>
								Previous
							</button>
							<div className="flex items-center gap-1">
								{Array.from({ length: Math.min(5, recent_orders.total_pages) }, (_, i) => {
									let pageNum: number;
									if (recent_orders.total_pages <= 5) {
										pageNum = i + 1;
									} else if (ordersPage <= 3) {
										pageNum = i + 1;
									} else if (ordersPage >= recent_orders.total_pages - 2) {
										pageNum = recent_orders.total_pages - 4 + i;
									} else {
										pageNum = ordersPage - 2 + i;
									}
									return (
										<button
											key={pageNum}
											onClick={() => setOrdersPage(pageNum)}
											className={`px-2 py-1 text-xs sm:text-sm border rounded ${
												ordersPage === pageNum
													? 'bg-blue-600 text-white border-blue-600'
													: 'bg-[var(--bg)] border-[#1e293b] text-[var(--text)] hover:bg-[#0f1720]'
											}`}
										>
											{pageNum}
										</button>
									);
								})}
							</div>
							<button
								onClick={() => setOrdersPage((p) => Math.min(recent_orders.total_pages, p + 1))}
								disabled={ordersPage === recent_orders.total_pages}
								className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
							>
								Next
							</button>
							<button
								onClick={() => setOrdersPage(recent_orders.total_pages)}
								disabled={ordersPage === recent_orders.total_pages}
								className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
							>
								Last
							</button>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
