import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listTargets } from '@/api/targets';

function formatMoney(amount: number): string {
	return `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
	return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function TargetsPage() {
	const { data, isLoading, isError, refetch } = useQuery({
		queryKey: ['targets'],
		queryFn: listTargets,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	useEffect(() => {
		document.title = 'Targets';
	}, []);

	const activeTargets = (data ?? []).filter((t) => t.is_active);
	const achievedTargets = (data ?? []).filter((t) => !t.is_active && t.achieved_at);

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
				<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Price Targets</h1>
				<button
					onClick={() => refetch()}
					className="px-3 py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90"
				>
					Refresh
				</button>
			</div>

			{/* Stats */}
			{data && data.length > 0 && (
				<div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3">
						<div className="text-xs text-[var(--muted)]">Total Targets</div>
						<div className="text-lg sm:text-xl font-semibold text-[var(--text)]">{data.length}</div>
					</div>
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3">
						<div className="text-xs text-[var(--muted)]">Active</div>
						<div className="text-lg sm:text-xl font-semibold text-yellow-400">{activeTargets.length}</div>
					</div>
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3">
						<div className="text-xs text-[var(--muted)]">Achieved</div>
						<div className="text-lg sm:text-xl font-semibold text-green-400">{achievedTargets.length}</div>
					</div>
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-3">
						<div className="text-xs text-[var(--muted)]">Success Rate</div>
						<div className="text-lg sm:text-xl font-semibold text-blue-400">
							{data.length > 0 ? `${((achievedTargets.length / data.length) * 100).toFixed(0)}%` : '0%'}
						</div>
					</div>
				</div>
			)}

			{/* Active Targets */}
			{activeTargets.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
					<div className="px-3 py-2 border-b border-[#1e293b]">
						<div className="font-medium text-sm sm:text-base text-[var(--text)]">
							Active Targets ({activeTargets.length})
						</div>
					</div>
					<div className="overflow-x-auto -mx-2 sm:mx-0">
						<table className="w-full text-xs sm:text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2 whitespace-nowrap">Symbol</th>
									<th className="text-right p-2 whitespace-nowrap">Entry</th>
									<th className="text-right p-2 whitespace-nowrap">Current</th>
									<th className="text-right p-2 whitespace-nowrap">Target</th>
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Distance</th>
									<th className="text-right p-2 whitespace-nowrap hidden lg:table-cell">Qty</th>
								</tr>
							</thead>
							<tbody>
								{activeTargets.map((t) => {
									const distancePercent = t.current_price
										? ((t.target_price - t.current_price) / t.current_price) * 100
										: 0;

									return (
										<tr key={t.id} className="border-t border-[#1e293b]">
											<td className="p-2 text-[var(--text)] font-medium">{t.symbol}</td>
											<td className="p-2 text-right text-[var(--text)]">
												{formatMoney(t.entry_price || 0)}
											</td>
											<td className="p-2 text-right text-[var(--text)]">
												{formatMoney(t.current_price || 0)}
											</td>
											<td className="p-2 text-right text-[var(--text)] font-semibold">
												{formatMoney(t.target_price)}
											</td>
											<td
												className={`p-2 text-right font-medium hidden md:table-cell ${
													distancePercent <= 0 ? 'text-green-400' : 'text-yellow-400'
												}`}
											>
												{formatPercent(distancePercent)}
											</td>
											<td className="p-2 text-right text-[var(--text)] hidden lg:table-cell">
												{t.quantity}
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>
				</div>
			)}

			{/* Achieved Targets */}
			{achievedTargets.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
					<div className="px-3 py-2 border-b border-[#1e293b]">
						<div className="font-medium text-sm sm:text-base text-green-400">
							Achieved Targets ({achievedTargets.length})
						</div>
					</div>
					<div className="overflow-x-auto -mx-2 sm:mx-0">
						<table className="w-full text-xs sm:text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2 whitespace-nowrap">Symbol</th>
									<th className="text-right p-2 whitespace-nowrap">Entry</th>
									<th className="text-right p-2 whitespace-nowrap">Target</th>
									<th className="text-right p-2 whitespace-nowrap">Profit</th>
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Achieved</th>
									<th className="text-right p-2 whitespace-nowrap hidden lg:table-cell">Qty</th>
								</tr>
							</thead>
							<tbody>
								{achievedTargets.map((t) => {
									const profitPercent = t.entry_price
										? ((t.target_price - t.entry_price) / t.entry_price) * 100
										: 0;

									return (
										<tr key={t.id} className="border-t border-[#1e293b]">
											<td className="p-2 text-[var(--text)] font-medium">{t.symbol}</td>
											<td className="p-2 text-right text-[var(--text)]">
												{formatMoney(t.entry_price || 0)}
											</td>
											<td className="p-2 text-right text-green-400 font-semibold">
												{formatMoney(t.target_price)}
											</td>
											<td className="p-2 text-right text-green-400 font-semibold">
												{formatPercent(profitPercent)}
											</td>
											<td className="p-2 text-right text-[var(--muted)] text-xs hidden md:table-cell">
												{t.achieved_at
													? new Date(t.achieved_at).toLocaleDateString('en-IN', {
															year: 'numeric',
															month: 'short',
															day: 'numeric',
														})
													: '-'}
											</td>
											<td className="p-2 text-right text-[var(--text)] hidden lg:table-cell">
												{t.quantity}
											</td>
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>
				</div>
			)}

			{/* No Targets */}
			{!isLoading && !isError && (data ?? []).length === 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-8 text-center">
					<div className="text-[var(--muted)]">No price targets set yet</div>
					<div className="text-xs text-[var(--muted)] mt-2">
						Targets are automatically created from your trading signals and strategies
					</div>
				</div>
			)}

			{/* Loading & Error States */}
			{isLoading && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-8 text-center">
					<div className="text-sm text-[var(--muted)]">Loading targets...</div>
				</div>
			)}

			{isError && (
				<div className="bg-[var(--panel)] border border-red-500/30 rounded p-8 text-center">
					<div className="text-sm text-red-400">Failed to load targets</div>
					<button
						onClick={() => refetch()}
						className="mt-3 px-3 py-1 text-sm bg-red-500/20 text-red-400 rounded hover:bg-red-500/30"
					>
						Retry
					</button>
				</div>
			)}
		</div>
	);
}
