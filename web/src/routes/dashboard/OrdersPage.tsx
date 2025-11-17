import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listOrders, type Order, type OrderStatus } from '@/api/orders';

const TABS: { key: OrderStatus; label: string }[] = [
	{ key: 'amo', label: 'AMO' },
	{ key: 'ongoing', label: 'Ongoing' },
	{ key: 'sell', label: 'Sell' },
	{ key: 'closed', label: 'Closed' },
];

const formatPrice = (value: number | null | undefined): string => {
	if (typeof value !== 'number' || Number.isNaN(value)) {
		return '—';
	}
	const truncated = Math.trunc(value * 100) / 100;
	return truncated.toFixed(2);
};

export function OrdersPage() {
	const [tab, setTab] = useState<OrderStatus>('amo');
	const { data, isLoading, isError } = useQuery({
		queryKey: ['orders', tab],
		queryFn: () => listOrders(tab),
	});

	useEffect(() => {
		document.title = 'Orders';
	}, []);

	const orders: Order[] = useMemo(() => data ?? [], [data]);

	return (
		<div className="p-4 space-y-4">
			<h1 className="text-xl font-semibold">Orders</h1>
			<div className="flex gap-2">
				{TABS.map((t) => (
					<button
						key={t.key}
						className={`px-3 py-1 rounded border ${tab === t.key ? 'bg-blue-600 text-white' : 'bg-white'}`}
						onClick={() => setTab(t.key)}
						aria-pressed={tab === t.key}
					>
						{t.label}
					</button>
				))}
			</div>
			<div className="rounded border">
				<div className="flex items-center justify-between px-3 py-2 border-b">
					<div className="font-medium">{TABS.find((t) => t.key === tab)?.label} Orders</div>
					{isLoading && <span className="text-sm text-gray-500">Loading...</span>}
					{isError && <span className="text-sm text-red-600">Failed to load orders</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
						<tr>
							<th className="text-left p-2">Symbol</th>
							<th className="text-left p-2">Side</th>
							<th className="text-left p-2">Qty</th>
							<th className="text-left p-2">Price</th>
							<th className="text-left p-2">Status</th>
						</tr>
					</thead>
					<tbody>
						{orders.map((o) => (
							<tr key={o.id} className="border-t">
								<td className="p-2">{o.symbol}</td>
								<td className="p-2">{o.side}</td>
								<td className="p-2">{o.qty}</td>
								<td className="p-2">{formatPrice(o.price)}</td>
								<td className="p-2">{o.status}</td>
							</tr>
						))}
						{orders.length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-gray-500" colSpan={5}>
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
