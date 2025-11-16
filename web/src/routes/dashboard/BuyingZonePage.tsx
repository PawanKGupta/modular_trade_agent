import { useQuery } from '@tanstack/react-query';
import { getBuyingZone, type BuyingZoneItem } from '@/api/signals';

export function BuyingZonePage() {
	const { data, isLoading, error } = useQuery<BuyingZoneItem[]>({
		queryKey: ['buying-zone'],
		queryFn: () => getBuyingZone(100),
	});

	if (isLoading) return <div>Loading...</div>;
	if (error) return <div className="text-red-400">Failed to load</div>;

	return (
		<div>
			<h2 className="text-lg font-semibold mb-4">Buying Zone</h2>
			<div className="overflow-auto">
				<table className="w-full text-sm">
					<thead className="text-left text-[var(--muted)]">
						<tr>
							<th className="py-2 pr-3">Symbol</th>
							<th className="py-2 pr-3">RSI10</th>
							<th className="py-2 pr-3">Dist to EMA9</th>
							<th className="py-2 pr-3">{'>'} EMA200</th>
							<th className="py-2 pr-3">Clean</th>
							<th className="py-2 pr-3">Monthly Support</th>
							<th className="py-2 pr-3">Confidence</th>
							<th className="py-2 pr-3">As of</th>
						</tr>
					</thead>
					<tbody>
						{(data ?? []).map((row) => {
							const aboveEma200 = row.ema200 != null && row.ema9 != null ? (row.ema9 > row.ema200) : null;
							return (
								<tr key={row.id} className="border-t border-[#1e293b]">
									<td className="py-2 pr-3">{row.symbol}</td>
									<td className="py-2 pr-3">{row.rsi10?.toFixed(1) ?? '-'}</td>
									<td className="py-2 pr-3">{row.distance_to_ema9?.toFixed(2) ?? '-'}</td>
									<td className="py-2 pr-3">{aboveEma200 == null ? '-' : aboveEma200 ? 'Yes' : 'No'}</td>
									<td className="py-2 pr-3">{row.clean_chart == null ? '-' : row.clean_chart ? 'Yes' : 'No'}</td>
									<td className="py-2 pr-3">{row.monthly_support_dist?.toFixed(2) ?? '-'}</td>
									<td className="py-2 pr-3">{row.confidence?.toFixed(2) ?? '-'}</td>
									<td className="py-2 pr-3">{new Date(row.ts).toLocaleString()}</td>
								</tr>
							);
						})}
					</tbody>
				</table>
			</div>
		</div>
	);
}
