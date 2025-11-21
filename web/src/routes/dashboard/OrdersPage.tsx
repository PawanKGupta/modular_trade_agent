import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listOrders, retryOrder, dropOrder, type Order, type OrderStatus } from '@/api/orders';

const TABS: { key: OrderStatus; label: string }[] = [
	{ key: 'amo', label: 'AMO' },
	{ key: 'ongoing', label: 'Ongoing' },
	{ key: 'pending_execution', label: 'Pending Execution' },
	{ key: 'sell', label: 'Sell' },
	{ key: 'failed', label: 'Failed' },
	{ key: 'retry_pending', label: 'Retry Pending' },
	{ key: 'rejected', label: 'Rejected' },
	{ key: 'closed', label: 'Closed' },
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

export function OrdersPage() {
	const [tab, setTab] = useState<OrderStatus>('amo');
	const queryClient = useQueryClient();
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

	const orders: Order[] = useMemo(() => data ?? [], [data]);

	const handleRetry = async (orderId: number) => {
		if (confirm('Retry this order?')) {
			try {
				await retryMutation.mutateAsync(orderId);
			} catch (error) {
				alert('Failed to retry order');
			}
		}
	};

	const handleDrop = async (orderId: number) => {
		if (confirm('Drop this order from retry queue?')) {
			try {
				await dropMutation.mutateAsync(orderId);
			} catch (error) {
				alert('Failed to drop order');
			}
		}
	};

	const isFailedOrRetryPending = tab === 'failed' || tab === 'retry_pending';

	return (
		<div className="p-4 space-y-4">
			<h1 className="text-xl font-semibold text-[var(--text)]">Orders</h1>
			<div className="flex gap-2">
				{TABS.map((t) => (
					<button
						key={t.key}
						className={`px-3 py-1 rounded border ${
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
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">{TABS.find((t) => t.key === tab)?.label} Orders</div>
					{isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{isError && <span className="text-sm text-red-400">Failed to load orders</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-[#0f172a] text-[var(--muted)]">
						<tr>
							<th className="text-left p-2">Symbol</th>
							<th className="text-left p-2">Side</th>
							<th className="text-left p-2">Qty</th>
							<th className="text-left p-2">Price</th>
							<th className="text-left p-2">Status</th>
							{isFailedOrRetryPending && (
								<>
									<th className="text-left p-2">Failure Reason</th>
									<th className="text-left p-2">Retry Count</th>
									<th className="text-left p-2">Last Retry</th>
								</>
							)}
							{isFailedOrRetryPending && <th className="text-left p-2">Actions</th>}
						</tr>
					</thead>
					<tbody>
						{orders.map((o) => (
							<tr key={o.id} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)]">{o.symbol}</td>
								<td className="p-2 text-[var(--text)]">{o.side}</td>
								<td className="p-2 text-[var(--text)]">{o.quantity}</td>
								<td className="p-2 text-[var(--text)]">{formatPrice(o.price)}</td>
								<td className="p-2 text-[var(--text)]">{o.status}</td>
								{isFailedOrRetryPending && (
									<>
										<td className="p-2 text-[var(--text)]">
											{o.failure_reason || o.rejection_reason || '-'}
										</td>
										<td className="p-2 text-[var(--text)]">{o.retry_count ?? 0}</td>
										<td className="p-2 text-[var(--text)]">
											{formatDate(o.last_retry_attempt || o.first_failed_at)}
										</td>
									</>
								)}
								{isFailedOrRetryPending && (
									<td className="p-2">
										<div className="flex gap-2">
											<button
												onClick={() => handleRetry(o.id)}
												disabled={retryMutation.isPending}
												className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
											>
												Retry
											</button>
											<button
												onClick={() => handleDrop(o.id)}
												disabled={dropMutation.isPending}
												className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
									colSpan={isFailedOrRetryPending ? 9 : 5}
								>
									No orders
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}
