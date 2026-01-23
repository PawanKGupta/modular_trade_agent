import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPaperTradingHistory } from '@/api/paper-trading';
import { exportTradeHistory } from '@/api/export';
import { ExportButton } from '@/components/ExportButton';
import { DateRangePicker, type DateRange } from '@/components/DateRangePicker';
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

function getDefaultDateRange(): DateRange {
	const endDate = new Date();
	const startDate = new Date();
	startDate.setDate(startDate.getDate() - 90); // Last 90 days

	return {
		startDate: startDate.toISOString().split('T')[0],
		endDate: endDate.toISOString().split('T')[0],
	};
}

export function PaperTradingHistoryPage() {
	const [showExportOptions, setShowExportOptions] = useState(false);
	const [exportDateRange, setExportDateRange] = useState<DateRange>(getDefaultDateRange());
	const [positionsPage, setPositionsPage] = useState(1);
	const [positionsPageSize, setPositionsPageSize] = useState(10);
	const [transactionsPage, setTransactionsPage] = useState(1);
	const [transactionsPageSize, setTransactionsPageSize] = useState(10);

	const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<TradeHistory>({
		queryKey: ['paper-trading-history', positionsPage, positionsPageSize, transactionsPage, transactionsPageSize],
		queryFn: () => getPaperTradingHistory({
			positions_page: positionsPage,
			positions_page_size: positionsPageSize,
			transactions_page: transactionsPage,
			transactions_page_size: transactionsPageSize,
		}),
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	useEffect(() => {
		document.title = 'Trade History - Paper Trading';
	}, []);

	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

	const handleExport = async () => {
		await exportTradeHistory({
			startDate: exportDateRange.startDate,
			endDate: exportDateRange.endDate,
			tradeMode: 'paper',
		});
	};

	if (error) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-red-400">Failed to load trade history</div>
			</div>
		);
	}

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			{/* Header */}
			<div className="flex flex-col gap-3">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
					<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
						<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Trade History</h1>
						<div className="flex items-center gap-2">
							<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
							<span className="text-xs text-[var(--muted)]">Live • Last update: {lastUpdate}</span>
						</div>
					</div>
					<div className="flex items-center gap-2 w-full sm:w-auto">
						<button
							onClick={() => setShowExportOptions(!showExportOptions)}
							className="px-3 py-2 sm:py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 flex-1 sm:flex-initial min-h-[44px] sm:min-h-0"
						>
							Export {showExportOptions ? '▲' : '▼'}
						</button>
						<button
							onClick={() => refetch()}
							className="px-3 py-2 sm:py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90 flex-1 sm:flex-initial min-h-[44px] sm:min-h-0"
						>
							Refresh
						</button>
					</div>
				</div>

				{/* Export Options Panel */}
				{showExportOptions && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
						<h3 className="text-sm font-medium text-[var(--text)] mb-3">Export Trade History</h3>
						<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
							<DateRangePicker value={exportDateRange} onChange={setExportDateRange} />
							<ExportButton onExport={handleExport} label="Download CSV" />
						</div>
						<p className="text-xs text-[var(--muted)] mt-2">
							Export closed trades with entry/exit prices, P&L, holding periods, and fees.
						</p>
					</div>
				)}
			</div>

			{isLoading && (
				<div className="text-center py-6 sm:py-8 text-xs sm:text-sm text-[var(--muted)]">Loading trade history...</div>
			)}

			{data && (
				<>
					{/* Statistics Cards */}
					<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3 sm:p-4">
							<div className="text-xs sm:text-sm text-[var(--muted)]">Total Trades</div>
							<div className="text-xl sm:text-2xl font-semibold text-[var(--text)]">
								{data.statistics.total_trades}
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3 sm:p-4">
							<div className="text-xs sm:text-sm text-[var(--muted)]">Win Rate</div>
							<div className="text-xl sm:text-2xl font-semibold text-green-400">
								{formatPercent(data.statistics.win_rate)}
							</div>
							<div className="text-xs text-[var(--muted)] mt-1">
								{data.statistics.profitable_trades}W / {data.statistics.losing_trades}L
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3 sm:p-4">
							<div className="text-xs sm:text-sm text-[var(--muted)]">Net P&L</div>
							<div
								className={`text-xl sm:text-2xl font-semibold ${data.statistics.net_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
							>
								{formatMoney(data.statistics.net_pnl)}
							</div>
						</div>

						<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3 sm:p-4">
							<div className="text-xs sm:text-sm text-[var(--muted)]">Avg P&L per Trade</div>
							<div
								className={`text-lg sm:text-xl font-semibold ${data.statistics.net_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
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
						<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
							<div className="font-medium text-sm sm:text-base text-[var(--text)]">
								Closed Positions ({data.closed_positions.total || 0})
							</div>
							<div className="flex items-center gap-2 text-xs sm:text-sm">
								<select
									value={positionsPageSize}
									onChange={(e) => {
										setPositionsPageSize(Number(e.target.value));
										setPositionsPage(1);
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

						{data.closed_positions.items?.length === 0 && (
							<div className="p-3 sm:p-4 text-center text-xs sm:text-sm text-[var(--muted)]">No closed positions yet</div>
						)}

						{data.closed_positions.items && data.closed_positions.items.length > 0 && (
							<div className="overflow-x-auto -mx-2 sm:mx-0">
								<table className="w-full text-xs sm:text-sm">
									<thead className="bg-[#0f172a] text-[var(--muted)]">
										<tr>
											<th className="text-left p-2 whitespace-nowrap">Symbol</th>
											<th className="text-right p-2 whitespace-nowrap">Entry</th>
											<th className="text-right p-2 whitespace-nowrap">Exit</th>
											<th className="text-right p-2 whitespace-nowrap">Qty</th>
											<th className="text-right p-2 whitespace-nowrap hidden sm:table-cell">Days</th>
											<th className="text-right p-2 whitespace-nowrap">P&L</th>
											<th className="text-right p-2 whitespace-nowrap">P&L %</th>
											<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Charges</th>
											<th className="text-left p-2 whitespace-nowrap hidden lg:table-cell">Entry Date</th>
											<th className="text-left p-2 whitespace-nowrap hidden lg:table-cell">Exit Date</th>
										</tr>
									</thead>
									<tbody>
										{data.closed_positions.items.map((position, idx) => (
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
													<td className="p-2 text-right text-[var(--text)] hidden sm:table-cell">
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
													<td className="p-2 text-right text-[var(--muted)] hidden md:table-cell">
														{formatMoney(position.charges)}
													</td>
													<td className="p-2 text-[var(--text)] text-xs hidden lg:table-cell">
														{formatDate(position.buy_date)}
													</td>
													<td className="p-2 text-[var(--text)] text-xs hidden lg:table-cell">
														{formatDate(position.sell_date)}
													</td>
												</tr>
											))}
									</tbody>
								</table>
							</div>
						)}
						{data.closed_positions.total_pages > 1 && (
							<div className="flex flex-col sm:flex-row items-center justify-between gap-2 p-3 border-t border-[#1e293b]">
								<div className="text-xs sm:text-sm text-[var(--muted)]">
									Showing {((positionsPage - 1) * positionsPageSize) + 1} to{' '}
									{Math.min(positionsPage * positionsPageSize, data.closed_positions.total)} of{' '}
									{data.closed_positions.total} positions
								</div>
								<div className="flex items-center gap-1">
									<button
										onClick={() => setPositionsPage(1)}
										disabled={positionsPage === 1}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										First
									</button>
									<button
										onClick={() => setPositionsPage((p) => Math.max(1, p - 1))}
										disabled={positionsPage === 1}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Previous
									</button>
									<div className="flex items-center gap-1">
										{Array.from({ length: Math.min(5, data.closed_positions.total_pages) }, (_, i) => {
											let pageNum: number;
											if (data.closed_positions.total_pages <= 5) {
												pageNum = i + 1;
											} else if (positionsPage <= 3) {
												pageNum = i + 1;
											} else if (positionsPage >= data.closed_positions.total_pages - 2) {
												pageNum = data.closed_positions.total_pages - 4 + i;
											} else {
												pageNum = positionsPage - 2 + i;
											}
											return (
												<button
													key={pageNum}
													onClick={() => setPositionsPage(pageNum)}
													className={`px-2 py-1 text-xs sm:text-sm border rounded ${
														positionsPage === pageNum
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
										onClick={() => setPositionsPage((p) => Math.min(data.closed_positions.total_pages, p + 1))}
										disabled={positionsPage === data.closed_positions.total_pages}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Next
									</button>
									<button
										onClick={() => setPositionsPage(data.closed_positions.total_pages)}
										disabled={positionsPage === data.closed_positions.total_pages}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Last
									</button>
								</div>
							</div>
						)}
					</div>

					{/* All Transactions */}
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
						<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
							<div className="font-medium text-sm sm:text-base text-[var(--text)]">
								All Transactions ({data.transactions.total || 0})
							</div>
							<div className="flex items-center gap-2 text-xs sm:text-sm">
								<select
									value={transactionsPageSize}
									onChange={(e) => {
										setTransactionsPageSize(Number(e.target.value));
										setTransactionsPage(1);
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

						{data.transactions.items?.length === 0 && (
							<div className="p-3 sm:p-4 text-center text-xs sm:text-sm text-[var(--muted)]">No transactions yet</div>
						)}

						{data.transactions.items && data.transactions.items.length > 0 && (
							<div className="overflow-x-auto -mx-2 sm:mx-0">
								<table className="w-full text-xs sm:text-sm">
									<thead className="bg-[#0f172a] text-[var(--muted)]">
										<tr>
											<th className="text-left p-2 whitespace-nowrap">Time</th>
											<th className="text-left p-2 whitespace-nowrap">Symbol</th>
											<th className="text-left p-2 whitespace-nowrap">Type</th>
											<th className="text-right p-2 whitespace-nowrap">Qty</th>
											<th className="text-right p-2 whitespace-nowrap">Price</th>
											<th className="text-right p-2 whitespace-nowrap hidden sm:table-cell">Value</th>
											<th className="text-right p-2 whitespace-nowrap">P&L</th>
											<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Charges</th>
											<th className="text-left p-2">Reason</th>
										</tr>
									</thead>
									<tbody>
										{data.transactions.items.map((txn, idx) => (
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
						{data.transactions.total_pages > 1 && (
							<div className="flex flex-col sm:flex-row items-center justify-between gap-2 p-3 border-t border-[#1e293b]">
								<div className="text-xs sm:text-sm text-[var(--muted)]">
									Showing {((transactionsPage - 1) * transactionsPageSize) + 1} to{' '}
									{Math.min(transactionsPage * transactionsPageSize, data.transactions.total)} of{' '}
									{data.transactions.total} transactions
								</div>
								<div className="flex items-center gap-1">
									<button
										onClick={() => setTransactionsPage(1)}
										disabled={transactionsPage === 1}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										First
									</button>
									<button
										onClick={() => setTransactionsPage((p) => Math.max(1, p - 1))}
										disabled={transactionsPage === 1}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Previous
									</button>
									<div className="flex items-center gap-1">
										{Array.from({ length: Math.min(5, data.transactions.total_pages) }, (_, i) => {
											let pageNum: number;
											if (data.transactions.total_pages <= 5) {
												pageNum = i + 1;
											} else if (transactionsPage <= 3) {
												pageNum = i + 1;
											} else if (transactionsPage >= data.transactions.total_pages - 2) {
												pageNum = data.transactions.total_pages - 4 + i;
											} else {
												pageNum = transactionsPage - 2 + i;
											}
											return (
												<button
													key={pageNum}
													onClick={() => setTransactionsPage(pageNum)}
													className={`px-2 py-1 text-xs sm:text-sm border rounded ${
														transactionsPage === pageNum
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
										onClick={() => setTransactionsPage((p) => Math.min(data.transactions.total_pages, p + 1))}
										disabled={transactionsPage === data.transactions.total_pages}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Next
									</button>
									<button
										onClick={() => setTransactionsPage(data.transactions.total_pages)}
										disabled={transactionsPage === data.transactions.total_pages}
										className="px-2 py-1 text-xs sm:text-sm bg-[var(--bg)] border border-[#1e293b] rounded disabled:opacity-50 disabled:cursor-not-allowed text-[var(--text)] hover:bg-[#0f1720]"
									>
										Last
									</button>
								</div>
							</div>
						)}
					</div>
				</>
			)}
		</div>
	);
}
