import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listOrders, retryOrder, dropOrder, type Order, type OrderStatus } from '@/api/orders';
import { exportOrders } from '@/api/export';
import { ExportButton } from '@/components/ExportButton';
import { DateRangePicker, type DateRange } from '@/components/DateRangePicker';
import { useSavedFilters } from '@/hooks/useSavedFilters';
import { FilterPresetDropdown } from '@/components/FilterPresetDropdown';

const TABS: { key: OrderStatus; label: string }[] = [
	{ key: 'pending', label: 'Pending' }, // Merged: AMO + PENDING_EXECUTION
	{ key: 'ongoing', label: 'Ongoing' },
	{ key: 'failed', label: 'Failed' }, // Merged: FAILED + RETRY_PENDING + REJECTED
	{ key: 'closed', label: 'Closed' },
	{ key: 'cancelled', label: 'Cancelled' },
	// Note: SELL status removed - use side='sell' to filter sell orders
];

const formatPrice = (value: number | null | undefined): string => {
	if (typeof value !== 'number' || Number.isNaN(value)) {
		return '-';
	}
	const truncated = Math.trunc(value * 100) / 100;
	return truncated.toFixed(2);
};

const formatDate = (dateStr: string | null | undefined): string => {
	if (!dateStr) return '-';
	try {
		const date = new Date(dateStr);
		return date.toLocaleString();
	} catch {
		return dateStr;
	}
};

function getDefaultDateRange(): DateRange {
	const endDate = new Date();
	const startDate = new Date();
	startDate.setDate(startDate.getDate() - 30); // Last 30 days

	return {
		startDate: startDate.toISOString().split('T')[0],
		endDate: endDate.toISOString().split('T')[0],
	};
}

