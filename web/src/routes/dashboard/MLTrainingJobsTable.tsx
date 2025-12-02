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
		<div className="overflow-x-auto -mx-2 sm:mx-0">
			<table className="w-full text-xs sm:text-sm">
				<thead>
					<tr className="text-left text-[var(--muted)]">
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Job</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap hidden sm:table-cell">Model</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap hidden md:table-cell">Algorithm</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Status</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Accuracy</th>
						<th className="py-2 whitespace-nowrap hidden lg:table-cell">Started</th>
					</tr>
				</thead>
				<tbody>
					{jobs.map((job) => (
						<tr key={job.id} className="border-t border-[#1e293b]">
							<td className="py-2 pr-2 sm:pr-4 font-mono text-xs">#{job.id}</td>
							<td className="py-2 pr-2 sm:pr-4 text-xs sm:text-sm hidden sm:table-cell">{job.model_type}</td>
							<td className="py-2 pr-2 sm:pr-4 text-xs sm:text-sm hidden md:table-cell">{job.algorithm}</td>
							<td className="py-2 pr-2 sm:pr-4">
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
							<td className="py-2 pr-2 sm:pr-4 text-xs sm:text-sm">
								{job.accuracy !== null ? `${(job.accuracy * 100).toFixed(2)}%` : '-'}
							</td>
							<td className="py-2 text-[var(--muted)] text-xs hidden lg:table-cell">
								{new Date(job.started_at).toLocaleString()}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
