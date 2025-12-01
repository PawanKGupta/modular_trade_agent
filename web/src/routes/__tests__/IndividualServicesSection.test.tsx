import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IndividualServicesSection } from '../dashboard/IndividualServicesSection';
import { withProviders } from '@/test/utils';
import * as serviceApi from '@/api/service';

// Mock the service API
vi.mock('@/api/service', () => ({
	getIndividualServicesStatus: vi.fn(),
}));

// Mock the session store
vi.mock('@/state/sessionStore', () => ({
	useSessionStore: vi.fn(() => ({ isAdmin: true })),
}));

describe('IndividualServicesSection', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('Bug #74: Message accuracy when unified service is running', () => {
		it('shows correct message when unified service is running', async () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({
				services: {
					analysis: {
						task_name: 'analysis',
						is_running: false,
						schedule_enabled: true,
						last_execution_at: null,
						last_execution_status: null,
						last_execution_duration: null,
						last_execution_details: null,
						next_execution_at: null,
						started_at: null,
					},
				},
			});

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={true} />));

			await waitFor(() => {
				expect(screen.getByText(/Individual Service Management/i)).toBeInTheDocument();
				expect(
					screen.getByText(
						/Unified service is running\. Individual services and most "Run Once" tasks are disabled to prevent broker session conflicts\./i
					)
				).toBeInTheDocument();
			});
		});

		it('shows correct message when unified service is not running', async () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({
				services: {
					analysis: {
						task_name: 'analysis',
						is_running: false,
						schedule_enabled: true,
						last_execution_at: null,
						last_execution_status: null,
						last_execution_duration: null,
						last_execution_details: null,
						next_execution_at: null,
						started_at: null,
					},
				},
			});

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={false} />));

			await waitFor(() => {
				expect(
					screen.getByText(/Start individual services to run specific tasks on their own schedule\./i)
				).toBeInTheDocument();
			});
		});

		it('does not show misleading "you can run tasks once" message', async () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({
				services: {
					buy_orders: {
						task_name: 'buy_orders',
						is_running: false,
						schedule_enabled: true,
						last_execution_at: null,
						last_execution_status: null,
						last_execution_duration: null,
						last_execution_details: null,
						next_execution_at: null,
						started_at: null,
					},
				},
			});

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={true} />));

			await waitFor(() => {
				// Should NOT show the old misleading message
				expect(screen.queryByText(/but you can run tasks once/i)).not.toBeInTheDocument();
			});
		});

		it('mentions session conflicts in the message', async () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({
				services: {
					sell_monitor: {
						task_name: 'sell_monitor',
						is_running: false,
						schedule_enabled: true,
						last_execution_at: null,
						last_execution_status: null,
						last_execution_duration: null,
						last_execution_details: null,
						next_execution_at: null,
						started_at: null,
					},
				},
			});

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={true} />));

			await waitFor(() => {
				expect(screen.getByText(/broker session conflicts/i)).toBeInTheDocument();
			});
		});
	});

	describe('Service loading and display', () => {
		it('shows loading state initially', () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockImplementation(
				() => new Promise(() => {}) // Never resolves
			);

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={false} />));

			expect(screen.getByText(/Loading individual services\.\.\./i)).toBeInTheDocument();
		});

		it('shows no services message when services object is empty', async () => {
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({
				services: {},
			});

			render(withProviders(<IndividualServicesSection unifiedServiceRunning={false} />));

			await waitFor(() => {
				expect(screen.getByText(/No individual services available/i)).toBeInTheDocument();
			});
		});
	});
});
