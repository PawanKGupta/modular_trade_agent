import { useState, useMemo } from 'react';
import { type TaskExecution } from '@/api/service';

interface ServiceTasksTableProps {
	tasks: TaskExecution[];
	isLoading: boolean;
}

export function ServiceTasksTable({ tasks, isLoading }: ServiceTasksTableProps) {
	const [currentPage, setCurrentPage] = useState(1);
	const [pageSize, setPageSize] = useState(10);

	// Calculate pagination
	const totalPages = Math.ceil(tasks.length / pageSize);
	const startIndex = (currentPage - 1) * pageSize;
	const endIndex = startIndex + pageSize;
	const currentTasks = useMemo(() => tasks.slice(startIndex, endIndex), [tasks, startIndex, endIndex]);

	// Reset to page 1 when page size changes
	const handlePageSizeChange = (newSize: number) => {
		setPageSize(newSize);
		setCurrentPage(1);
	};

	// Reset to page 1 when tasks change (e.g., filter or new data)
	useMemo(() => {
		if (currentPage > totalPages && totalPages > 0) {
			setCurrentPage(1);
		}
	}, [tasks.length, totalPages, currentPage]);

	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading tasks...</div>;
	}

	if (tasks.length === 0) {
		return <div className="text-sm text-[var(--muted)]">No task executions found</div>;
	}

	const getStatusColor = (status: string) => {
		switch (status) {
			case 'success':
				return 'text-green-400';
			case 'failed':
				return 'text-red-400';
			case 'skipped':
				return 'text-yellow-400';
			default:
				return 'text-[var(--muted)]';
		}
	};

	return (
		<div className="space-y-4">
			{/* Pagination Controls - Top */}
			<div className="flex items-center justify-between text-sm">
				<div className="text-[var(--muted)]">
					Showing {startIndex + 1}-{Math.min(endIndex, tasks.length)} of {tasks.length} tasks
				</div>
				<div className="flex items-center gap-4">
					<div className="flex items-center gap-2">
						<label className="text-[var(--muted)]">Per page:</label>
						<select
							value={pageSize}
							onChange={(e) => handlePageSizeChange(Number(e.target.value))}
							className="bg-[#0f1720] border border-[#1e293b] rounded px-2 py-1 text-[var(--text)] focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option value={10}>10</option>
							<option value={25}>25</option>
							<option value={50}>50</option>
						</select>
					</div>
					<div className="flex items-center gap-2">
						<button
							onClick={() => setCurrentPage(1)}
							disabled={currentPage === 1}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b] text-[var(--text)] hover:bg-[#1e293b] disabled:opacity-50 disabled:cursor-not-allowed"
							title="First page"
						>
							«
						</button>
						<button
							onClick={() => setCurrentPage(currentPage - 1)}
							disabled={currentPage === 1}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b] text-[var(--text)] hover:bg-[#1e293b] disabled:opacity-50 disabled:cursor-not-allowed"
							title="Previous page"
						>
							‹
						</button>
						<span className="text-[var(--text)] px-2">
							Page {currentPage} of {totalPages}
						</span>
						<button
							onClick={() => setCurrentPage(currentPage + 1)}
							disabled={currentPage === totalPages}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b] text-[var(--text)] hover:bg-[#1e293b] disabled:opacity-50 disabled:cursor-not-allowed"
							title="Next page"
						>
							›
						</button>
						<button
							onClick={() => setCurrentPage(totalPages)}
							disabled={currentPage === totalPages}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b] text-[var(--text)] hover:bg-[#1e293b] disabled:opacity-50 disabled:cursor-not-allowed"
							title="Last page"
						>
							»
						</button>
					</div>
				</div>
			</div>

			{/* Table */}
			<div className="overflow-x-auto">
				<table className="w-full text-sm">
					<thead>
						<tr className="border-b border-[#1e293b]">
							<th className="text-left p-2 text-[var(--muted)]">Task Name</th>
							<th className="text-left p-2 text-[var(--muted)]">Executed At</th>
							<th className="text-left p-2 text-[var(--muted)]">Status</th>
							<th className="text-left p-2 text-[var(--muted)]">Duration</th>
							<th className="text-left p-2 text-[var(--muted)]">Details</th>
						</tr>
					</thead>
					<tbody>
						{currentTasks.map((task) => (
							<tr key={task.id} className="border-b border-[#1e293b] hover:bg-[#0f1720]">
								<td className="p-2 font-medium text-[var(--text)]">{task.task_name}</td>
								<td className="p-2 text-[var(--muted)]">
									{new Date(task.executed_at).toLocaleString()}
								</td>
								<td className={`p-2 font-medium ${getStatusColor(task.status)}`}>
									{task.status.toUpperCase()}
								</td>
								<td className="p-2 text-[var(--text)]">{task.duration_seconds.toFixed(2)}s</td>
								<td className="p-2">
									{task.details ? (
										<details className="cursor-pointer">
											<summary className="text-blue-400 hover:text-blue-300">View</summary>
											<pre className="mt-2 p-2 bg-[#0f1720] rounded text-xs overflow-auto max-h-32 text-[var(--text)]">
												{JSON.stringify(task.details, null, 2)}
											</pre>
										</details>
									) : (
										<span className="text-[var(--muted)]">-</span>
									)}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}
