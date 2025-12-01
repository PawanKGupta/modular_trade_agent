import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
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

export function MLTrainingPage() {
	const queryClient = useQueryClient();

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
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] });
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
		},
	});

	const activateModelMutation = useMutation({
		mutationFn: (modelId: number) => activateModel(modelId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ['mlModels'] });
		},
	});

	useEffect(() => {
		document.title = 'ML Training Management';
	}, []);

	return (
		<div className="p-4 space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-xl font-semibold">ML Training Management</h1>
					<p className="text-sm text-[var(--muted)]">
						Admin-only tools for training and activating ML models.
					</p>
				</div>
			</div>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6 space-y-4">
				<h2 className="text-lg font-semibold">Start Training Job</h2>
				<MLTrainingForm
					onSubmit={(payload) => startTrainingMutation.mutate(payload)}
					isSubmitting={startTrainingMutation.isPending}
				/>
			</div>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6 space-y-4">
				<div className="flex items-center justify-between">
					<h2 className="text-lg font-semibold">Recent Training Jobs</h2>
					<button
						type="button"
						onClick={() => queryClient.invalidateQueries({ queryKey: ['mlTrainingJobs'] })}
						className="text-xs text-[var(--accent)]"
					>
						Refresh
					</button>
				</div>
				<MLTrainingJobsTable jobs={jobs} isLoading={jobsLoading} />
			</div>

			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6 space-y-4">
				<div className="flex items-center justify-between">
					<h2 className="text-lg font-semibold">Model Versions</h2>
					<button
						type="button"
						onClick={() => queryClient.invalidateQueries({ queryKey: ['mlModels'] })}
						className="text-xs text-[var(--accent)]"
					>
						Refresh
					</button>
				</div>
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
