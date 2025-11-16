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
		<div className="p-4 space-y-4">
			<h1 className="text-xl font-semibold">Activity</h1>
			<div className="flex items-center gap-2">
				<label htmlFor="level" className="text-sm">Level</label>
				<select id="level" className="border rounded px-2 py-1" value={level} onChange={(e) => setLevel(e.target.value as any)}>
					{LEVELS.map((l) => (
						<option key={l} value={l}>
							{l}
						</option>
					))}
				</select>
			</div>
			<div className="rounded border">
				<div className="flex items-center justify-between px-3 py-2 border-b">
					<div className="font-medium">Recent Activity</div>
					{isLoading && <span className="text-sm text-gray-500">Loading...</span>}
					{isError && <span className="text-sm text-red-600">Failed to load</span>}
				</div>
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
						<tr>
							<th className="text-left p-2">Time</th>
							<th className="text-left p-2">Event</th>
							<th className="text-left p-2">Detail</th>
							<th className="text-left p-2">Level</th>
						</tr>
					</thead>
					<tbody>
						{(data ?? []).map((a) => (
							<tr key={a.id} className="border-t">
								<td className="p-2">{new Date(a.ts).toLocaleString()}</td>
								<td className="p-2">{a.event}</td>
								<td className="p-2">{a.detail ?? '-'}</td>
								<td className="p-2">{a.level ?? 'info'}</td>
							</tr>
						))}
						{(data ?? []).length === 0 && !isLoading && (
							<tr>
								<td className="p-2 text-gray-500" colSpan={4}>
									No activity
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>
	);
}
