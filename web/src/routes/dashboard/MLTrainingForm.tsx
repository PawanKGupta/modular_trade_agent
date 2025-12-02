import { FormEvent, useMemo, useState } from 'react';
import type { StartTrainingPayload } from '@/api/ml-training';

interface Props {
	onSubmit: (payload: StartTrainingPayload) => void;
	isSubmitting: boolean;
}

export function MLTrainingForm({ onSubmit, isSubmitting }: Props) {
	const [modelType, setModelType] = useState<StartTrainingPayload['model_type']>('verdict_classifier');
	const [algorithm, setAlgorithm] = useState<StartTrainingPayload['algorithm']>('xgboost');
	const [trainingDataPath, setTrainingDataPath] = useState('data/training/verdict_classifier.csv');
	const [hyperparametersText, setHyperparametersText] = useState('{"max_depth": 6, "learning_rate": 0.1}');
	const [notes, setNotes] = useState<string>('');
	const [autoActivate, setAutoActivate] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const parsedHyperparameters = useMemo<Record<string, string | number | boolean>>(() => {
		try {
			if (!hyperparametersText.trim()) {
				return {};
			}
			const parsed = JSON.parse(hyperparametersText);
			if (typeof parsed !== 'object' || Array.isArray(parsed)) {
				return {};
			}
			return parsed;
		} catch {
			return {};
		}
	}, [hyperparametersText]);

	function handleSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		setError(null);

		if (!trainingDataPath.trim()) {
			setError('Training data path is required');
			return;
		}

		try {
			const payload: StartTrainingPayload = {
				model_type: modelType,
				algorithm,
				training_data_path: trainingDataPath.trim(),
				hyperparameters: parsedHyperparameters,
				notes: notes.trim() || undefined,
				auto_activate: autoActivate,
			};
			onSubmit(payload);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to submit training job');
		}
	}

	return (
		<form onSubmit={handleSubmit} className="space-y-3 sm:space-y-4" aria-label="ML Training Form">
			<div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
				<label className="text-xs sm:text-sm flex flex-col gap-1">
					<span className="text-[var(--muted)]">Model Type</span>
					<select
						value={modelType}
						onChange={(e) => setModelType(e.target.value as StartTrainingPayload['model_type'])}
						className="bg-transparent border border-[#1e293b] rounded px-3 py-2.5 sm:p-2 text-xs sm:text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="verdict_classifier">Verdict Classifier</option>
						<option value="price_regressor">Price Regressor</option>
					</select>
				</label>

				<label className="text-xs sm:text-sm flex flex-col gap-1">
					<span className="text-[var(--muted)]">Algorithm</span>
					<select
						value={algorithm}
						onChange={(e) => setAlgorithm(e.target.value as StartTrainingPayload['algorithm'])}
						className="bg-transparent border border-[#1e293b] rounded px-3 py-2.5 sm:p-2 text-xs sm:text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="xgboost">XGBoost</option>
						<option value="random_forest">Random Forest</option>
						<option value="logistic_regression">Logistic Regression</option>
					</select>
				</label>
			</div>

			<label className="text-xs sm:text-sm flex flex-col gap-1">
				<span className="text-[var(--muted)]">Training Data Path</span>
				<input
					type="text"
					value={trainingDataPath}
					onChange={(e) => setTrainingDataPath(e.target.value)}
					placeholder="data/training/verdict_classifier.csv"
					className="bg-transparent border border-[#1e293b] rounded px-3 py-2.5 sm:p-2 text-xs sm:text-sm min-h-[44px] sm:min-h-0"
				/>
			</label>

			<label className="text-sm flex flex-col gap-1">
				<span className="text-[var(--muted)]">Hyperparameters (JSON)</span>
				<textarea
					value={hyperparametersText}
					onChange={(e) => setHyperparametersText(e.target.value)}
					rows={4}
					className="bg-transparent border border-[#1e293b] rounded p-2 text-sm font-mono"
				/>
				<span className="text-[var(--muted)] text-xs">
					Example: {"{ \"max_depth\": 6, \"learning_rate\": 0.1 }"}
				</span>
			</label>

			<label className="text-sm flex flex-col gap-1">
				<span className="text-[var(--muted)]">Notes (optional)</span>
				<textarea
					value={notes}
					onChange={(e) => setNotes(e.target.value)}
					rows={2}
					className="bg-transparent border border-[#1e293b] rounded p-2 text-sm"
				/>
			</label>

			<label className="text-sm flex items-center gap-2">
				<input
					type="checkbox"
					checked={autoActivate}
					onChange={(e) => setAutoActivate(e.target.checked)}
				/>
				<span>Auto-activate new model version</span>
			</label>

			{error && <div className="text-sm text-red-400">{error}</div>}

			<button
				type="submit"
				className="px-4 py-2 bg-[var(--accent)] text-[var(--background)] rounded text-sm font-medium disabled:opacity-50"
				disabled={isSubmitting}
			>
				{isSubmitting ? 'Starting Training...' : 'Start Training'}
			</button>
		</form>
	);
}
