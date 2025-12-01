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
		<div className="overflow-x-auto">
			<table className="w-full text-sm">
				<thead>
					<tr className="text-left text-[var(--muted)]">
						<th className="py-2 pr-4">Model</th>
						<th className="py-2 pr-4">Version</th>
						<th className="py-2 pr-4">Accuracy</th>
						<th className="py-2 pr-4">Status</th>
						<th className="py-2 pr-4">Created</th>
						<th className="py-2">Action</th>
					</tr>
				</thead>
				<tbody>
					{models.map((model) => (
						<tr key={model.id} className="border-t border-[#1e293b]">
							<td className="py-2 pr-4">{model.model_type}</td>
							<td className="py-2 pr-4 font-mono text-xs">{model.version}</td>
							<td className="py-2 pr-4">
								{model.accuracy !== null ? `${(model.accuracy * 100).toFixed(2)}%` : '-'}
							</td>
							<td className="py-2 pr-4">
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
							<td className="py-2 pr-4 text-[var(--muted)]">
								{new Date(model.created_at).toLocaleString()}
							</td>
							<td className="py-2">
								{model.is_active ? (
									<span className="text-xs text-green-300 font-medium">In Use</span>
								) : (
									<button
										type="button"
										onClick={() => onActivate(model.id)}
										className="text-xs text-[var(--accent)] disabled:opacity-50"
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
