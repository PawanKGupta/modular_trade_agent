import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listTargets } from '@/api/targets';

export function TargetsPage() {
	const { data, isLoading, isError } = useQuery({ queryKey: ['targets'], queryFn: listTargets });

	useEffect(() => {
		document.title = 'Targets';
	}, []);

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Targets</h1>
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">Tracked Targets</div>
					{isLoading && <span className="text-xs sm:text-sm text-[var(--muted)]">Loading...</span>}
					{isError && <span className="text-xs sm:text-sm text-red-400">Failed to load</span>}
				</div>
				<div className="overflow-x-auto -mx-2 sm:mx-0">
					<table className="w-full text-xs sm:text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th className="text-left p-2 whitespace-nowrap">Symbol</th>
								<th className="text-left p-2 whitespace-nowrap">Target Price</th>
								<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Note</th>
								<th className="text-left p-2 whitespace-nowrap hidden md:table-cell">Created</th>
							</tr>
						</thead>
					<tbody>
						{(data ?? []).map((t) => (
							<tr key={t.id} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)] font-medium">{t.symbol}</td>
								<td className="p-2 text-[var(--text)]">{t.target_price}</td>
								<td className="p-2 text-[var(--text)] hidden sm:table-cell">{t.note ?? '-'}</td>
								<td className="p-2 text-[var(--text)] text-xs hidden md:table-cell">{new Date(t.created_at).toLocaleDateString()}</td>
							</tr>
						))}
						{(data ?? []).length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-[var(--muted)]" colSpan={4}>
									No targets
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
