import type { MLModel } from '@/api/ml-training';

interface Props {
	models: MLModel[];
	isLoading: boolean;
	onActivate: (modelId: number) => void;
	activatingModelId?: number | null;
}

export function MLModelsTable({ models, isLoading, onActivate, activatingModelId }: Props) {
	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading models...</div>;
	}

	if (!models.length) {
		return <div className="text-sm text-[var(--muted)]">No trained models yet.</div>;
	}

	return (
		<div className="overflow-x-auto -mx-2 sm:mx-0">
			<table className="w-full text-xs sm:text-sm">
				<thead>
					<tr className="text-left text-[var(--muted)]">
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Model</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap hidden sm:table-cell">Version</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Accuracy</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap">Status</th>
						<th className="py-2 pr-2 sm:pr-4 whitespace-nowrap hidden md:table-cell">Created</th>
						<th className="py-2 whitespace-nowrap">Action</th>
					</tr>
				</thead>
				<tbody>
					{models.map((model) => (
						<tr key={model.id} className="border-t border-[#1e293b]">
							<td className="py-2 pr-2 sm:pr-4 text-xs sm:text-sm">{model.model_type}</td>
							<td className="py-2 pr-2 sm:pr-4 font-mono text-xs hidden sm:table-cell">{model.version}</td>
							<td className="py-2 pr-2 sm:pr-4 text-xs sm:text-sm">
								{model.accuracy !== null ? `${(model.accuracy * 100).toFixed(2)}%` : '-'}
							</td>
							<td className="py-2 pr-2 sm:pr-4">
								{model.is_active ? (
									<span className="px-2 py-1 rounded-full text-xs bg-green-500/20 text-green-300">
										Active
									</span>
								) : (
									<span className="px-2 py-1 rounded-full text-xs bg-slate-500/20 text-slate-200">
										Inactive
									</span>
								)}
							</td>
							<td className="py-2 pr-2 sm:pr-4 text-[var(--muted)] text-xs hidden md:table-cell">
								{new Date(model.created_at).toLocaleString()}
							</td>
							<td className="py-2">
								{model.is_active ? (
									<span className="text-xs text-green-300 font-medium">In Use</span>
								) : (
									<button
										type="button"
										onClick={() => onActivate(model.id)}
										className="text-xs px-3 py-2 sm:px-2 sm:py-1 text-[var(--accent)] disabled:opacity-50 min-h-[36px] sm:min-h-0"
										disabled={activatingModelId === model.id}
									>
										{activatingModelId === model.id ? 'Activating...' : 'Activate'}
									</button>
								)}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
