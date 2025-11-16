import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDailyPnl, getPnlSummary } from '@/api/pnl';

export function PnlPage() {
	const dailyQ = useQuery({ queryKey: ['pnl', 'daily'], queryFn: getDailyPnl });
	const summaryQ = useQuery({ queryKey: ['pnl', 'summary'], queryFn: getPnlSummary });

	useEffect(() => {
		document.title = 'PnL';
	}, []);

	return (
		<div className="p-4 space-y-4">
			<h1 className="text-xl font-semibold">PnL</h1>
			<div className="rounded border p-3">
				<div className="font-medium mb-2">Summary</div>
				{summaryQ.isLoading && <div className="text-sm text-gray-500">Loading summary...</div>}
				{summaryQ.isError && <div className="text-sm text-red-600">Failed to load summary</div>}
				{summaryQ.data && (
					<div className="text-sm">
						<div>Total PnL: {summaryQ.data.totalPnl.toFixed(2)}</div>
						<div>Green Days: {summaryQ.data.daysGreen}</div>
						<div>Red Days: {summaryQ.data.daysRed}</div>
					</div>
				)}
			</div>
			<div className="rounded border">
				<div className="flex items-center justify-between px-3 py-2 border-b">
					<div className="font-medium">Daily</div>
					{dailyQ.isLoading && <span className="text-sm text-gray-500">Loading...</span>}
					{dailyQ.isError && <span className="text-sm text-red-600">Failed to load</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
						<tr>
							<th className="text-left p-2">Date</th>
							<th className="text-left p-2">PnL</th>
						</tr>
					</thead>
					<tbody>
						{(dailyQ.data ?? []).map((d) => (
							<tr key={d.date} className="border-t">
								<td className="p-2">{d.date}</td>
								<td className="p-2">{d.pnl.toFixed(2)}</td>
							</tr>
						))}
						{(dailyQ.data ?? []).length === 0 && !dailyQ.isLoading && (
							<tr>
								<td className="p-2 text-gray-500" colSpan={2}>
									No PnL rows
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}
