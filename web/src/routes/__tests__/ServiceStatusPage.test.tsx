import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ServiceStatusPage } from '../dashboard/ServiceStatusPage';
import { withProviders } from '@/test/utils';
import * as serviceApi from '@/api/service';

// Mock the API module
vi.mock('@/api/service', () => ({
	getServiceStatus: vi.fn(),
	getTaskHistory: vi.fn(),
	getServiceLogs: vi.fn(),
	startService: vi.fn(),
	stopService: vi.fn(),
}));

describe('ServiceStatusPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Default mock implementations
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
			service_running: true,
			last_heartbeat: new Date().toISOString(),
			last_task_execution: new Date(Date.now() - 60000).toISOString(),
			error_count: 0,
			last_error: null,
			updated_at: new Date().toISOString(),
		});
		vi.mocked(serviceApi.getTaskHistory).mockResolvedValue({
			tasks: [
				{
					id: 1,
					task_name: 'premarket_retry',
					executed_at: new Date().toISOString(),
					status: 'success' as const,
					duration_seconds: 1.5,
					details: { symbols_processed: 5 },
				},
			],
			total: 1,
		});
		vi.mocked(serviceApi.getServiceLogs).mockResolvedValue({
			logs: [
				{
					id: 1,
					level: 'INFO' as const,
					module: 'TradingService',
					message: 'Service started successfully',
					context: { action: 'start_service' },
					timestamp: new Date().toISOString(),
				},
			],
			total: 1,
			limit: 100,
		});
		vi.mocked(serviceApi.startService).mockResolvedValue({
			success: true,
			message: 'Trading service started successfully',
			service_running: true,
		});
		vi.mocked(serviceApi.stopService).mockResolvedValue({
			success: true,
			message: 'Trading service stopped successfully',
			service_running: false,
		});
	});

	it('renders service status page with all sections', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Service Status/i)).toBeInTheDocument();
			expect(screen.getByText(/Service Health/i)).toBeInTheDocument();
			expect(screen.getByText(/Task Execution History/i)).toBeInTheDocument();
			expect(screen.getByText(/Recent Service Logs/i)).toBeInTheDocument();
		});
	});

	it('displays service running status', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/? Running/i)).toBeInTheDocument();
		});
	});

	it('displays service stopped status', async () => {
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
			service_running: false,
			last_heartbeat: null,
			last_task_execution: null,
			error_count: 0,
			last_error: null,
			updated_at: new Date().toISOString(),
		});

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/? Stopped/i)).toBeInTheDocument();
		});
	});

	it('displays last heartbeat and task execution times', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Last Heartbeat/i)).toBeInTheDocument();
			expect(screen.getByText(/Last Task Execution/i)).toBeInTheDocument();
		});
	});

	it('displays error count', async () => {
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
			service_running: true,
			last_heartbeat: new Date().toISOString(),
			last_task_execution: new Date().toISOString(),
			error_count: 5,
			last_error: 'Test error message',
			updated_at: new Date().toISOString(),
		});

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Error Count/i)).toBeInTheDocument();
			// Find the error count specifically (in the error count div, not in task details)
			const errorCountSection = screen.getByText(/Error Count/i).closest('div')?.nextElementSibling;
			expect(errorCountSection?.textContent).toContain('5');
			expect(screen.getByText(/Last Error/i)).toBeInTheDocument();
			expect(screen.getByText(/Test error message/i)).toBeInTheDocument();
		});
	});

	it('allows toggling auto-refresh', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const checkbox = screen.getByLabelText(/Auto-refresh/i);
			expect(checkbox).toBeInTheDocument();
			expect(checkbox).toBeChecked();
		});

		const checkbox = screen.getByLabelText(/Auto-refresh/i);
		fireEvent.click(checkbox);

		await waitFor(() => {
			expect(checkbox).not.toBeChecked();
		});
	});

	it('calls startService when start button is clicked', async () => {
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValue({
			service_running: false,
			last_heartbeat: null,
			last_task_execution: null,
			error_count: 0,
			last_error: null,
			updated_at: new Date().toISOString(),
		});

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const startButton = screen.getByRole('button', { name: /Start Service/i });
			expect(startButton).toBeInTheDocument();
			expect(startButton).not.toBeDisabled();
		});

		const startButton = screen.getByRole('button', { name: /Start Service/i });
		fireEvent.click(startButton);

		await waitFor(() => {
			expect(serviceApi.startService).toHaveBeenCalled();
		});
	});

	it('calls stopService when stop button is clicked', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const stopButton = screen.getByRole('button', { name: /Stop Service/i });
			expect(stopButton).toBeInTheDocument();
			expect(stopButton).not.toBeDisabled();
		});

		const stopButton = screen.getByRole('button', { name: /Stop Service/i });
		fireEvent.click(stopButton);

		await waitFor(() => {
			expect(serviceApi.stopService).toHaveBeenCalled();
		});
	});

	it('displays task history', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/premarket_retry/i)).toBeInTheDocument();
		});
	});

	it('displays service logs', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/service']}>
					<ServiceStatusPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Service started successfully/i)).toBeInTheDocument();
		});
	});
});
