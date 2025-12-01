import type { ServiceLogEntry } from '@/api/logs';

type Props = {
	logs: ServiceLogEntry[];
	isLoading?: boolean;
};

export function LogTable({ logs, isLoading }: Props) {
	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading logs...</div>;
	}

	if (!logs.length) {
		return <div className="text-sm text-[var(--muted)]">No logs found for the selected filters.</div>;
	}

	return (
		<div className="overflow-auto rounded border border-[#1f2937]">
			<table className="w-full text-sm text-left">
				<thead className="bg-[#0f172a] text-[var(--muted)]">
					<tr>
						<th className="px-3 py-2">Time</th>
						<th className="px-3 py-2">Level</th>
						<th className="px-3 py-2">Module</th>
						<th className="px-3 py-2">Message</th>
					</tr>
				</thead>
				<tbody>
					{logs.map((log) => (
						<tr key={log.id} className="border-t border-[#1f2937]">
							<td className="px-3 py-2 whitespace-nowrap">
								{new Date(log.timestamp).toLocaleString()}
							</td>
							<td className="px-3 py-2 font-mono">{log.level}</td>
							<td className="px-3 py-2">{log.module}</td>
							<td className="px-3 py-2">
								<div>{log.message}</div>
								{log.context && (
									<div className="mt-1 text-[var(--muted)] text-xs">
										{JSON.stringify(log.context)}
									</div>
								)}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
