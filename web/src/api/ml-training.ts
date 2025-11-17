import { api } from './client';

export type TrainingStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface MLTrainingJob {
	id: number;
	started_by: number;
	status: TrainingStatus;
	model_type: string;
	algorithm: string;
	training_data_path: string;
	started_at: string;
	completed_at: string | null;
	model_path: string | null;
	accuracy: number | null;
	error_message: string | null;
	logs: string | null;
}

export interface MLModel {
	id: number;
	model_type: string;
	version: string;
	model_path: string;
	accuracy: number | null;
	training_job_id: number;
	is_active: boolean;
	created_at: string;
	created_by: number;
}

export interface StartTrainingPayload {
	model_type: 'verdict_classifier' | 'price_regressor';
	algorithm: 'random_forest' | 'xgboost' | 'logistic_regression';
	training_data_path: string;
	hyperparameters?: Record<string, string | number | boolean>;
	notes?: string | null;
	auto_activate?: boolean;
}

export async function startTrainingJob(payload: StartTrainingPayload): Promise<MLTrainingJob> {
	const { data } = await api.post<MLTrainingJob>('/admin/ml/train', payload);
	return data;
}

export async function getTrainingJobs(params?: {
	status?: TrainingStatus;
	model_type?: string;
	limit?: number;
}): Promise<MLTrainingJob[]> {
	const { data } = await api.get<{ jobs: MLTrainingJob[] }>('/admin/ml/jobs', { params });
	return data.jobs;
}

export async function getMLModels(params?: {
	model_type?: string;
	active?: boolean;
}): Promise<MLModel[]> {
	const { data } = await api.get<{ models: MLModel[] }>('/admin/ml/models', { params });
	return data.models;
}

export async function activateModel(modelId: number): Promise<{ message: string; model: MLModel }> {
	const { data } = await api.post<{ message: string; model: MLModel }>(
		`/admin/ml/models/${modelId}/activate`,
		{}
	);
	return data;
}
