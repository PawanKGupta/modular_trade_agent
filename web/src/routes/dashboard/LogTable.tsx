import type { ServiceLogEntry } from '@/api/logs';
import { ContextViewer } from './ContextViewer';
import { LogIdCell } from './LogIdCell';

type Props = {
	logs: ServiceLogEntry[];
	isLoading?: boolean;
	isRefreshing?: boolean;
	showId?: boolean;
	searchTerm?: string;
};

export function LogTable({ logs, isLoading, isRefreshing, showId = false, searchTerm }: Props) {
	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading logs...</div>;
	}

	if (!logs.length) {
		return <div className="text-sm text-[var(--muted)]">No logs found for the selected filters.</div>;
	}

	return (
		<div className="relative">
			{isRefreshing && (
				<div className="absolute top-2 right-2 z-10 flex items-center gap-2 text-xs text-blue-400">
					<div className="animate-spin">⟳</div>
					<span>Refreshing...</span>
				</div>
			)}
			<div className="overflow-x-auto -mx-2 sm:mx-0 rounded border border-[#1f2937]">
				<table className="w-full text-xs sm:text-sm text-left">
					<thead className="bg-[#0f172a] text-[var(--muted)]">
						<tr>
							<th className="px-2 sm:px-3 py-2 whitespace-nowrap">Time</th>
							{showId && (
								<th className="px-2 sm:px-3 py-2 whitespace-nowrap hidden lg:table-cell">ID</th>
							)}
							<th className="px-2 sm:px-3 py-2 whitespace-nowrap hidden sm:table-cell">Level</th>
							<th className="px-2 sm:px-3 py-2 whitespace-nowrap hidden md:table-cell">Module</th>
							<th className="px-2 sm:px-3 py-2">Message</th>
						</tr>
					</thead>
					<tbody>
						{logs.map((log) => (
							<tr key={String(log.id)} className="border-t border-[#1f2937]">
								<td className="px-2 sm:px-3 py-2 whitespace-nowrap text-xs sm:text-sm">
									{new Date(log.timestamp).toLocaleString()}
								</td>
								{showId && (
									<td className="px-2 sm:px-3 py-2 text-xs hidden lg:table-cell">
										<LogIdCell log={log} />
									</td>
								)}
								<td className="px-2 sm:px-3 py-2 font-mono text-xs hidden sm:table-cell">{log.level}</td>
								<td className="px-2 sm:px-3 py-2 text-xs hidden md:table-cell">{log.module}</td>
								<td className="px-2 sm:px-3 py-2">
									<div className="text-xs sm:text-sm">{log.message}</div>
									<ContextViewer context={log.context} searchTerm={searchTerm} />
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}
