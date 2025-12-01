import { type ServiceLog } from '@/api/service';
import { useState } from 'react';

interface ServiceLogsViewerProps {
	logs: ServiceLog[];
	isLoading: boolean;
}

export function ServiceLogsViewer({ logs, isLoading }: ServiceLogsViewerProps) {
	const [filterLevel, setFilterLevel] = useState<string>('all');
	const [filterModule, setFilterModule] = useState<string>('all');

	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading logs...</div>;
	}

	// Get unique modules
	const modules = Array.from(new Set(logs.map((log) => log.module))).sort();

	// Filter logs
	const filteredLogs = logs.filter((log) => {
		if (filterLevel !== 'all' && log.level !== filterLevel) return false;
		if (filterModule !== 'all' && log.module !== filterModule) return false;
		return true;
	});

	const getLevelColor = (level: string) => {
		switch (level) {
			case 'DEBUG':
				return 'text-gray-400';
			case 'INFO':
				return 'text-blue-400';
			case 'WARNING':
				return 'text-yellow-400';
			case 'ERROR':
				return 'text-red-400';
			case 'CRITICAL':
				return 'text-red-600 font-bold';
			default:
				return 'text-[var(--muted)]';
		}
	};

	if (logs.length === 0) {
		return <div className="text-sm text-[var(--muted)]">No logs found</div>;
	}

	return (
		<div className="space-y-4">
			{/* Filters */}
			<div className="flex gap-4 items-center">
				<div>
					<label htmlFor="log-level-filter" className="text-sm text-[var(--muted)] mr-2">Level:</label>
					<select
						id="log-level-filter"
						value={filterLevel}
						onChange={(e) => setFilterLevel(e.target.value)}
						className="bg-[#0f1720] border border-[#1e293b] rounded px-2 py-1 text-sm"
					>
						<option value="all">All</option>
						<option value="DEBUG">DEBUG</option>
						<option value="INFO">INFO</option>
						<option value="WARNING">WARNING</option>
						<option value="ERROR">ERROR</option>
						<option value="CRITICAL">CRITICAL</option>
					</select>
				</div>
				<div>
					<label htmlFor="log-module-filter" className="text-sm text-[var(--muted)] mr-2">Module:</label>
					<select
						id="log-module-filter"
						value={filterModule}
						onChange={(e) => setFilterModule(e.target.value)}
						className="bg-[#0f1720] border border-[#1e293b] rounded px-2 py-1 text-sm"
					>
						<option value="all">All</option>
						{modules.map((module) => (
							<option key={module} value={module}>
								{module}
							</option>
						))}
					</select>
				</div>
				<div className="text-sm text-[var(--muted)]">
					Showing {filteredLogs.length} of {logs.length} logs
				</div>
			</div>

			{/* Logs List */}
			<div className="space-y-2 max-h-96 overflow-y-auto">
				{filteredLogs.map((log) => (
					<div
						key={log.id}
						className="p-3 bg-[#0f1720] border border-[#1e293b] rounded text-sm"
					>
						<div className="flex items-start justify-between gap-4 mb-1">
							<div className="flex items-center gap-2">
								<span className={`font-medium ${getLevelColor(log.level)}`}>
									[{log.level}]
								</span>
								<span className="text-[var(--muted)]">{log.module}</span>
							</div>
							<span className="text-[var(--muted)] text-xs">
								{new Date(log.timestamp).toLocaleString()}
							</span>
						</div>
						<div className="text-white mb-1">{log.message}</div>
						{log.context && Object.keys(log.context).length > 0 && (
							<details className="mt-2">
								<summary className="text-blue-400 hover:text-blue-300 cursor-pointer text-xs">
									Context
								</summary>
								<pre className="mt-2 p-2 bg-[#0a0e14] rounded text-xs overflow-auto">
									{JSON.stringify(log.context, null, 2)}
								</pre>
							</details>
						)}
					</div>
				))}
			</div>
		</div>
	);
}