export function OrdersPage() {
	const [tab, setTab] = useState<OrderStatus>('pending');
	const [tradeModeFilter, setTradeModeFilter] = useState<'all' | 'paper' | 'broker'>('all');
	const [showExportOptions, setShowExportOptions] = useState(false);
	const [exportDateRange, setExportDateRange] = useState<DateRange>(getDefaultDateRange());
	const queryClient = useQueryClient();

	// Saved filters hook
	const { presets, savePreset, deletePreset, loading: presetsLoading } = useSavedFilters('orders');

	const { data, isLoading, isError } = useQuery({
		queryKey: ['orders', tab],
		queryFn: () => listOrders({ status: tab }),
	});

	const retryMutation = useMutation({
		mutationFn: retryOrder,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['orders'] });
		},
	});

	const dropMutation = useMutation({
		mutationFn: dropOrder,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['orders'] });
		},
	});

	useEffect(() => {
		document.title = 'Orders';
	}, []);

	const handleExport = async () => {
		const tradeMode = tradeModeFilter === 'all' ? undefined : tradeModeFilter === 'paper' ? 'paper' : 'broker';
		await exportOrders({
			startDate: exportDateRange.startDate,
			endDate: exportDateRange.endDate,
			tradeMode: tradeMode as 'paper' | 'broker' | undefined,
			status: tab,
		});
	};

	// Filter preset handlers
	const handleLoadPreset = (filters: any) => {
		if (filters.tab) setTab(filters.tab);
		if (filters.tradeModeFilter) setTradeModeFilter(filters.tradeModeFilter);
	};

	const handleSavePreset = async (name: string) => {
		return await savePreset(name, {
			tab,
			tradeModeFilter,
		});
	};

	const orders: Order[] = useMemo(() => {
		const allOrders = data ?? [];
		if (tradeModeFilter === 'all') {
			return allOrders;
		}
		// Filter by trade_mode_display (case-insensitive)
		return allOrders.filter((o) => {
			if (!o.trade_mode_display) return false;
			const display = o.trade_mode_display.toLowerCase();
			if (tradeModeFilter === 'paper') {
				return display === 'paper';
			}
			if (tradeModeFilter === 'broker') {
				return display !== 'paper'; // Any broker name
			}
			return true;
		});
	}, [data, tradeModeFilter]);

	const handleRetry = async (orderId: number) => {
		if (confirm('Retry this order?')) {
			try {
				await retryMutation.mutateAsync(orderId);
			} catch {
				alert('Failed to retry order');
			}
		}
	};

	const handleDrop = async (orderId: number) => {
		if (confirm('Drop this order from retry queue?')) {
			try {
				await dropMutation.mutateAsync(orderId);
			} catch {
				alert('Failed to drop order');
			}
		}
	};

	const isFailed = tab === 'failed';
	const isOngoingOrClosed = tab === 'ongoing' || tab === 'closed';

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
				<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Orders</h1>
				<div className="flex items-center gap-2">
					<FilterPresetDropdown
						presets={presets}
						onLoadPreset={handleLoadPreset}
						onSavePreset={handleSavePreset}
						onDeletePreset={deletePreset}
						currentFilters={{ tab, tradeModeFilter }}
						loading={presetsLoading}
					/>
					<button
						onClick={() => setShowExportOptions(!showExportOptions)}
						className="px-3 py-2 sm:py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 min-h-[44px] sm:min-h-0"
					>
						Export {showExportOptions ? '▲' : '▼'}
					</button>
				</div>
			</div>
			{showExportOptions && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
					<h3 className="text-sm font-medium text-[var(--text)] mb-3">Export Orders</h3>
					<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
						<DateRangePicker value={exportDateRange} onChange={setExportDateRange} />
						<ExportButton onExport={handleExport} label="Download CSV" />
					</div>
					<p className="text-xs text-[var(--muted)] mt-2">
						Export will include orders with status "{tab}" and trade mode "{tradeModeFilter}" for the selected date range.
					</p>
				</div>
			)}
			<div className="flex flex-wrap gap-2">
				{TABS.map((t) => (
					<button
						key={t.key}
						className={`px-3 py-2 sm:py-1 rounded border text-sm sm:text-base min-h-[44px] sm:min-h-0 ${
							tab === t.key
								? 'bg-blue-600 text-white border-blue-600'
								: 'bg-[var(--panel)] text-[var(--text)] border-[#1e293b] hover:bg-[#0f1720]'
						}`}
						onClick={() => setTab(t.key)}
						aria-pressed={tab === t.key}
					>
						{t.label}
					</button>
				))}
			</div>
			<div className="flex flex-wrap gap-2 items-center">
				<span className="text-sm text-[var(--muted)]">Filter by mode:</span>
				<button
					className={`px-3 py-1 rounded border text-sm ${
						tradeModeFilter === 'all'
							? 'bg-blue-600 text-white border-blue-600'
							: 'bg-[var(--panel)] text-[var(--text)] border-[#1e293b] hover:bg-[#0f1720]'
					}`}
					onClick={() => setTradeModeFilter('all')}
				>
					All
				</button>
				<button
					className={`px-3 py-1 rounded border text-sm ${
						tradeModeFilter === 'paper'
							? 'bg-purple-600 text-white border-purple-600'
							: 'bg-[var(--panel)] text-[var(--text)] border-[#1e293b] hover:bg-[#0f1720]'
					}`}
					onClick={() => setTradeModeFilter('paper')}
				>
					Paper
				</button>
				<button
					className={`px-3 py-1 rounded border text-sm ${
						tradeModeFilter === 'broker'
							? 'bg-green-600 text-white border-green-600'
							: 'bg-[var(--panel)] text-[var(--text)] border-[#1e293b] hover:bg-[#0f1720]'
					}`}
					onClick={() => setTradeModeFilter('broker')}
				>
					Broker
				</button>
			</div>
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">{TABS.find((t) => t.key === tab)?.label} Orders</div>
					{isLoading && <span className="text-xs sm:text-sm text-[var(--muted)]">Loading...</span>}
					{isError && <span className="text-xs sm:text-sm text-red-400">Failed to load orders</span>}
				</div>
				<div className="overflow-x-auto -mx-2 sm:mx-0">
					<table className="w-full text-xs sm:text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th className="text-left p-2 whitespace-nowrap">Symbol</th>
								<th className="text-left p-2 whitespace-nowrap">Side</th>
								<th className="text-left p-2 whitespace-nowrap">Qty</th>
								<th className="text-left p-2 whitespace-nowrap">Price</th>
								<th className="text-left p-2 whitespace-nowrap">Status</th>
								<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Mode</th>
								<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Created</th>
								<th className="text-left p-2 whitespace-nowrap hidden md:table-cell">Entry Type</th>
								<th className="text-left p-2 whitespace-nowrap hidden md:table-cell">Manual</th>
								<th className="text-left p-2 whitespace-nowrap hidden lg:table-cell">Reason</th>
							{isOngoingOrClosed && (
								<>
									<th className="text-left p-2 whitespace-nowrap">Exec Price</th>
									<th className="text-left p-2 whitespace-nowrap">Exec Qty</th>
									<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Exec Time</th>
								</>
							)}
							{isFailed && (
								<>
									<th className="text-left p-2 whitespace-nowrap">Retry Count</th>
									<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Last Retry</th>
								</>
							)}
							{isFailed && <th className="text-left p-2 whitespace-nowrap">Actions</th>}
						</tr>
					</thead>
					<tbody>
						{orders.map((o) => (
							<tr key={o.id} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)] font-medium">{o.symbol}</td>
								<td className="p-2 text-[var(--text)]">{o.side}</td>
								<td className="p-2 text-[var(--text)]">{o.quantity}</td>
								<td className="p-2 text-[var(--text)]">{formatPrice(o.price)}</td>
								<td className="p-2 text-[var(--text)]">{o.status}</td>
								<td className="p-2 text-[var(--text)] hidden sm:table-cell">
									{o.trade_mode_display ? (
										<span className={`px-2 py-0.5 text-xs rounded ${
											o.trade_mode_display.toLowerCase() === 'paper'
												? 'bg-purple-500/20 text-purple-300'
												: 'bg-green-500/20 text-green-300'
										}`}>
											{o.trade_mode_display}
										</span>
									) : (
										<span className="text-[var(--muted)]">-</span>
									)}
								</td>
								<td className="p-2 text-[var(--text)] text-xs hidden sm:table-cell">
									{formatDate(o.created_at)}
								</td>
								<td className="p-2 text-[var(--text)] hidden md:table-cell">
									{o.entry_type ? (
										<span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-300">
											{o.entry_type}
										</span>
									) : (
										<span className="text-[var(--muted)]">-</span>
									)}
								</td>
								<td className="p-2 text-[var(--text)] hidden md:table-cell">
									{o.is_manual ? (
										<span className="px-2 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-300">
											Yes
										</span>
									) : (
										<span className="text-[var(--muted)]">No</span>
									)}
								</td>
								<td className="p-2 text-[var(--text)] hidden lg:table-cell">
									{o.reason ? (
										<span
											className="cursor-help inline-flex items-center justify-center w-5 h-5 rounded-full bg-[var(--muted)]/20 text-[var(--muted)] hover:bg-[var(--muted)]/30 transition-colors"
											title={o.reason}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												strokeLinecap="round"
												strokeLinejoin="round"
												className="w-4 h-4"
											>
												<circle cx="12" cy="12" r="10" />
												<path d="M12 16v-4" />
												<path d="M12 8h.01" />
											</svg>
										</span>
									) : (
										<span className="text-[var(--muted)]">-</span>
									)}
								</td>
								{isOngoingOrClosed && (
									<>
										<td className="p-2 text-[var(--text)]">
											{formatPrice(o.execution_price)}
										</td>
										<td className="p-2 text-[var(--text)]">
											{o.execution_qty != null ? o.execution_qty : '-'}
										</td>
										<td className="p-2 text-[var(--text)] text-xs hidden sm:table-cell">
											{formatDate(o.execution_time)}
										</td>
									</>
								)}
								{isFailed && (
									<>
										<td className="p-2 text-[var(--text)]">{o.retry_count ?? 0}</td>
										<td className="p-2 text-[var(--text)] text-xs hidden sm:table-cell">
											{formatDate(o.last_retry_attempt || o.first_failed_at)}
										</td>
									</>
								)}
								{isFailed && (
									<td className="p-2">
										<div className="flex flex-col sm:flex-row gap-1 sm:gap-2">
											<button
												onClick={() => handleRetry(o.id)}
												disabled={retryMutation.isPending}
												className="px-2 py-2 sm:py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px] sm:min-h-0"
											>
												Retry
											</button>
											<button
												onClick={() => handleDrop(o.id)}
												disabled={dropMutation.isPending}
												className="px-2 py-2 sm:py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px] sm:min-h-0"
											>
												Drop
											</button>
										</div>
									</td>
								)}
							</tr>
						))}
						{orders.length === 0 && !isLoading && (
							<tr>
								<td
									className="p-2 text-[var(--muted)]"
									colSpan={
										isFailed
											? 12
											: isOngoingOrClosed
												? 12
												: 9
									}
								>
									No orders
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
