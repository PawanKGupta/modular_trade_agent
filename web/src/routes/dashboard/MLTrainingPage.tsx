import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
	getMLModels,
	getTrainingJobs,
	startTrainingJob,
	activateModel,
	type MLModel,
	type MLTrainingJob,
	type StartTrainingPayload,
} from '@/api/ml-training';
import { MLTrainingForm } from './MLTrainingForm';
import { MLTrainingJobsTable } from './MLTrainingJobsTable';
import { MLModelsTable } from './MLModelsTable';
import { getApiErrorMessage } from '@/utils/getApiErrorMessage';

export function MLTrainingPage() {
	const queryClient = useQueryClient();
	const [trainingServerError, setTrainingServerError] = useState<string | null>(null);
	const [activateServerError, setActivateServerError] = useState<string | null>(null);

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

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<h2 className="text-base sm:text-lg font-semibold">Start Training Job</h2>
				<MLTrainingForm
					onSubmit={(payload) => startTrainingMutation.mutate(payload)}
					isSubmitting={startTrainingMutation.isPending}
					serverError={trainingServerError}
				/>
			</div>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
					<h2 className="text-base sm:text-lg font-semibold">Recent Training Jobs</h2>
					<button
						type="button"
						onClick={() => queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] })}
						className="text-xs text-[var(--accent)] min-h-[36px] sm:min-h-0 px-3 py-2 sm:py-1"
					>
						Refresh
					</button>
				</div>
				<MLTrainingJobsTable jobs={jobs} isLoading={jobsLoading} />
			</div>

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
				{activateServerError ? (
					<div
						role="alert"
						className="text-xs sm:text-sm text-red-400 break-words whitespace-pre-wrap border border-red-900/40 rounded p-3"
					>
						{activateServerError}
					</div>
				) : null}
				<MLModelsTable
					models={models}
					isLoading={modelsLoading}
					onActivate={(modelId) => activateModelMutation.mutate(modelId)}
					activatingModelId={
						activateModelMutation.isPending ? activateModelMutation.variables : null
					}
				/>
			</div>
		</div>
	);
}
