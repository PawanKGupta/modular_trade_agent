import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listTargets } from '@/api/targets';

export function TargetsPage() {
	const { data, isLoading, isError } = useQuery({ queryKey: ['targets'], queryFn: listTargets });

	useEffect(() => {
		document.title = 'Targets';
	}, []);

	return (
		<div className="p-4 space-y-4">
			<h1 className="text-xl font-semibold">Targets</h1>
			<div className="rounded border">
				<div className="flex items-center justify-between px-3 py-2 border-b">
					<div className="font-medium">Tracked Targets</div>
					{isLoading && <span className="text-sm text-gray-500">Loading...</span>}
					{isError && <span className="text-sm text-red-600">Failed to load</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
						<tr>
							<th className="text-left p-2">Symbol</th>
							<th className="text-left p-2">Target Price</th>
							<th className="text-left p-2">Note</th>
							<th className="text-left p-2">Created</th>
						</tr>
					</thead>
					<tbody>
						{(data ?? []).map((t) => (
							<tr key={t.id} className="border-t">
								<td className="p-2">{t.symbol}</td>
								<td className="p-2">{t.target_price}</td>
								<td className="p-2">{t.note ?? '-'}</td>
								<td className="p-2">{new Date(t.created_at).toLocaleDateString()}</td>
							</tr>
						))}
						{(data ?? []).length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-gray-500" colSpan={4}>
									No targets
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}
