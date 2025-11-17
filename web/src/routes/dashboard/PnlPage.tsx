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
			<h1 className="text-xl font-semibold text-[var(--text)]">PnL</h1>
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3">
				<div className="font-medium mb-2 text-[var(--text)]">Summary</div>
				{summaryQ.isLoading && <div className="text-sm text-[var(--muted)]">Loading summary...</div>}
				{summaryQ.isError && <div className="text-sm text-red-400">Failed to load summary</div>}
				{summaryQ.data && (
					<div className="text-sm text-[var(--text)]">
						<div>Total PnL: {summaryQ.data.totalPnl.toFixed(2)}</div>
						<div>Green Days: {summaryQ.data.daysGreen}</div>
						<div>Red Days: {summaryQ.data.daysRed}</div>
					</div>
				)}
			</div>
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Daily</div>
					{dailyQ.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{dailyQ.isError && <span className="text-sm text-red-400">Failed to load</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-[#0f172a] text-[var(--muted)]">
						<tr>
							<th className="text-left p-2">Date</th>
							<th className="text-left p-2">PnL</th>
						</tr>
					</thead>
					<tbody>
						{(dailyQ.data ?? []).map((d) => (
							<tr key={d.date} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)]">{d.date}</td>
								<td className="p-2 text-[var(--text)]">{d.pnl.toFixed(2)}</td>
							</tr>
						))}
						{(dailyQ.data ?? []).length === 0 && !dailyQ.isLoading && (
							<tr>
								<td className="p-2 text-[var(--muted)]" colSpan={2}>
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
