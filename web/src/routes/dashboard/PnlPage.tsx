import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getClosedPositions, getDailyPnl, getPnlSummary, type DailyPnl, type PnlSummary } from '@/api/pnl';
import { exportPnl } from '@/api/export';
import { exportPnlPdf } from '@/api/reports';
import { PnlTrendChart } from '@/components/charts/PnlTrendChart';
import { ExportButton } from '@/components/ExportButton';
import { DateRangePicker, type DateRange } from '@/components/DateRangePicker';

function formatMoney(amount: number | null | undefined): string {
	if (amount == null || isNaN(amount)) {
		return '-';
	}
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getDefaultDateRange(): DateRange {
	const endDate = new Date();
	const startDate = new Date();
	startDate.setDate(startDate.getDate() - 30); // Last 30 days

	return {
		startDate: startDate.toISOString().split('T')[0],
		endDate: endDate.toISOString().split('T')[0],
	};
}

export function PnlPage() {
	const [tradeMode, setTradeMode] = useState<'paper' | 'broker' | undefined>(undefined);
	const [includeUnrealized, setIncludeUnrealized] = useState<boolean>(false);
	const [exportDateRange, setExportDateRange] = useState<DateRange>(getDefaultDateRange());
	const [showExportOptions, setShowExportOptions] = useState(false);
	const [positionsPage, setPositionsPage] = useState(1);
	const [positionsPageSize, setPositionsPageSize] = useState(10);
	const [positionsSortBy, setPositionsSortBy] = useState<'closed_at' | 'symbol' | 'realized_pnl' | 'opened_at'>('closed_at');
	const [positionsSortOrder, setPositionsSortOrder] = useState<'asc' | 'desc'>('desc');
	const [dailySortBy, setDailySortBy] = useState<'date' | 'pnl'>('date');
	const [dailySortOrder, setDailySortOrder] = useState<'asc' | 'desc'>('desc');

	const dailyQ = useQuery<DailyPnl[]>({
		queryKey: ['pnl', 'daily', tradeMode, includeUnrealized],
		queryFn: () => getDailyPnl(undefined, undefined, tradeMode, includeUnrealized),
		refetchInterval: 30000,
	});
	const summaryQ = useQuery<PnlSummary>({
		queryKey: ['pnl', 'summary', tradeMode, includeUnrealized],
		queryFn: () => getPnlSummary(undefined, undefined, tradeMode, includeUnrealized),
		refetchInterval: 30000,
	});

	const closedPositionsQ = useQuery({
		queryKey: ['pnl', 'closed-positions', tradeMode, positionsPage, positionsPageSize, positionsSortBy, positionsSortOrder],
		queryFn: () => getClosedPositions(positionsPage, positionsPageSize, tradeMode, positionsSortBy, positionsSortOrder),
		refetchInterval: 30000,
	});

	useEffect(() => {
		document.title = 'PnL';
	}, []);

	// Reset page when filters change
	useEffect(() => {
		setPositionsPage(1);
	}, [tradeMode, positionsSortBy, positionsSortOrder]);

	// Sort daily P&L data
	const sortedDailyData = useMemo(() => {
		if (!dailyQ.data) return [];
		const sorted = [...dailyQ.data];
		sorted.sort((a, b) => {
			const multiplier = dailySortOrder === 'asc' ? 1 : -1;
			if (dailySortBy === 'pnl') {
				return (a.pnl - b.pnl) * multiplier;
			}
			// Sort by date
			return (new Date(a.date).getTime() - new Date(b.date).getTime()) * multiplier;
		});
		return sorted;
	}, [dailyQ.data, dailySortBy, dailySortOrder]);

	// Format last update time
	const lastUpdate = summaryQ.dataUpdatedAt ? new Date(summaryQ.dataUpdatedAt).toLocaleTimeString() : 'Never';

	// Handle CSV export
	const handleExport = async () => {
		await exportPnl({
			startDate: exportDateRange.startDate,
			endDate: exportDateRange.endDate,
			tradeMode: tradeMode,
			includeUnrealized,
		});
	};

	// Handle PDF export
	const handleExportPdf = async () => {
		await exportPnlPdf({
			period: 'custom',
			startDate: exportDateRange.startDate,
			endDate: exportDateRange.endDate,
			tradeMode: tradeMode,
			includeUnrealized,
		});
	};

	return (
		<div className="p-4 space-y-4">
			<div className="flex flex-col gap-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-3">
						<h1 className="text-xl font-semibold text-[var(--text)]">Profit & Loss</h1>
						<div className="flex items-center gap-2">
							<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
							<span className="text-xs text-[var(--muted)]">
								Live • Last update: {lastUpdate}
							</span>
						</div>
					</div>
					<div className="flex items-center gap-2">
						<button
							onClick={() => setShowExportOptions(!showExportOptions)}
							className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
						>
							Export Options {showExportOptions ? '▲' : '▼'}
						</button>
						<select
							value={tradeMode ?? ''}
							onChange={(e) => {
								const v = e.target.value as 'paper' | 'broker' | '';
								setTradeMode(v === '' ? undefined : v);
							}}
							className="px-2 py-1 text-sm bg-[var(--panel)] border border-[#1e293b] rounded text-[var(--text)]"
						>
							<option value="">All</option>
							<option value="paper">Paper</option>
							<option value="broker">Broker</option>
						</select>
						<label className="flex items-center gap-1 text-sm text-[var(--text)]">
							<input
								type="checkbox"
								checked={includeUnrealized}
								onChange={(e) => setIncludeUnrealized(e.target.checked)}
							/>
							Include Unrealized
						</label>
						<button
							onClick={() => {
								summaryQ.refetch();
								dailyQ.refetch();
								closedPositionsQ.refetch();
							}}
							className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
						>
							Refresh
						</button>
					</div>
				</div>

				{/* Export Options Panel */}
				{showExportOptions && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
						<h3 className="text-sm font-medium text-[var(--text)] mb-3">Export P&L Data</h3>
						<div className="flex items-center gap-4">
							<DateRangePicker value={exportDateRange} onChange={setExportDateRange} />
							<ExportButton onExport={handleExport} label="Download CSV" />
							<ExportButton onExport={handleExportPdf} label="Download PDF" />
						</div>
						<p className="text-xs text-[var(--muted)] mt-2">
							Export will include realized/unrealized P&L, fees, and totals for the selected date range.
						</p>
					</div>
				)}
			</div>

			{/* Summary Section */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Summary</div>
				</div>
				<div className="p-4">
					{summaryQ.isLoading && <div className="text-sm text-[var(--muted)]">Loading summary...</div>}
					{summaryQ.isError && <div className="text-sm text-red-400">Failed to load summary</div>}
					{summaryQ.data && (
						<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
							<div>
								<div className="text-sm text-[var(--muted)]">Total P&L</div>
								<div
									className={`text-2xl font-semibold ${
										summaryQ.data.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
									}`}
								>
									{formatMoney(summaryQ.data.totalPnl)}
								</div>
							</div>
							<div>
								<div className="text-sm text-[var(--muted)]">Profitable Trades</div>
								<div className="text-2xl font-semibold text-green-400">
									{summaryQ.data.tradesGreen}
								</div>
							</div>
							<div>
								<div className="text-sm text-[var(--muted)]">Loss Trades</div>
								<div className="text-2xl font-semibold text-red-400">
									{summaryQ.data.tradesRed}
								</div>
							</div>
						</div>
					)}
				</div>
			</div>

			{/* Detailed Metrics */}
			{summaryQ.data && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
					<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<div className="text-sm text-[var(--muted)]">Total Realized</div>
							<div className="text-xl font-semibold text-[var(--text)]">{formatMoney(summaryQ.data.totalRealizedPnl)}</div>
						</div>
						<div>
							<div className="text-sm text-[var(--muted)]">Total Unrealized</div>
							<div className="text-xl font-semibold text-[var(--text)]">{formatMoney(summaryQ.data.totalUnrealizedPnl)}</div>
						</div>
						<div>
							<div className="text-sm text-[var(--muted)]">Average per Trade</div>
							<div className="text-xl font-semibold text-[var(--text)]">{formatMoney(summaryQ.data.avgTradePnl)}</div>
						</div>
						<div>
							<div className="text-sm text-[var(--muted)]">Min Trade P&L</div>
							<div className="text-xl font-semibold text-[var(--text)]">{formatMoney(summaryQ.data.minTradePnl)}</div>
						</div>
						<div>
							<div className="text-sm text-[var(--muted)]">Max Trade P&L</div>
							<div className="text-xl font-semibold text-[var(--text)]">{formatMoney(summaryQ.data.maxTradePnl)}</div>
						</div>
					</div>
				</div>
			)}

			{/* P&L Trend Chart */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-2 sm:p-4">
				<PnlTrendChart height={420} tradeMode={tradeMode} includeUnrealized={includeUnrealized} />
			</div>

			{/* Daily P&L Section */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Daily P&L</div>
					{dailyQ.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{dailyQ.isError && <span className="text-sm text-red-400">Failed to load</span>}
				</div>
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th
									className="text-left p-2 whitespace-nowrap cursor-pointer hover:bg-[#1e293b]"
									onClick={() => {
										if (dailySortBy === 'date') {
											setDailySortOrder(dailySortOrder === 'asc' ? 'desc' : 'asc');
										} else {
											setDailySortBy('date');
											setDailySortOrder('desc');
										}
									}}
								>
									Date {dailySortBy === 'date' && (dailySortOrder === 'asc' ? '▲' : '▼')}
								</th>
								<th className="text-left p-2 whitespace-nowrap">Symbols</th>
								<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Realized</th>
								<th className="text-right p-2 whitespace-nowrap hidden lg:table-cell">Unrealized</th>
								<th className="text-right p-2 whitespace-nowrap hidden lg:table-cell">Fees</th>
								<th
									className="text-right p-2 whitespace-nowrap cursor-pointer hover:bg-[#1e293b]"
									onClick={() => {
										if (dailySortBy === 'pnl') {
											setDailySortOrder(dailySortOrder === 'asc' ? 'desc' : 'asc');
										} else {
											setDailySortBy('pnl');
											setDailySortOrder('desc');
										}
									}}
								>
									Total P&L {dailySortBy === 'pnl' && (dailySortOrder === 'asc' ? '▲' : '▼')}
								</th>
								<th className="text-right p-2 whitespace-nowrap hidden sm:table-cell">Trades</th>
								<th className="text-right p-2 whitespace-nowrap">Status</th>
							</tr>
						</thead>
						<tbody>
							{sortedDailyData.map((d) => (
								<tr key={d.date} className="border-t border-[#1e293b]">
									<td className="p-2 text-[var(--text)]">
										{new Date(d.date).toLocaleDateString('en-IN', {
											day: 'numeric',
											month: 'short',
											year: 'numeric'
										})}
									</td>
									<td className="p-2 text-[var(--text)] text-xs">
										{d.symbols && d.symbols.length > 0 ? (
											<div className="flex flex-wrap gap-1">
												{d.symbols.slice(0, 3).map((sym) => (
													<span key={sym} className="px-1.5 py-0.5 bg-[#1e293b] rounded text-[var(--text)]">
														{sym.split('-')[0]}
													</span>
												))}
												{d.symbols.length > 3 && (
													<span className="px-1.5 py-0.5 text-[var(--muted)]">
														+{d.symbols.length - 3}
													</span>
												)}
											</div>
										) : '-'}
									</td>
									<td className="p-2 text-right text-[var(--text)] hidden md:table-cell">
										{formatMoney(d.realized_pnl)}
									</td>
									<td className="p-2 text-right text-[var(--text)] hidden lg:table-cell">
										{formatMoney(d.unrealized_pnl)}
									</td>
									<td className="p-2 text-right text-[var(--text)] hidden lg:table-cell">
										{formatMoney(d.fees)}
									</td>
									<td
										className={`p-2 text-right font-medium ${
											(d.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
										}`}
									>
										{formatMoney(d.pnl)}
									</td>
									<td className="p-2 text-right text-[var(--text)] hidden sm:table-cell">
										{d.trades_count !== undefined ? d.trades_count : '-'}
									</td>
									<td className="p-2 text-right">
										<span
											className={`px-2 py-0.5 rounded text-xs ${
												d.pnl >= 0
													? 'bg-green-500/20 text-green-400'
													: 'bg-red-500/20 text-red-400'
											}`}
										>
											{d.pnl >= 0 ? 'Profit' : 'Loss'}
										</span>
									</td>
								</tr>
							))}
							{sortedDailyData.length === 0 && !dailyQ.isLoading && (
								<tr>
									<td className="p-2 text-[var(--muted)] text-center" colSpan={8}>
										No P&L data available
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			{/* Closed Positions Section */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Closed Positions</div>
					{closedPositionsQ.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{closedPositionsQ.isError && <span className="text-sm text-red-400">Failed to load</span>}
				</div>

				{/* Pagination Controls - Top */}
				{closedPositionsQ.data && closedPositionsQ.data.total > 0 && (
					<div className="px-3 py-2 border-b border-[#1e293b] flex items-center justify-between gap-4 flex-wrap">
						<div className="flex items-center gap-2">
							<span className="text-sm text-[var(--muted)]">Items per page:</span>
							<select
								value={positionsPageSize}
								onChange={(e) => {
									setPositionsPageSize(Number(e.target.value));
									setPositionsPage(1);
								}}
								className="px-2 py-1 text-sm bg-[var(--panel)] border border-[#1e293b] rounded text-[var(--text)]"
							>
								<option value={10}>10</option>
								<option value={25}>25</option>
								<option value={50}>50</option>
								<option value={100}>100</option>
							</select>
						</div>
						<div className="text-sm text-[var(--muted)]">
							Showing {((positionsPage - 1) * positionsPageSize) + 1} to {Math.min(positionsPage * positionsPageSize, closedPositionsQ.data.total)} of {closedPositionsQ.data.total}
						</div>
					</div>
				)}

				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th
									className="text-left p-2 whitespace-nowrap cursor-pointer hover:bg-[#1e293b]"
									onClick={() => {
										if (positionsSortBy === 'symbol') {
											setPositionsSortOrder(positionsSortOrder === 'asc' ? 'desc' : 'asc');
										} else {
											setPositionsSortBy('symbol');
											setPositionsSortOrder('asc');
										}
									}}
								>
									Symbol {positionsSortBy === 'symbol' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
								</th>
								<th className="text-left p-2 whitespace-nowrap">Stock Name</th>
								<th className="text-right p-2 whitespace-nowrap">Qty</th>
								<th className="text-right p-2 whitespace-nowrap">Entry</th>
								<th className="text-right p-2 whitespace-nowrap">Exit</th>
								<th
									className="text-right p-2 whitespace-nowrap cursor-pointer hover:bg-[#1e293b]"
									onClick={() => {
										if (positionsSortBy === 'realized_pnl') {
											setPositionsSortOrder(positionsSortOrder === 'asc' ? 'desc' : 'asc');
										} else {
											setPositionsSortBy('realized_pnl');
											setPositionsSortOrder('desc');
										}
									}}
								>
									P&L {positionsSortBy === 'realized_pnl' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
								</th>
								<th className="text-right p-2 whitespace-nowrap">P&L %</th>
								<th
									className="text-left p-2 whitespace-nowrap cursor-pointer hover:bg-[#1e293b]"
									onClick={() => {
										if (positionsSortBy === 'closed_at') {
											setPositionsSortOrder(positionsSortOrder === 'asc' ? 'desc' : 'asc');
										} else {
											setPositionsSortBy('closed_at');
											setPositionsSortOrder('desc');
										}
									}}
								>
									Closed Date {positionsSortBy === 'closed_at' && (positionsSortOrder === 'asc' ? '▲' : '▼')}
								</th>
							</tr>
						</thead>
						<tbody>
							{(closedPositionsQ.data?.items ?? []).map((pos) => (
								<tr key={pos.id} className="border-t border-[#1e293b]">
									<td className="p-2 text-[var(--text)] font-medium">{pos.symbol}</td>
									<td className="p-2 text-[var(--text)]">{pos.stock_name || '-'}</td>
									<td className="p-2 text-right text-[var(--text)]">{pos.quantity}</td>
									<td className="p-2 text-right text-[var(--text)]">{formatMoney(pos.avg_price)}</td>
									<td className="p-2 text-right text-[var(--text)]">{pos.exit_price ? formatMoney(pos.exit_price) : '-'}</td>
									<td
										className={`p-2 text-right font-medium ${
											pos.realized_pnl && pos.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
										}`}
									>
										{pos.realized_pnl !== null ? formatMoney(pos.realized_pnl) : '-'}
									</td>
									<td
										className={`p-2 text-right font-medium ${
											pos.realized_pnl_pct && pos.realized_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'
										}`}
									>
										{pos.realized_pnl_pct !== null ? `${pos.realized_pnl_pct.toFixed(2)}%` : '-'}
									</td>
									<td className="p-2 text-[var(--text)]">{new Date(pos.closed_at).toLocaleDateString('en-IN')}</td>
								</tr>
							))}
							{(closedPositionsQ.data?.items ?? []).length === 0 && !closedPositionsQ.isLoading && (
								<tr>
									<td className="p-2 text-[var(--muted)] text-center" colSpan={8}>
										No closed positions available
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>

				{/* Pagination Controls - Bottom */}
				{closedPositionsQ.data && closedPositionsQ.data.total_pages > 1 && (
					<div className="px-3 py-2 border-t border-[#1e293b] flex items-center justify-between gap-2 flex-wrap">
						<button
							onClick={() => setPositionsPage((p) => Math.max(1, p - 1))}
							disabled={positionsPage === 1}
							className="px-3 py-1 text-sm bg-[var(--panel)] border border-[#1e293b] rounded text-[var(--text)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#1e293b]"
						>
							Previous
						</button>
						<div className="flex items-center gap-1">
							{Array.from({ length: Math.min(5, closedPositionsQ.data.total_pages) }, (_, i) => {
								let pageNum: number;
								if (closedPositionsQ.data.total_pages <= 5) {
									pageNum = i + 1;
								} else if (positionsPage <= 3) {
									pageNum = i + 1;
								} else if (positionsPage >= closedPositionsQ.data.total_pages - 2) {
									pageNum = closedPositionsQ.data.total_pages - 4 + i;
								} else {
									pageNum = positionsPage - 2 + i;
								}
								return (
									<button
										key={pageNum}
										onClick={() => setPositionsPage(pageNum)}
										className={`px-2 py-1 text-sm rounded ${
											positionsPage === pageNum
												? 'bg-blue-600 text-white'
												: 'bg-[var(--panel)] border border-[#1e293b] text-[var(--text)] hover:bg-[#1e293b]'
										}`}
									>
										{pageNum}
									</button>
								);
							})}
						</div>
						<button
							onClick={() => setPositionsPage((p) => Math.min(closedPositionsQ.data!.total_pages, p + 1))}
							disabled={positionsPage === closedPositionsQ.data.total_pages}
							className="px-3 py-1 text-sm bg-[var(--panel)] border border-[#1e293b] rounded text-[var(--text)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#1e293b]"
						>
							Next
						</button>
					</div>
				)}
			</div>
		</div>
	);
}
