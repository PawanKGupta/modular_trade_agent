import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ServiceStatusPage } from '../dashboard/ServiceStatusPage';
import { withProviders } from '@/test/utils';
import * as serviceApi from '@/api/service';

// Mock the service API
vi.mock('@/api/service', () => ({
	getServiceStatus: vi.fn(),
	getTaskHistory: vi.fn(),
	getServiceLogs: vi.fn(),
	getIndividualServicesStatus: vi.fn(),
	startService: vi.fn(),
	stopService: vi.fn(),
}));

describe('ServiceStatusPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('Bug #73: Service status symbols', () => {
		it('displays checkmark symbol when service is running', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: true,
				last_heartbeat: new Date().toISOString(),
				last_task_execution: null,
				error_count: 0,
				last_error: null,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				expect(screen.getByText(/✓ Running/i)).toBeInTheDocument();
			});
		});

		it('displays X mark symbol when service is stopped', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: false,
				last_heartbeat: null,
				last_task_execution: null,
				error_count: 0,
				last_error: null,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				expect(screen.getByText(/✗ Stopped/i)).toBeInTheDocument();
			});
		});

		it('does not display question mark symbols', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: true,
				last_heartbeat: new Date().toISOString(),
				last_task_execution: null,
				error_count: 0,
				last_error: null,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				expect(screen.queryByText(/\? Running/i)).not.toBeInTheDocument();
				expect(screen.queryByText(/\? Stopped/i)).not.toBeInTheDocument();
			});
		});

		it('formats error messages using formatErrorMessage utility', async () => {
			const longError = 'Analysis failed with return code 1 STDERR (tail): File "C:\\path\\to\\file.py", line 677, in __str__ Some error';

			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: true,
				last_heartbeat: new Date().toISOString(),
				last_task_execution: null,
				error_count: 1,
				last_error: longError,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				expect(screen.getByText(/Last Error/i)).toBeInTheDocument();
				// Should display formatted error (with line breaks and structure)
				const errorContainer = screen.getByText(/Analysis failed with return code 1/i);
				expect(errorContainer).toBeInTheDocument();
			});
		});

		it('displays error with proper styling (monospace font)', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: true,
				last_heartbeat: new Date().toISOString(),
				last_task_execution: null,
				error_count: 1,
				last_error: 'Simple error message',
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				const errorDiv = screen.getByText('Simple error message');
				expect(errorDiv).toHaveClass('font-mono');
			});
		});
	});

	describe('Service Health display', () => {
		it('shows green background for running service', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: true,
				last_heartbeat: new Date().toISOString(),
				last_task_execution: null,
				error_count: 0,
				last_error: null,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				const badge = screen.getByText(/✓ Running/i);
				expect(badge.className).toContain('bg-green-500/20');
				expect(badge.className).toContain('text-green-400');
			});
		});

		it('shows red background for stopped service', async () => {
			vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
				service_running: false,
				last_heartbeat: null,
				last_task_execution: null,
				error_count: 0,
				last_error: null,
			});

			vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({ tasks: [] });
			vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({ logs: [] });
			vi.mocked(serviceApi.getIndividualServicesStatus).mockResolvedValue({ services: {} });

			render(withProviders(<ServiceStatusPage />));

			await waitFor(() => {
				const badge = screen.getByText(/✗ Stopped/i);
				expect(badge.className).toContain('bg-red-500/20');
				expect(badge.className).toContain('text-red-400');
			});
		});
	});
});
