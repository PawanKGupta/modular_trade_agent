import { describe, it, beforeEach, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient } from '@tanstack/react-query';
import { withProviders } from '@/test/utils';
import { MLTrainingPage } from '../dashboard/MLTrainingPage';
import * as mlApi from '@/api/ml-training';

vi.mock('@/api/ml-training', () => ({
	getTrainingJobs: vi.fn(),
	getMLModels: vi.fn(),
	startTrainingJob: vi.fn(),
	activateModel: vi.fn(),
}));

describe('MLTrainingPage', () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		vi.clearAllMocks();
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});

		vi.mocked(mlApi.getTrainingJobs).mockResolvedValue([
			{
				id: 1,
				started_by: 1,
				status: 'completed',
				model_type: 'verdict_classifier',
				algorithm: 'xgboost',
				training_data_path: 'data/mock.csv',
				started_at: new Date().toISOString(),
				completed_at: new Date().toISOString(),
				model_path: 'models/mock.json',
				accuracy: 0.82,
				error_message: null,
				logs: 'done',
			},
		]);
		vi.mocked(mlApi.getMLModels).mockResolvedValue([
			{
				id: 1,
				model_type: 'verdict_classifier',
				version: 'v1',
				model_path: 'models/mock.json',
				accuracy: 0.82,
				training_job_id: 1,
				is_active: false,
				created_at: new Date().toISOString(),
				created_by: 1,
			},
		]);
		vi.mocked(mlApi.startTrainingJob).mockResolvedValue({
			id: 2,
			started_by: 1,
			status: 'completed',
			model_type: 'verdict_classifier',
			algorithm: 'xgboost',
			training_data_path: 'data/mock.csv',
			started_at: new Date().toISOString(),
			completed_at: new Date().toISOString(),
			model_path: 'models/mock-v2.json',
			accuracy: 0.83,
			error_message: null,
			logs: 'done',
		});
		vi.mocked(mlApi.activateModel).mockResolvedValue({
			message: 'Model activated',
			model: {
				id: 1,
				model_type: 'verdict_classifier',
				version: 'v1',
				model_path: 'models/mock.json',
				accuracy: 0.82,
				training_job_id: 1,
				is_active: true,
				created_at: new Date().toISOString(),
				created_by: 1,
			},
		});
	});

	it('renders training form, jobs, and models', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/admin/ml']}>
					<MLTrainingPage />
				</MemoryRouter>,
				{ queryClient }
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/ML Training Management/i)).toBeInTheDocument();
			expect(screen.getByText(/Recent Training Jobs/i)).toBeInTheDocument();
			expect(screen.getByText(/Model Versions/i)).toBeInTheDocument();
		});

		expect(mlApi.getTrainingJobs).toHaveBeenCalled();
		expect(mlApi.getMLModels).toHaveBeenCalled();
	});

	it('submits a new training job', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/admin/ml']}>
					<MLTrainingPage />
				</MemoryRouter>,
				{ queryClient }
			)
		);

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /Start Training/i })).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: /Start Training/i }));

		await waitFor(() => {
			expect(mlApi.startTrainingJob).toHaveBeenCalledTimes(1);
		});
	});

	it('activates a model from the table', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/admin/ml']}>
					<MLTrainingPage />
				</MemoryRouter>,
				{ queryClient }
			)
		);

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /Activate/i })).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: /Activate/i }));

		await waitFor(() => {
			expect(mlApi.activateModel).toHaveBeenCalledTimes(1);
		});
	});
});
