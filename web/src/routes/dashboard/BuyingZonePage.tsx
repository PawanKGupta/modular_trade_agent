import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo, useEffect } from 'react';
import { getBuyingZone, getBuyingZoneColumns, saveBuyingZoneColumns, type BuyingZoneItem, type DateFilter } from '@/api/signals';

type ColumnKey =
	| 'symbol'
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

// Default columns: Symbol, Distance to EMA9, Backtest, Confidence, ML Confidence
const DEFAULT_COLUMNS: ColumnKey[] = ['symbol', 'distance_to_ema9', 'backtest_score', 'confidence', 'ml_confidence'];

export function BuyingZonePage() {
	const qc = useQueryClient();
	const [dateFilter, setDateFilter] = useState<DateFilter>(null);

	const { data, isLoading, error } = useQuery<BuyingZoneItem[]>({
		queryKey: ['buying-zone', dateFilter],
		queryFn: () => getBuyingZone(100, dateFilter),
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
			// Ensure symbol is always included
			if (validColumns.length >= MIN_COLUMNS && validColumns.length <= MAX_COLUMNS) {
				if (!validColumns.includes('symbol')) {
					validColumns.unshift('symbol');
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

	if (isLoading) return <div className="p-4 text-[var(--text)]">Loading...</div>;
	if (error) return <div className="p-4 text-red-400">Failed to load</div>;

	return (
		<div className="p-4 space-y-4">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold text-[var(--text)]">Buying Zone</h1>
				<div className="flex items-center gap-4">
					{/* Date Filter */}
					<div className="flex items-center gap-2">
						<label className="text-sm text-[var(--muted)]">Date Filter:</label>
						<select
							value={dateFilter || ''}
							onChange={(e) => setDateFilter((e.target.value || null) as DateFilter)}
							className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-1.5 text-sm text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="">All (Recent)</option>
							<option value="today">Today</option>
							<option value="yesterday">Yesterday</option>
							<option value="last_10_days">Last 10 Days</option>
						</select>
					</div>
					<span className="text-sm text-[var(--muted)]">
						{selectedColumns.size} / {MAX_COLUMNS} columns
					</span>
				</div>
			</div>

			{/* Column Selection */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
				<div className="flex items-center justify-between mb-3">
					<label className="text-sm font-medium text-[var(--text)]">
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
						className="w-full bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 text-left text-sm text-[var(--text)] flex items-center justify-between hover:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
										×
									</button>
								)}
							</span>
						))}
					</div>
				)}
			</div>

			{/* Results Count */}
			{(data ?? []).length > 0 && (
				<div className="text-sm text-[var(--muted)]">
					Showing {data.length} signal{data.length === 1 ? '' : 's'}
					{dateFilter === 'today' && ' from today'}
					{dateFilter === 'yesterday' && ' from yesterday'}
					{dateFilter === 'last_10_days' && ' from last 10 days'}
					{!dateFilter && ' (most recent)'}
				</div>
			)}

			{/* Table */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								{visibleColumns.map((col) => (
									<th key={col.key} className="py-2 px-3 text-left">
										{col.label}
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							{(data ?? []).map((row) => {
								return (
									<tr key={row.id} className="border-t border-[#1e293b] hover:bg-[#0f1720]">
										{visibleColumns.map((col) => {
											let displayValue: string;
											if (col.formatter) {
												displayValue = col.formatter((row as any)[col.key], row);
											} else {
												displayValue = String((row as any)[col.key] ?? '-');
											}
											return (
												<td key={col.key} className="py-2 px-3 text-[var(--text)]">
													{displayValue}
												</td>
											);
										})}
									</tr>
								);
							})}
							{(data ?? []).length === 0 && (
								<tr>
									<td className="py-4 px-3 text-center text-[var(--muted)]" colSpan={visibleColumns.length}>
										No signals found
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	);
}
