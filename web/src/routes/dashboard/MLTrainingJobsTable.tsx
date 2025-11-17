import type { MLTrainingJob } from '@/api/ml-training';

interface Props {
	jobs: MLTrainingJob[];
	isLoading: boolean;
}

export function MLTrainingJobsTable({ jobs, isLoading }: Props) {
	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading training jobs...</div>;
	}

	if (!jobs.length) {
		return <div className="text-sm text-[var(--muted)]">No training jobs yet.</div>;
	}

	return (
		<div className="overflow-x-auto">
			<table className="w-full text-sm">
				<thead>
					<tr className="text-left text-[var(--muted)]">
						<th className="py-2 pr-4">Job</th>
						<th className="py-2 pr-4">Model</th>
						<th className="py-2 pr-4">Algorithm</th>
						<th className="py-2 pr-4">Status</th>
						<th className="py-2 pr-4">Accuracy</th>
						<th className="py-2">Started</th>
					</tr>
				</thead>
				<tbody>
					{jobs.map((job) => (
						<tr key={job.id} className="border-t border-[#1e293b]">
							<td className="py-2 pr-4 font-mono text-xs">#{job.id}</td>
							<td className="py-2 pr-4">{job.model_type}</td>
							<td className="py-2 pr-4">{job.algorithm}</td>
							<td className="py-2 pr-4">
								<span
									className={`px-2 py-1 rounded-full text-xs ${
										job.status === 'completed'
											? 'bg-green-500/20 text-green-300'
											: job.status === 'failed'
												? 'bg-red-500/20 text-red-300'
												: 'bg-slate-500/20 text-slate-200'
									}`}
								>
									{job.status}
								</span>
							</td>
							<td className="py-2 pr-4">
								{job.accuracy !== null ? `${(job.accuracy * 100).toFixed(2)}%` : '—'}
							</td>
							<td className="py-2 text-[var(--muted)]">
								{new Date(job.started_at).toLocaleString()}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
