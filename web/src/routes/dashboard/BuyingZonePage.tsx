import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo, useEffect } from 'react';
import { getBuyingZone, getBuyingZoneColumns, saveBuyingZoneColumns, rejectSignal, activateSignal, type BuyingZoneItem, type DateFilter, type StatusFilter } from '@/api/signals';

type ColumnKey =
	| 'symbol'
	| 'status'
	| 'rsi10'
	| 'ema9'
	| 'ema200'
	| 'distance_to_ema9'
	| 'above_ema200'
	| 'clean_chart'
	| 'monthly_support_dist'
	| 'confidence'
	| 'backtest_score'
	| 'combined_score'
	| 'strength_score'
	| 'priority_score'
	| 'ml_verdict'
	| 'ml_confidence'
	| 'buy_range'
	| 'target'
	| 'stop'
	| 'last_close'
	| 'pe'
	| 'pb'
	| 'fundamental_ok'
	| 'avg_vol'
	| 'today_vol'
	| 'vol_ok'
	| 'volume_ratio'
	| 'verdict'
	| 'final_verdict'
	| 'rule_verdict'
	| 'verdict_source'
	| 'backtest_confidence'
	| 'vol_strong'
	| 'is_above_ema200'
	| 'dip_depth_from_20d_high_pct'
	| 'consecutive_red_days'
	| 'dip_speed_pct_per_day'
	| 'decline_rate_slowing'
	| 'volume_green_vs_red_ratio'
	| 'support_hold_count'
	| 'ts';

interface ColumnDef {
	key: ColumnKey;
	label: string;
	mandatory?: boolean;
	formatter?: (value: any, row: BuyingZoneItem) => string;
}

