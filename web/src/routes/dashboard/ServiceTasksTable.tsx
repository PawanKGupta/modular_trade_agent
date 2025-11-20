import { type TaskExecution } from '@/api/service';

interface ServiceTasksTableProps {
	tasks: TaskExecution[];
	isLoading: boolean;
}

export function ServiceTasksTable({ tasks, isLoading }: ServiceTasksTableProps) {
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
					{tasks.map((task) => (
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
	);
}
