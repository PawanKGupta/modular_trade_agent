import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPaperTradingHistory } from '@/api/paper-trading';
import type { TradeHistory } from '@/api/paper-trading';

function formatMoney(amount: number): string {
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
	return `${value.toFixed(2)}%`;
}

function formatDate(dateStr: string): string {
	try {
		return new Date(dateStr).toLocaleString('en-IN', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	} catch {
		return dateStr;
	}
}

export function PaperTradingHistoryPage() {
	const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<TradeHistory>({
		queryKey: ['paper-trading-history'],
		queryFn: getPaperTradingHistory,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	useEffect(() => {
		document.title = 'Trade History - Paper Trading';
	}, []);

	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

	if (error) {
		return (
			<div className="p-4">
				<div className="text-red-400">Failed to load trade history</div>
			</div>
		);
	}

	return (
		<div className="p-4 space-y-4">
			{/* Header */}
			<div className="flex items-center justify-between">
				<div className="flex items-center gap-3">
					<h1 className="text-xl font-semibold text-[var(--text)]">Trade History</h1>
					<div className="flex items-center gap-2">
						<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
						<span className="text-xs text-[var(--muted)]">Live • Last update: {lastUpdate}</span>
					</div>
				</div>
				<button
					onClick={() => refetch()}
					className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
				>
					Refresh
				</button>
			</div>

			{isLoading && (
				<div className="text-center py-8 text-[var(--muted)]">Loading trade history...</div>
			)}

			{data && (
				<>
					{/* Statistics Cards */}
					<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
							<div className="text-sm text-[var(--muted)]">Total Trades</div>
							<div className="text-2xl font-semibold text-[var(--text)]">
								{data.statistics.total_trades}
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
							<div className="text-sm text-[var(--muted)]">Win Rate</div>
							<div className="text-2xl font-semibold text-green-400">
								{formatPercent(data.statistics.win_rate)}
							</div>
							<div className="text-xs text-[var(--muted)] mt-1">
								{data.statistics.profitable_trades}W / {data.statistics.losing_trades}L
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
							<div className="text-sm text-[var(--muted)]">Net P&L</div>
							<div
								className={`text-2xl font-semibold ${data.statistics.net_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
							>
								{formatMoney(data.statistics.net_pnl)}
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
							<div className="text-sm text-[var(--muted)]">Avg P&L per Trade</div>
							<div
								className={`text-xl font-semibold ${data.statistics.net_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
							>
								{formatMoney(
									data.statistics.total_trades > 0
										? data.statistics.net_pnl / data.statistics.total_trades
										: 0
								)}
							</div>
						</div>
					</div>

					{/* Closed Positions */}
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
						<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
							<div className="font-medium text-[var(--text)]">
								Closed Positions ({data.closed_positions.length})
							</div>
						</div>

						{data.closed_positions.length === 0 && (
							<div className="p-4 text-center text-[var(--muted)]">No closed positions yet</div>
						)}

						{data.closed_positions.length > 0 && (
							<div className="overflow-x-auto">
								<table className="w-full text-sm">
									<thead className="bg-[#0f172a] text-[var(--muted)]">
										<tr>
											<th className="text-left p-2">Symbol</th>
											<th className="text-right p-2">Entry</th>
											<th className="text-right p-2">Exit</th>
											<th className="text-right p-2">Qty</th>
											<th className="text-right p-2">Days</th>
											<th className="text-right p-2">P&L</th>
											<th className="text-right p-2">P&L %</th>
											<th className="text-right p-2">Charges</th>
											<th className="text-left p-2">Entry Date</th>
											<th className="text-left p-2">Exit Date</th>
										</tr>
									</thead>
									<tbody>
										{data.closed_positions
											.sort(
												(a, b) =>
													new Date(b.sell_date).getTime() - new Date(a.sell_date).getTime()
											)
											.map((position, idx) => (
												<tr key={idx} className="border-t border-[#1e293b]">
													<td className="p-2 text-[var(--text)] font-medium">
														{position.symbol}
													</td>
													<td className="p-2 text-right text-[var(--text)]">
														{formatMoney(position.entry_price)}
													</td>
													<td className="p-2 text-right text-[var(--text)]">
														{formatMoney(position.exit_price)}
													</td>
													<td className="p-2 text-right text-[var(--text)]">
														{position.quantity}
													</td>
													<td className="p-2 text-right text-[var(--text)]">
														{position.holding_days}
													</td>
													<td
														className={`p-2 text-right font-medium ${position.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
													>
														{formatMoney(position.realized_pnl)}
													</td>
													<td
														className={`p-2 text-right font-medium ${position.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}
													>
														{formatPercent(position.pnl_percentage)}
													</td>
													<td className="p-2 text-right text-[var(--muted)]">
														{formatMoney(position.charges)}
													</td>
													<td className="p-2 text-[var(--text)] text-xs">
														{formatDate(position.buy_date)}
													</td>
													<td className="p-2 text-[var(--text)] text-xs">
														{formatDate(position.sell_date)}
													</td>
												</tr>
											))}
									</tbody>
								</table>
							</div>
						)}
					</div>

					{/* All Transactions */}
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
						<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
							<div className="font-medium text-[var(--text)]">
								All Transactions ({data.transactions.length})
							</div>
						</div>

						{data.transactions.length === 0 && (
							<div className="p-4 text-center text-[var(--muted)]">No transactions yet</div>
						)}

						{data.transactions.length > 0 && (
							<div className="overflow-x-auto">
								<table className="w-full text-sm">
									<thead className="bg-[#0f172a] text-[var(--muted)]">
										<tr>
											<th className="text-left p-2">Time</th>
											<th className="text-left p-2">Symbol</th>
											<th className="text-left p-2">Type</th>
											<th className="text-right p-2">Qty</th>
											<th className="text-right p-2">Price</th>
											<th className="text-right p-2">Value</th>
											<th className="text-right p-2">P&L</th>
											<th className="text-right p-2">Charges</th>
											<th className="text-left p-2">Reason</th>
										</tr>
									</thead>
									<tbody>
										{data.transactions
											.sort(
												(a, b) =>
													new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
											)
											.map((txn, idx) => (
												<tr key={idx} className="border-t border-[#1e293b]">
													<td className="p-2 text-[var(--text)] text-xs">
														{formatDate(txn.timestamp)}
													</td>
													<td className="p-2 text-[var(--text)] font-medium">{txn.symbol}</td>
													<td className="p-2">
														<span
															className={`px-2 py-0.5 rounded text-xs font-medium ${
																txn.transaction_type === 'BUY'
																	? 'bg-green-500/20 text-green-400'
																	: 'bg-red-500/20 text-red-400'
															}`}
														>
															{txn.transaction_type}
														</span>
													</td>
													<td className="p-2 text-right text-[var(--text)]">{txn.quantity}</td>
													<td className="p-2 text-right text-[var(--text)]">
														{formatMoney(txn.price)}
													</td>
													<td className="p-2 text-right text-[var(--text)]">
														{formatMoney(txn.order_value)}
													</td>
													<td className="p-2 text-right">
														{txn.transaction_type === 'SELL' && txn.realized_pnl !== undefined ? (
															<div>
																<div
																	className={`font-medium ${txn.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
																>
																	{formatMoney(txn.realized_pnl)}
																</div>
																{txn.pnl_percentage !== undefined && (
																	<div
																		className={`text-xs ${txn.realized_pnl >= 0 ? 'text-green-400/70' : 'text-red-400/70'}`}
																	>
																		({formatPercent(txn.pnl_percentage)})
																	</div>
																)}
															</div>
														) : (
															<span className="text-[var(--muted)]">-</span>
														)}
													</td>
													<td className="p-2 text-right text-[var(--muted)]">
														{formatMoney(txn.charges)}
													</td>
													<td className="p-2">
														{txn.exit_reason ? (
															<span
																className={`px-2 py-0.5 rounded text-xs ${
																	txn.exit_reason === 'Target Hit'
																		? 'bg-green-500/20 text-green-400'
																		: txn.exit_reason === 'RSI > 50'
																			? 'bg-yellow-500/20 text-yellow-400'
																			: 'bg-blue-500/20 text-blue-400'
																}`}
															>
																{txn.exit_reason}
															</span>
														) : (
															<span className="text-[var(--muted)] text-xs">-</span>
														)}
													</td>
												</tr>
											))}
									</tbody>
								</table>
							</div>
						)}
					</div>
				</>
			)}
		</div>
	);
}
