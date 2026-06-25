import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
	getMLModels,
	getTrainingJobs,
	startTrainingJob,
	activateModel,
	deleteModel,
	registerModel,
	type MLModel,
	type MLTrainingJob,
	type StartTrainingPayload,
	type RegisterModelPayload,
} from '@/api/ml-training';
import { MLTrainingForm } from './MLTrainingForm';
import { MLTrainingJobsTable } from './MLTrainingJobsTable';
import { MLModelsTable } from './MLModelsTable';
import { MLRegisterModelForm } from './MLRegisterModelForm';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function MLTrainingPage() {
	const queryClient = useQueryClient();
	const [trainingServerError, setTrainingServerError] = useState<string | null>(null);
	const [activateServerError, setActivateServerError] = useState<string | null>(null);
	const [deleteServerError, setDeleteServerError] = useState<string | null>(null);
	const [registerServerError, setRegisterServerError] = useState<string | null>(null);
	const [showTrainingForm, setShowTrainingForm] = useState(false);
	const [showRegisterForm, setShowRegisterForm] = useState(false);
	const [showJobs, setShowJobs] = useState(false);

	const {
		data: jobs = [],
		isLoading: jobsLoading,
	} = useQuery<MLTrainingJob[]>({
		queryKey: ['mlTrainingJobs'],
		queryFn: () => getTrainingJobs({ limit: 50 }),
		refetchInterval: 12000,
	});

	const {
		data: models = [],
		isLoading: modelsLoading,
	} = useQuery<MLModel[]>({
		queryKey: ['mlModels'],
		queryFn: () => getMLModels(),
		refetchInterval: 15000,
	});

	const startTrainingMutation = useMutation({
		mutationFn: (payload: StartTrainingPayload) => startTrainingJob(payload),
		onMutate: () => {
			setTrainingServerError(null);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] });
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
		},
		onError: (err) => {
			setTrainingServerError(getApiErrorMessage(err));
		},
	});

	const registerModelMutation = useMutation({
		mutationFn: (payload: RegisterModelPayload) => registerModel(payload),
		onMutate: () => {
			setRegisterServerError(null);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
			queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] });
			setShowRegisterForm(false);
		},
		onError: (err) => {
			setRegisterServerError(getApiErrorMessage(err));
		},
	});

	const deleteModelMutation = useMutation({
		mutationFn: (modelId: number) => deleteModel(modelId),
		onMutate: () => {
			setDeleteServerError(null);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
		},
		onError: (err) => {
			setDeleteServerError(getApiErrorMessage(err));
		},
	});

	const activateModelMutation = useMutation({
		mutationFn: (modelId: number) => activateModel(modelId),
		onMutate: () => {
			setActivateServerError(null);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
		},
		onError: (err) => {
			setActivateServerError(getApiErrorMessage(err));
		},
	});

	useEffect(() => {
		document.title = 'ML Training Management';
	}, []);

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<div>
					<h1 className="text-lg sm:text-xl font-semibold">ML Training Management</h1>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Admin-only tools for training and activating ML models.
					</p>
				</div>
			</div>

			{/* Start Training Job — collapsed by default */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
					<h2 className="text-base sm:text-lg font-semibold">Start Training Job</h2>
					<button
						type="button"
						onClick={() => setShowTrainingForm((v) => !v)}
						className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
					>
						{showTrainingForm ? 'Cancel' : 'New Training Job'}
					</button>
				</div>
				{showTrainingForm && (
					<MLTrainingForm
						onSubmit={(payload) => startTrainingMutation.mutate(payload)}
						isSubmitting={startTrainingMutation.isPending}
						serverError={trainingServerError}
					/>
				)}
			</div>

			{/* Recent Training Jobs — collapsed by default */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
					<h2 className="text-base sm:text-lg font-semibold">Recent Training Jobs</h2>
					<div className="flex items-center gap-3">
						{showJobs && (
							<button
								type="button"
								onClick={() => queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] })}
								className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
							>
								Refresh
							</button>
						)}
						<button
							type="button"
							onClick={() => setShowJobs((v) => !v)}
							className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
						>
							{showJobs ? 'Hide' : `Show${jobs.length ? ` (${jobs.length})` : ''}`}
						</button>
					</div>
				</div>
				{showJobs && <MLTrainingJobsTable jobs={jobs} isLoading={jobsLoading} />}
			</div>

			{/* Model Versions */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
					<h2 className="text-base sm:text-lg font-semibold">Model Versions</h2>
					<button
						type="button"
						onClick={() => queryClient.invalidateQueries({ queryKey: ['mlModels'] })}
						className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
					>
						Refresh
					</button>
				</div>
				{(activateServerError || deleteServerError) ? (
					<div
						role="alert"
						className="text-xs sm:text-sm text-red-400 break-words whitespace-pre-wrap border border-red-900/40 rounded p-3"
					>
						{activateServerError ?? deleteServerError}
					</div>
				) : null}
				<MLModelsTable
					models={models}
					isLoading={modelsLoading}
					onActivate={(modelId) => activateModelMutation.mutate(modelId)}
					activatingModelId={
						activateModelMutation.isPending ? activateModelMutation.variables : null
					}
					onDelete={(modelId) => deleteModelMutation.mutate(modelId)}
					deletingModelId={
						deleteModelMutation.isPending ? deleteModelMutation.variables : null
					}
				/>
			</div>

			{/* Register Existing Model — at the bottom, collapsed by default */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
					<div>
						<h2 className="text-base sm:text-lg font-semibold">Register Existing Model</h2>
						<p className="text-xs text-[var(--muted)]">
							Import a model trained outside the UI so it appears in the registry above.
						</p>
					</div>
					<button
						type="button"
						onClick={() => setShowRegisterForm((v) => !v)}
						className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
					>
						{showRegisterForm ? 'Cancel' : 'Register Model'}
					</button>
				</div>
				{showRegisterForm && (
					<MLRegisterModelForm
						onSubmit={(payload) => registerModelMutation.mutate(payload)}
						isSubmitting={registerModelMutation.isPending}
						serverError={registerServerError}
					/>
				)}
			</div>
		</div>
	);
}
