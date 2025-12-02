import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listActivity, type ActivityItem } from '@/api/activity';

const LEVELS: Array<ActivityItem['level'] | 'all'> = ['all', 'info', 'warn', 'error'];

export function ActivityPage() {
	const [level, setLevel] = useState<ActivityItem['level'] | 'all'>('all');
	const { data, isLoading, isError } = useQuery({
		queryKey: ['activity', level],
		queryFn: () => listActivity(level === 'all' ? undefined : level),
	});

	useEffect(() => {
		document.title = 'Activity';
	}, []);

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">Activity</h1>
			<div className="flex items-center gap-2">
				<label htmlFor="level" className="text-xs sm:text-sm text-[var(--text)]">Level</label>
				<select
					id="level"
					className="bg-[#0f1720] border border-[#1e293b] rounded px-3 py-2 sm:py-1 text-sm text-[var(--text)] min-h-[44px] sm:min-h-0"
					value={level}
					onChange={(e) => setLevel(e.target.value as any)}
				>
					{LEVELS.map((l) => (
						<option key={l} value={l}>
							{l}
						</option>
					))}
				</select>
			</div>
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">Recent Activity</div>
					{isLoading && <span className="text-xs sm:text-sm text-[var(--muted)]">Loading...</span>}
					{isError && <span className="text-xs sm:text-sm text-red-400">Failed to load</span>}
				</div>
				<div className="overflow-x-auto -mx-2 sm:mx-0">
					<table className="w-full text-xs sm:text-sm">
						<thead className="bg-[#0f172a] text-[var(--muted)]">
							<tr>
								<th className="text-left p-2 whitespace-nowrap">Time</th>
								<th className="text-left p-2 whitespace-nowrap">Event</th>
								<th className="text-left p-2 whitespace-nowrap hidden sm:table-cell">Detail</th>
								<th className="text-left p-2 whitespace-nowrap">Level</th>
							</tr>
						</thead>
					<tbody>
						{(data ?? []).map((a) => (
							<tr key={a.id} className="border-t border-[#1e293b]">
								<td className="p-2 text-[var(--text)] text-xs">{new Date(a.ts).toLocaleString()}</td>
								<td className="p-2 text-[var(--text)]">{a.event}</td>
								<td className="p-2 text-[var(--text)] hidden sm:table-cell">{a.detail ?? '-'}</td>
								<td className="p-2 text-[var(--text)]">{a.level ?? 'info'}</td>
							</tr>
						))}
						{(data ?? []).length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-[var(--muted)]" colSpan={4}>
									No activity
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
