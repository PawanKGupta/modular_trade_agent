import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBrokerOrders, type BrokerOrder } from '@/api/user';
import { useSettings } from '@/hooks/useSettings';
import { formatBrokerError, calculateRetryDelay } from '@/utils/brokerApi';

type OrderStatusFilter = 'all' | 'pending' | 'ongoing' | 'closed' | 'failed' | 'cancelled';

const STATUS_TABS: { key: OrderStatusFilter; label: string }[] = [
	{ key: 'all', label: 'All' },
	{ key: 'pending', label: 'Pending' },
	{ key: 'ongoing', label: 'Ongoing' },
	{ key: 'closed', label: 'Closed' },
	{ key: 'failed', label: 'Failed' },
	{ key: 'cancelled', label: 'Cancelled' },
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

const getStatusColor = (status: string): string => {
	switch (status) {
		case 'pending':
			return 'bg-yellow-500/20 text-yellow-400';
		case 'ongoing':
			return 'bg-blue-500/20 text-blue-400';
		case 'closed':
			return 'bg-green-500/20 text-green-400';
		case 'failed':
			return 'bg-red-500/20 text-red-400';
		case 'cancelled':
			return 'bg-gray-500/20 text-gray-400';
		default:
			return 'bg-[var(--muted)]/20 text-[var(--muted)]';
	}
};

const getSideColor = (side: string): string => {
	return side === 'buy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400';
};

export function BrokerOrdersPage() {
	const { isBrokerMode, isBrokerConnected, broker } = useSettings();
	const [statusFilter, setStatusFilter] = useState<OrderStatusFilter>('all');

	const { data, isLoading, error, refetch, dataUpdatedAt, failureCount } = useQuery<BrokerOrder[]>({
		queryKey: ['broker-orders'],
		queryFn: getBrokerOrders,
		enabled: isBrokerMode && isBrokerConnected,
		refetchInterval: 10000, // Refresh every 10 seconds
		retry: (failureCount, error) => {
			// Retry up to 3 times for retryable errors
			if (failureCount >= 3) return false;
			const brokerError = formatBrokerError(error);
			return brokerError.retryable;
		},
		retryDelay: (attemptIndex) => calculateRetryDelay(attemptIndex),
	});

	useEffect(() => {
		document.title = 'Broker Orders';
	}, []);

	// Format last update time
	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

	if (!isBrokerMode) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-yellow-400">
					Broker orders are only available in broker mode. Please switch to broker mode in settings.
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

	const orders: BrokerOrder[] = useMemo(() => {
		if (!data) return [];
		if (statusFilter === 'all') return data;
		return data.filter((o) => o.status === statusFilter);
	}, [data, statusFilter]);

	const filteredOrdersCount = orders.length;
	const totalOrdersCount = data?.length ?? 0;

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
					<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">
						Broker Orders {broker ? `(${broker.toUpperCase()})` : ''}
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
					disabled={isLoading}
					className="px-3 py-2 sm:py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px] sm:min-h-0 w-full sm:w-auto"
				>
					{isLoading ? 'Refreshing...' : 'Refresh'}
				</button>
			</div>

			{/* Status Filter Tabs */}
			<div className="flex flex-wrap gap-2">
				{STATUS_TABS.map((tab) => (
					<button
						key={tab.key}
						className={`px-3 py-2 sm:py-1 rounded border text-sm sm:text-base min-h-[44px] sm:min-h-0 ${
							statusFilter === tab.key
								? 'bg-blue-600 text-white border-blue-600'
								: 'bg-[var(--panel)] text-[var(--text)] border-[#1e293b] hover:bg-[#0f1720]'
						}`}
						onClick={() => setStatusFilter(tab.key)}
						aria-pressed={statusFilter === tab.key}
					>
						{tab.label} {tab.key !== 'all' && `(${data?.filter((o) => o.status === tab.key).length ?? 0})`}
					</button>
				))}
			</div>

			{/* Orders Table */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">
						{statusFilter === 'all' ? 'All Orders' : `${STATUS_TABS.find((t) => t.key === statusFilter)?.label} Orders`} ({filteredOrdersCount} / {totalOrdersCount})
					</div>
					{isLoading && <span className="text-xs sm:text-sm text-[var(--muted)]">Loading...</span>}
					{error && (() => {
						const brokerError = formatBrokerError(error);
						return (
							<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
								<div className="flex flex-col">
									<span className="text-xs sm:text-sm text-red-400">
										Failed to load orders: {brokerError.message}
										{brokerError.statusCode && ` (${brokerError.statusCode})`}
									</span>
									{brokerError.retryable && failureCount && failureCount > 0 && (
										<span className="text-xs text-yellow-400">
											Retrying... (Attempt {failureCount}/3)
										</span>
									)}
								</div>
								<button
									onClick={() => refetch()}
									className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 min-h-[32px] sm:min-h-0"
								>
									Retry Now
								</button>
							</div>
						);
					})()}
				</div>
				<div className="overflow-x-auto -mx-2 sm:mx-0">
					<table className="w-full text-xs sm:text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th className="text-left p-2 whitespace-nowrap">Broker Order ID</th>
								<th className="text-left p-2 whitespace-nowrap">Symbol</th>
								<th className="text-left p-2 whitespace-nowrap">Side</th>
								<th className="text-left p-2 whitespace-nowrap">Qty</th>
								<th className="text-left p-2 whitespace-nowrap">Price</th>
								<th className="text-left p-2 whitespace-nowrap">Status</th>
								<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Created</th>
								<th className="text-left p-2 whitespace-nowrap">Exec Price</th>
								<th className="text-left p-2 whitespace-nowrap">Exec Qty</th>
							</tr>
						</thead>
						<tbody>
							{orders.map((order, index) => (
								<tr key={order.broker_order_id || index} className="border-t border-[#1e293b]">
									<td className="p-2 text-[var(--text)] font-mono text-xs">
										{order.broker_order_id || '-'}
									</td>
									<td className="p-2 text-[var(--text)] font-medium">{order.symbol}</td>
									<td className="p-2">
										<span className={`px-2 py-0.5 rounded text-xs font-medium ${getSideColor(order.side)}`}>
											{order.side.toUpperCase()}
										</span>
									</td>
									<td className="p-2 text-[var(--text)]">{order.quantity}</td>
									<td className="p-2 text-[var(--text)] font-mono">{formatPrice(order.price)}</td>
									<td className="p-2">
										<span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(order.status)}`}>
											{order.status.toUpperCase()}
										</span>
									</td>
									<td className="p-2 text-[var(--text)] text-xs hidden sm:table-cell">
										{formatDate(order.created_at)}
									</td>
									<td className="p-2 text-[var(--text)] font-mono">{formatPrice(order.execution_price)}</td>
									<td className="p-2 text-[var(--text)]">{order.execution_qty ?? '-'}</td>
								</tr>
							))}
							{orders.length === 0 && !isLoading && (
								<tr>
									<td className="p-2 text-[var(--muted)]" colSpan={9}>
										No orders found
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
