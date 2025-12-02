import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDailyPnl, getPnlSummary } from '@/api/pnl';

function formatMoney(amount: number): string {
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function PnlPage() {
	const dailyQ = useQuery({
		queryKey: ['pnl', 'daily'],
		queryFn: getDailyPnl,
		refetchInterval: 30000, // Refresh every 30 seconds (less frequent than paper trading)
	});
	const summaryQ = useQuery({
		queryKey: ['pnl', 'summary'],
		queryFn: getPnlSummary,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	useEffect(() => {
		document.title = 'PnL';
	}, []);

	// Format last update time
	const lastUpdate = summaryQ.dataUpdatedAt ? new Date(summaryQ.dataUpdatedAt).toLocaleTimeString() : 'Never';

	return (
		<div className="p-4 space-y-4">
			<div className="flex items-center justify-between">
				<div className="flex items-center gap-3">
					<h1 className="text-xl font-semibold text-[var(--text)]">Profit & Loss</h1>
					<div className="flex items-center gap-2">
						<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
						<span className="text-xs text-[var(--muted)]">
							Live • Last update: {lastUpdate}
						</span>
					</div>
				</div>
				<button
					onClick={() => {
						summaryQ.refetch();
						dailyQ.refetch();
					}}
					className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
				>
					Refresh
				</button>
			</div>

			{/* Summary Section */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Summary</div>
				</div>
				<div className="p-4">
					{summaryQ.isLoading && <div className="text-sm text-[var(--muted)]">Loading summary...</div>}
					{summaryQ.isError && <div className="text-sm text-red-400">Failed to load summary</div>}
					{summaryQ.data && (
						<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
							<div>
								<div className="text-sm text-[var(--muted)]">Total P&L</div>
								<div
									className={`text-2xl font-semibold ${
										summaryQ.data.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
									}`}
								>
									{formatMoney(summaryQ.data.totalPnl)}
								</div>
							</div>
							<div>
								<div className="text-sm text-[var(--muted)]">Profitable Days</div>
								<div className="text-2xl font-semibold text-green-400">
									{summaryQ.data.daysGreen}
								</div>
							</div>
							<div>
								<div className="text-sm text-[var(--muted)]">Loss Days</div>
								<div className="text-2xl font-semibold text-red-400">
									{summaryQ.data.daysRed}
								</div>
							</div>
						</div>
					)}
				</div>
			</div>
			{/* Daily P&L Section */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex items-center justify-between px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-[var(--text)]">Daily P&L</div>
					{dailyQ.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
					{dailyQ.isError && <span className="text-sm text-red-400">Failed to load</span>}
				</div>
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th className="text-left p-2 whitespace-nowrap">Date</th>
								<th className="text-right p-2 whitespace-nowrap">P&L</th>
								<th className="text-right p-2 whitespace-nowrap">Status</th>
							</tr>
						</thead>
						<tbody>
							{(dailyQ.data ?? []).map((d) => (
								<tr key={d.date} className="border-t border-[#1e293b]">
									<td className="p-2 text-[var(--text)]">{d.date}</td>
									<td
										className={`p-2 text-right font-medium ${
											d.pnl >= 0 ? 'text-green-400' : 'text-red-400'
										}`}
									>
										{formatMoney(d.pnl)}
									</td>
									<td className="p-2 text-right">
										<span
											className={`px-2 py-0.5 rounded text-xs ${
												d.pnl >= 0
													? 'bg-green-500/20 text-green-400'
													: 'bg-red-500/20 text-red-400'
											}`}
										>
											{d.pnl >= 0 ? 'Profit' : 'Loss'}
										</span>
									</td>
								</tr>
							))}
							{(dailyQ.data ?? []).length === 0 && !dailyQ.isLoading && (
								<tr>
									<td className="p-2 text-[var(--muted)] text-center" colSpan={3}>
										No P&L data available
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