const ALL_COLUMNS: ColumnDef[] = [
	{ key: 'symbol', label: 'Stock Symbol', mandatory: true },
	{ key: 'status', label: 'Status' },
	// Technical indicators
	{ key: 'rsi10', label: 'RSI10', formatter: (v) => (v != null ? v.toFixed(1) : '-') },
	{ key: 'ema9', label: 'EMA9', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'ema200', label: 'EMA200', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'distance_to_ema9', label: 'Distance to EMA9', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'above_ema200', label: '> EMA200', formatter: (v, row) => {
		const above = row.ema200 != null && row.ema9 != null ? (row.ema9 > row.ema200) : null;
		return above == null ? '-' : above ? 'Yes' : 'No';
	}},
	{ key: 'clean_chart', label: 'Clean Chart', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	{ key: 'monthly_support_dist', label: 'Monthly Support', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'confidence', label: 'Confidence', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	// Scoring fields
	{ key: 'backtest_score', label: 'Backtest', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'combined_score', label: 'Combined Score', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'strength_score', label: 'Strength Score', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'priority_score', label: 'Priority Score', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	// ML fields
	{ key: 'ml_verdict', label: 'ML Verdict', formatter: (v) => (v ?? '-') },
	{ key: 'ml_confidence', label: 'ML Confidence', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	// Trading parameters
	{ key: 'buy_range', label: 'Buy Range', formatter: (v) => {
		if (!v || typeof v !== 'object') return '-';
		const range = v as { low?: number; high?: number };
		if (range.low != null && range.high != null) {
			return `${range.low.toFixed(2)} - ${range.high.toFixed(2)}`;
		}
		return '-';
	}},
	{ key: 'target', label: 'Target', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'stop', label: 'Stop', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'last_close', label: 'Last Close', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	// Fundamental data
	{ key: 'pe', label: 'P/E', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'pb', label: 'P/B', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'fundamental_ok', label: 'Fundamental OK', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	// Volume data
	{ key: 'avg_vol', label: 'Avg Vol', formatter: (v) => (v != null ? v.toLocaleString() : '-') },
	{ key: 'today_vol', label: 'Today Vol', formatter: (v) => (v != null ? v.toLocaleString() : '-') },
	{ key: 'vol_ok', label: 'Vol OK', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	{ key: 'volume_ratio', label: 'Volume Ratio', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	// Analysis metadata
	{ key: 'verdict', label: 'Verdict', formatter: (v) => (v ?? '-') },
	{ key: 'final_verdict', label: 'Final Verdict', formatter: (v) => (v ?? '-') },
	{ key: 'rule_verdict', label: 'Rule Verdict', formatter: (v) => (v ?? '-') },
	{ key: 'verdict_source', label: 'Verdict Source', formatter: (v) => (v ?? '-') },
	{ key: 'backtest_confidence', label: 'Backtest Confidence', formatter: (v) => (v ?? '-') },
	// Additional analysis fields
	{ key: 'vol_strong', label: 'Vol Strong', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	{ key: 'is_above_ema200', label: 'Above EMA200', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	// Dip buying features
	{ key: 'dip_depth_from_20d_high_pct', label: 'Dip Depth %', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'consecutive_red_days', label: 'Red Days', formatter: (v) => (v != null ? v.toString() : '-') },
	{ key: 'dip_speed_pct_per_day', label: 'Dip Speed %/Day', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'decline_rate_slowing', label: 'Decline Slowing', formatter: (v) => (v == null ? '-' : v ? 'Yes' : 'No') },
	{ key: 'volume_green_vs_red_ratio', label: 'Vol G/R Ratio', formatter: (v) => (v != null ? v.toFixed(2) : '-') },
	{ key: 'support_hold_count', label: 'Support Holds', formatter: (v) => (v != null ? v.toString() : '-') },
	// Timestamp
	{ key: 'ts', label: 'As of', formatter: (v) => new Date(v).toLocaleString() },
];

const MIN_COLUMNS = 5;
const MAX_COLUMNS = 20;

// Default columns: Symbol, Status, Distance to EMA9, Backtest, Confidence, ML Confidence
const DEFAULT_COLUMNS: ColumnKey[] = ['symbol', 'status', 'distance_to_ema9', 'backtest_score', 'confidence', 'ml_confidence'];

export function BuyingZonePage() {
	const qc = useQueryClient();
	const [dateFilter, setDateFilter] = useState<DateFilter>(null);
	const [statusFilter, setStatusFilter] = useState<StatusFilter>('active');

	const { data, isLoading, error} = useQuery<BuyingZoneItem[]>({
		queryKey: ['buying-zone', dateFilter, statusFilter],
		queryFn: () => getBuyingZone(100, dateFilter, statusFilter),
	});
	const totalSignals = data?.length ?? 0;

	// Reject signal mutation
	const rejectMutation = useMutation({
		mutationFn: (symbol: string) => rejectSignal(symbol),
		onSuccess: () => {
			// Refetch buying zone data
			qc.invalidateQueries({ queryKey: ['buying-zone'] });
		},
	});

	// Activate signal mutation
	const activateMutation = useMutation({
		mutationFn: (symbol: string) => activateSignal(symbol),
		onSuccess: () => {
			// Refetch buying zone data
			qc.invalidateQueries({ queryKey: ['buying-zone'] });
		},
	});

	// Load saved columns from API
	const { data: savedColumns } = useQuery<string[]>({
		queryKey: ['buying-zone-columns'],
		queryFn: getBuyingZoneColumns,
	});

	// Initialize with saved columns or defaults
	const [selectedColumns, setSelectedColumns] = useState<Set<ColumnKey>>(
		new Set(DEFAULT_COLUMNS)
	);

	// Update selected columns when saved columns are loaded
	useEffect(() => {
		if (savedColumns && savedColumns.length > 0) {
			// Validate saved columns are valid ColumnKeys
			const validColumns = savedColumns.filter((col) =>
				ALL_COLUMNS.some((c) => c.key === col)
			) as ColumnKey[];
			// Ensure symbol and status are always included (status needed for badges/reject buttons)
			if (validColumns.length >= MIN_COLUMNS && validColumns.length <= MAX_COLUMNS) {
				if (!validColumns.includes('symbol')) {
					validColumns.unshift('symbol');
				}
				// Ensure status is included after symbol (status column is needed for badges and reject buttons)
				if (!validColumns.includes('status')) {
					const symbolIndex = validColumns.indexOf('symbol');
					validColumns.splice(symbolIndex + 1, 0, 'status');
				}
				setSelectedColumns(new Set(validColumns));
			}
		}
	}, [savedColumns]);

	// Save columns mutation
	const saveColumnsMutation = useMutation({
		mutationFn: (columns: string[]) => saveBuyingZoneColumns(columns),
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['buying-zone-columns'] });
		},
	});

	useEffect(() => {
		document.title = 'Buying Zone';
	}, []);

	const [isDropdownOpen, setIsDropdownOpen] = useState(false);

	// Close dropdown on Escape key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === 'Escape' && isDropdownOpen) {
				setIsDropdownOpen(false);
			}
		};
		document.addEventListener('keydown', handleEscape);
		return () => document.removeEventListener('keydown', handleEscape);
	}, [isDropdownOpen]);

	const handleColumnToggle = (key: ColumnKey) => {
		setSelectedColumns((prev) => {
			const newSet = new Set(prev);
			const colDef = ALL_COLUMNS.find((c) => c.key === key);
			if (!colDef) return prev;

			// Mandatory columns cannot be deselected
			if (colDef.mandatory) return prev;

			// Toggle column
			if (newSet.has(key)) {
				// Deselecting: check min columns constraint
				if (newSet.size <= MIN_COLUMNS) {
					return prev; // Cannot deselect, already at minimum
				}
				newSet.delete(key);
			} else {
				// Selecting: check max columns constraint
				if (newSet.size >= MAX_COLUMNS) {
					return prev; // Cannot select, already at maximum
				}
				newSet.add(key);
			}

			// Save to backend
			const columnsArray = Array.from(newSet) as string[];
			saveColumnsMutation.mutate(columnsArray);

			return newSet;
		});
	};

	const visibleColumns = useMemo(() => {
		return ALL_COLUMNS.filter((col) => selectedColumns.has(col.key));
	}, [selectedColumns]);

	// Group signals by date
	const signalsByDate = useMemo(() => {
		if (!data || data.length === 0) return new Map<string, BuyingZoneItem[]>();

		const grouped = new Map<string, BuyingZoneItem[]>();
		data.forEach((signal) => {
			// Extract date from timestamp (YYYY-MM-DD)
			const date = signal.ts.split('T')[0];
			if (!grouped.has(date)) {
				grouped.set(date, []);
			}
			grouped.get(date)!.push(signal);
		});

		// Sort dates descending (newest first)
		const sortedDates = Array.from(grouped.keys()).sort((a, b) => b.localeCompare(a));
		const sortedMap = new Map<string, BuyingZoneItem[]>();
		sortedDates.forEach((date) => {
			sortedMap.set(date, grouped.get(date)!);
		});

		return sortedMap;
	}, [data]);

	if (isLoading) return <div className="p-2 sm:p-4 text-sm sm:text-base text-[var(--text)]">Loading...</div>;
	if (error) return <div className="p-2 sm:p-4 text-sm sm:text-base text-red-400">Failed to load</div>;

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Buying Zone</h1>
				<div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4 w-full sm:w-auto">
					{/* Status Filter */}
					<div className="flex items-center gap-2">
						<label className="text-xs sm:text-sm text-[var(--muted)] whitespace-nowrap">Status:</label>
						<select
							value={statusFilter}
							onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
							className="flex-1 sm:flex-none bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:py-1.5 text-sm text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px] sm:min-h-0"
						>
							<option value="active">✓ Active</option>
							<option value="all">All Statuses</option>
							<option value="expired">⏰ Expired</option>
							<option value="traded">✅ Traded</option>
							<option value="rejected">❌ Rejected</option>
						</select>
					</div>

					{/* Date Filter */}
					<div className="flex items-center gap-2">
						<label className="text-xs sm:text-sm text-[var(--muted)] whitespace-nowrap">Date:</label>
						<select
							value={dateFilter || ''}
							onChange={(e) => setDateFilter((e.target.value || null) as DateFilter)}
							className="flex-1 sm:flex-none bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:py-1.5 text-sm text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px] sm:min-h-0"
						>
							<option value="">All (Recent)</option>
							<option value="today">Today</option>
							<option value="yesterday">Yesterday</option>
							<option value="last_10_days">Last 10 Days</option>
						</select>
					</div>
					<span className="text-xs sm:text-sm text-[var(--muted)] self-center">
						{selectedColumns.size} / {MAX_COLUMNS} columns
					</span>
				</div>
			</div>

			{/* Column Selection */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3">
					<label className="text-xs sm:text-sm font-medium text-[var(--text)]">
						Select Columns (Min {MIN_COLUMNS}, Max {MAX_COLUMNS})
					</label>
					<span className="text-xs text-[var(--muted)]">
						{selectedColumns.size} selected
					</span>
				</div>

				{/* Multi-select Dropdown */}
				<div className="relative">
					<button
						type="button"
						onClick={() => setIsDropdownOpen(!isDropdownOpen)}
						className="w-full bg-[#0f1720] border border-[#1e293b] rounded px-3 py-3 sm:py-2 text-left text-sm text-[var(--text)] flex items-center justify-between hover:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px] sm:min-h-0"
					>
						<span>
							{selectedColumns.size === 0
								? 'Select columns...'
								: `${selectedColumns.size} column${selectedColumns.size === 1 ? '' : 's'} selected`}
						</span>
						<svg
							className={`w-4 h-4 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`}
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
						</svg>
					</button>

					{isDropdownOpen && (
						<>
							<div
								className="fixed inset-0 z-10"
								onClick={() => setIsDropdownOpen(false)}
							/>
							<div className="absolute z-20 w-full mt-1 bg-[#0f1720] border border-[#1e293b] rounded-lg shadow-lg max-h-96 overflow-y-auto">
								<div className="p-2 space-y-1">
									{ALL_COLUMNS.map((col) => {
										const isSelected = selectedColumns.has(col.key);
										const isDisabled =
											col.mandatory ||
											(!isSelected && selectedColumns.size >= MAX_COLUMNS) ||
											(isSelected && selectedColumns.size <= MIN_COLUMNS);
										return (
											<label
												key={col.key}
												className={`flex items-center gap-2 px-3 py-2 rounded cursor-pointer transition-colors ${
													isSelected
														? 'bg-blue-600/20 text-blue-400'
														: 'text-[var(--text)] hover:bg-[#1e293b]'
												} ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
											>
												<input
													type="checkbox"
													checked={isSelected}
													onChange={() => handleColumnToggle(col.key)}
													disabled={isDisabled}
													className="accent-blue-600"
												/>
												<span className="text-sm flex-1">{col.label}</span>
												{col.mandatory && (
													<span className="text-xs text-[var(--muted)]">(required)</span>
												)}
											</label>
										);
									})}
								</div>
							</div>
						</>
					)}
				</div>

				{/* Selected Columns Display */}
				{selectedColumns.size > 0 && (
					<div className="mt-3 flex flex-wrap gap-2">
						{visibleColumns.map((col) => (
							<span
								key={col.key}
								className="inline-flex items-center gap-1 px-2 py-1 bg-blue-600/20 text-blue-400 rounded text-xs"
							>
								{col.label}
								{!col.mandatory && (
									<button
										type="button"
										onClick={() => handleColumnToggle(col.key)}
										disabled={selectedColumns.size <= MIN_COLUMNS}
										className="hover:text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed"
									>
										x
									</button>
								)}
							</span>
						))}
					</div>
				)}
			</div>

			{/* Results Count */}
			{totalSignals > 0 && (
				<div className="text-sm text-[var(--muted)]">
					Showing {totalSignals} {statusFilter === 'active' ? 'active' : statusFilter} signal{totalSignals === 1 ? '' : 's'}
					{dateFilter === 'today' && ' from today'}
					{dateFilter === 'yesterday' && ' from yesterday'}
					{dateFilter === 'last_10_days' && ' from last 10 days'}
					{!dateFilter && ' (most recent)'}
					{signalsByDate.size > 1 && ` across ${signalsByDate.size} days`}
				</div>
			)}

			{/* Date-wise Tables */}
			{signalsByDate.size > 0 ? (
				<div className="space-y-6">
					{Array.from(signalsByDate.entries()).map(([date, signals]) => {
						const dateObj = new Date(date);
						const formattedDate = dateObj.toLocaleDateString('en-US', {
							weekday: 'short',
							year: 'numeric',
							month: 'short',
							day: 'numeric',
						});

						return (
							<div key={date} className="space-y-2">
								{/* Date Header */}
								<div className="flex items-center gap-3">
									<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">
										{formattedDate}
									</h2>
									<span className="text-sm text-[var(--muted)]">
										({signals.length} signal{signals.length === 1 ? '' : 's'})
									</span>
								</div>

								{/* Table for this date */}
								<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
									<div className="overflow-x-auto -mx-2 sm:mx-0">
										<table className="w-full text-xs sm:text-sm">
											<thead className="bg-[#0f172a] text-[var(--muted)]">
												<tr>
													{visibleColumns.map((col) => (
														<th key={col.key} className="py-2 px-2 sm:px-3 text-left whitespace-nowrap">
															{col.label}
														</th>
													))}
												</tr>
											</thead>
											<tbody>
												{signals.map((row) => {
													return (
														<tr key={row.id} className="border-t border-[#1e293b] hover:bg-[#0f1720]">
															{visibleColumns.map((col) => {
																// Special rendering for status column
																if (col.key === 'status') {
																	const status = row.status;
																	let badgeClass = '';
																	let badgeText = '';

																	switch (status) {
																		case 'active':
																			badgeClass = 'bg-green-500/20 text-green-400 border border-green-500/30';
																			badgeText = '✓ Active';
																			break;
																		case 'expired':
																			badgeClass = 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
																			badgeText = '⏰ Expired';
																			break;
																		case 'traded':
																			badgeClass = 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
																			badgeText = '✅ Traded';
																			break;
																		case 'rejected':
																			badgeClass = 'bg-red-500/20 text-red-400 border border-red-500/30';
																			badgeText = '❌ Rejected';
																			break;
																		default:
																			badgeClass = 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
																			badgeText = status || '-';
																	}

																	return (
																		<td key={col.key} className="py-2 px-2 sm:px-3">
																			<div className="flex flex-col sm:flex-row items-start sm:items-center gap-1 sm:gap-2">
																				<span className={`px-2 py-1 rounded-full text-xs font-semibold ${badgeClass}`}>
																					{badgeText}
																				</span>
																				{status === 'active' && (
																					<button
																						onClick={() => rejectMutation.mutate(row.symbol)}
																						disabled={rejectMutation.isPending}
																						className="text-xs px-2 py-1.5 sm:py-1 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 disabled:opacity-50 min-h-[32px] sm:min-h-0"
																						title="Reject this signal"
																					>
																						Reject
																					</button>
																				)}
																				{(status === 'rejected' || status === 'traded') && (() => {
																					// Check if signal is expired based on timestamp or base_status
																					const signalDate = new Date(row.ts);
																					const today = new Date();
																					today.setHours(0, 0, 0, 0);
																					const signalDateOnly = new Date(signalDate);
																					signalDateOnly.setHours(0, 0, 0, 0);
																					const isExpiredByDate = signalDateOnly < today;
																					const isExpired = row.base_status === 'expired' || isExpiredByDate;

																					return (
																						<button
																							onClick={() => activateMutation.mutate(row.symbol)}
																							disabled={activateMutation.isPending || isExpired}
																							className="text-xs px-2 py-1.5 sm:py-1 rounded bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed min-h-[32px] sm:min-h-0"
																							title={isExpired ? 'Cannot reactivate expired signals' : 'Reactivate this signal'}
																						>
																							{activateMutation.isPending ? 'Activating...' : 'Active'}
																						</button>
																					);
																				})()}
																			</div>
																		</td>
																	);
																}

																// Regular columns
																let displayValue: string;
																if (col.formatter) {
																	displayValue = col.formatter((row as any)[col.key], row);
																} else {
																	displayValue = String((row as any)[col.key] ?? '-');
																}
																return (
																	<td key={col.key} className="py-2 px-2 sm:px-3 text-[var(--text)]">
																		{displayValue}
																	</td>
																);
															})}
														</tr>
													);
												})}
											</tbody>
										</table>
									</div>
								</div>
							</div>
						);
					})}
				</div>
			) : (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-8">
					<div className="text-center text-[var(--muted)]">No signals found</div>
				</div>
			)}
		</div>
	);
}
