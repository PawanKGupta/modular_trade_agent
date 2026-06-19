import { useState } from 'react';
import type { RegisterModelPayload } from '@/api/ml-training';

interface Props {
	onSubmit: (payload: RegisterModelPayload) => void;
	isSubmitting: boolean;
	serverError: string | null;
}

const MODEL_TYPES = [
	{ value: 'verdict_classifier', label: 'Verdict Classifier' },
	{ value: 'price_regressor', label: 'Price Regressor' },
] as const;

export function MLRegisterModelForm({ onSubmit, isSubmitting, serverError }: Props) {
	const [modelType, setModelType] =
		useState<RegisterModelPayload['model_type']>('verdict_classifier');
	const [modelPath, setModelPath] = useState('');
	const [version, setVersion] = useState('');
	const [accuracy, setAccuracy] = useState('');
	const [throughDate, setThroughDate] = useState('');
	const [notes, setNotes] = useState('');
	const [autoActivate, setAutoActivate] = useState(false);

	function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		onSubmit({
			model_type: modelType,
			model_path: modelPath.trim(),
			version: version.trim(),
			accuracy: accuracy !== '' ? parseFloat(accuracy) : null,
			training_data_through_date: throughDate || null,
			notes: notes.trim() || null,
			auto_activate: autoActivate,
		});
	}

	return (
		<form onSubmit={handleSubmit} className="space-y-3">
			<p className="text-xs text-[var(--muted)]">
				Register a model trained outside the UI (e.g. via script). The path must be the
				absolute path inside the container (e.g.{' '}
				<code className="font-mono">/app/models/verdict_model_random_forest.pkl</code>).
			</p>

			<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
				<div>
					<label className="block text-xs text-[var(--muted)] mb-1">Model Type</label>
					<select
						value={modelType}
						onChange={(e) =>
							setModelType(e.target.value as RegisterModelPayload['model_type'])
						}
						className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm"
						required
					>
						{MODEL_TYPES.map((t) => (
							<option key={t.value} value={t.value}>
								{t.label}
							</option>
						))}
					</select>
				</div>

				<div>
					<label className="block text-xs text-[var(--muted)] mb-1">Version</label>
					<input
						type="text"
						value={version}
						onChange={(e) => setVersion(e.target.value)}
						placeholder="e.g. v0-legacy"
						className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm font-mono"
						required
					/>
				</div>
			</div>

			<div>
				<label className="block text-xs text-[var(--muted)] mb-1">
					Model Path (absolute, inside container)
				</label>
				<input
					type="text"
					value={modelPath}
					onChange={(e) => setModelPath(e.target.value)}
					placeholder="/app/models/verdict_model_random_forest.pkl"
					className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm font-mono"
					required
				/>
			</div>

			<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
				<div>
					<label className="block text-xs text-[var(--muted)] mb-1">
						Accuracy (0–1, optional)
					</label>
					<input
						type="number"
						step="0.001"
						min="0"
						max="1"
						value={accuracy}
						onChange={(e) => setAccuracy(e.target.value)}
						placeholder="e.g. 0.732"
						className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm"
					/>
				</div>

				<div>
					<label className="block text-xs text-[var(--muted)] mb-1">
						Training data through (optional)
					</label>
					<input
						type="date"
						value={throughDate}
						onChange={(e) => setThroughDate(e.target.value)}
						className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm"
					/>
				</div>
			</div>

			<div>
				<label className="block text-xs text-[var(--muted)] mb-1">Notes (optional)</label>
				<input
					type="text"
					value={notes}
					onChange={(e) => setNotes(e.target.value)}
					placeholder="e.g. Phase 5 dataset, walk-forward validated"
					maxLength={512}
					className="w-full bg-[var(--input)] border border-[#1e293b] rounded px-3 py-2 text-sm"
				/>
			</div>

			<label className="flex items-center gap-2 text-sm cursor-pointer select-none">
				<input
					type="checkbox"
					checked={autoActivate}
					onChange={(e) => setAutoActivate(e.target.checked)}
					className="accent-[var(--accent)]"
				/>
				Auto-activate and deploy to runtime after registration
			</label>

			{serverError && (
				<div
					role="alert"
					className="text-xs text-red-400 break-words whitespace-pre-wrap border border-red-900/40 rounded p-3"
				>
					{serverError}
				</div>
			)}

			<button
				type="submit"
				disabled={isSubmitting}
				className="px-4 py-2 bg-[var(--accent)] text-white rounded text-sm disabled:opacity-50"
			>
				{isSubmitting ? 'Registering…' : 'Register Model'}
			</button>
		</form>
	);
}
