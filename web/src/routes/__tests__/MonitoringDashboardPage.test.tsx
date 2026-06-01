import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { MonitoringDashboardPage } from '../dashboard/MonitoringDashboardPage';
import * as monitoringApi from '@/api/monitoring';

vi.mock('@/api/monitoring', () => ({
	getMonitoringDashboard: vi.fn(),
	getTaskExecutions: vi.fn(),
	getRunningTasks: vi.fn(),
	getScheduleCompliance: vi.fn(),
	getActiveSessions: vi.fn(),
	getReauthHistory: vi.fn(),
	getAuthErrors: vi.fn(),
}));

const dashboardMock = {
	summary: {
		total_services: 10,
		services_running: 8,
		services_stopped: 2,
		tasks_executed_today: 20,
		tasks_successful_today: 18,
		tasks_failed_today: 2,
		services_with_errors: 1,
		active_sessions: 5,
		sessions_expiring_soon: 1,
		reauth_count_24h: 3,
		reauth_success_rate: 90,
		auth_errors_24h: 1,
		tasks_failed_due_to_auth: 0,
	},
	alerts: {
		alerts: [
			{ severity: 'critical' as const, type: 'error', message: 'Service down', user_id: 1 },
			{ severity: 'warning' as const, type: 'delay', message: 'Task delayed', user_id: 2 },
		],
		critical_count: 1,
		warning_count: 1,
		info_count: 0,
	},
	recent_task_executions: [
		{
			id: 1,
			user_id: 1,
			user_email: 'a@x.com',
			task_name: 'analysis',
			scheduled_time: '09:00',
			executed_at: new Date(Date.now() - 60000).toISOString(),
			time_difference_seconds: 0,
			status: 'success' as const,
			duration_seconds: 45,
			execution_type: 'scheduled' as const,
			details: null,
		},
	],
	recent_reauth_events: [
		{
			id: 1,
			user_id: 1,
			user_email: 'a@x.com',
			timestamp: new Date(Date.now() - 120000).toISOString(),
			triggered_by: 'system',
			status: 'success' as const,
			duration_seconds: 2,
			reason: 'token_expired',
			error_message: null,
		},
	],
	running_tasks: [],
	updated_at: new Date().toISOString(),
};

describe('MonitoringDashboardPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(monitoringApi.getMonitoringDashboard).mockResolvedValue(dashboardMock);
		vi.mocked(monitoringApi.getTaskExecutions).mockResolvedValue({
			items: dashboardMock.recent_task_executions,
			total: 1,
			page: 1,
			page_size: 20,
			total_pages: 2,
		});
		vi.mocked(monitoringApi.getRunningTasks).mockResolvedValue({
			tasks: [
				{
					id: 5,
					user_id: 2,
					user_email: 'b@x.com',
					task_name: 'sell_monitor',
					started_at: new Date(Date.now() - 30000).toISOString(),
					duration_seconds: 30,
					estimated_completion: null,
				},
			],
			total: 1,
		});
		vi.mocked(monitoringApi.getScheduleCompliance).mockResolvedValue({
			tasks: [
				{
					task_name: 'analysis',
					scheduled_time: '09:00',
					enabled: true,
					is_continuous: false,
					end_time: null,
					last_execution_at: new Date().toISOString(),
					next_expected_execution: null,
					execution_count_today: 1,
					expected_count_today: 1,
					compliance_status: 'on_track' as const,
					last_execution_status: 'success',
				},
				{
					task_name: 'buy_orders',
					scheduled_time: '10:00',
					enabled: true,
					is_continuous: false,
					end_time: null,
					last_execution_at: null,
					next_expected_execution: null,
					execution_count_today: 0,
					expected_count_today: 1,
					compliance_status: 'missed' as const,
					last_execution_status: null,
				},
			],
			total_missed: 1,
			total_delayed: 0,
		});
		vi.mocked(monitoringApi.getActiveSessions).mockResolvedValue({
			sessions: [
				{
					user_id: 1,
					user_email: 'a@x.com',
					session_created_at: new Date().toISOString(),
					session_age_minutes: 30,
					session_status: 'valid' as const,
					ttl_remaining_minutes: 120,
					is_authenticated: true,
					client_available: true,
				},
			],
			total_active: 1,
			expiring_soon: 0,
			expired: 0,
		});
		vi.mocked(monitoringApi.getReauthHistory).mockResolvedValue({
			events: dashboardMock.recent_reauth_events,
			total: 1,
			page: 1,
			page_size: 20,
			total_pages: 2,
		});
		vi.mocked(monitoringApi.getAuthErrors).mockResolvedValue({
			errors: [
				{
					id: 1,
					user_id: 1,
					user_email: 'a@x.com',
					timestamp: new Date().toISOString(),
					error_type: 'AuthError',
					error_code: '401',
					error_message: 'Invalid token',
					api_endpoint: '/orders',
					method_name: 'GET',
					reauth_attempted: true,
					reauth_success: true,
				},
			],
			total: 1,
			page: 1,
			page_size: 20,
			total_pages: 2,
		});
	});

	it('renders dashboard summary, alerts, and tables', async () => {
		render(withProviders(<MonitoringDashboardPage />));

		await waitFor(() => {
			expect(screen.getByText('Monitoring Dashboard')).toBeInTheDocument();
			expect(screen.getByText('Service down')).toBeInTheDocument();
			expect(screen.getByText('8/10')).toBeInTheDocument();
			expect(screen.getByText('Currently Running Tasks (1)')).toBeInTheDocument();
			expect(screen.getByText(/Schedule Compliance/i)).toBeInTheDocument();
			expect(screen.getByText(/Authentication Errors \(1\)/i)).toBeInTheDocument();
		});
	});

	it('toggles auto-refresh and paginates executions', async () => {
		render(withProviders(<MonitoringDashboardPage />));

		await waitFor(() => expect(screen.getByText('Monitoring Dashboard')).toBeInTheDocument());

		fireEvent.click(screen.getByLabelText('Auto-refresh'));
		fireEvent.click(screen.getAllByRole('button', { name: 'Next' })[0]);

		await waitFor(() => {
			expect(monitoringApi.getTaskExecutions).toHaveBeenCalledWith(
				expect.objectContaining({ page: 2 })
			);
		});
	});

	it('paginates reauth history and auth errors', async () => {
		render(withProviders(<MonitoringDashboardPage />));
		await waitFor(() => expect(screen.getByText('Monitoring Dashboard')).toBeInTheDocument());

		const nextButtons = screen.getAllByRole('button', { name: 'Next' });
		fireEvent.click(nextButtons[1]);
		await waitFor(() => {
			expect(monitoringApi.getReauthHistory).toHaveBeenCalledWith(
				expect.objectContaining({ page: 2 })
			);
		});

		fireEvent.click(nextButtons[2]);
		await waitFor(() => {
			expect(monitoringApi.getAuthErrors).toHaveBeenCalledWith(
				expect.objectContaining({ page: 2 })
			);
		});
	});

	it('shows loading and empty states', async () => {
		vi.mocked(monitoringApi.getMonitoringDashboard).mockImplementation(
			() => new Promise(() => {})
		);
		const { unmount } = render(withProviders(<MonitoringDashboardPage />));
		expect(screen.getByText(/Loading dashboard data/i)).toBeInTheDocument();
		unmount();

		vi.mocked(monitoringApi.getMonitoringDashboard).mockResolvedValue(null as never);
		render(withProviders(<MonitoringDashboardPage />));
		await waitFor(() => {
			expect(screen.getByText(/No dashboard data available/i)).toBeInTheDocument();
		});
	});

	it('renders sessions, compliance statuses, and auth error reauth outcomes', async () => {
		vi.mocked(monitoringApi.getAuthErrors).mockResolvedValue({
			errors: [
				{
					id: 2,
					user_id: 2,
					user_email: null,
					timestamp: new Date().toISOString(),
					error_type: 'AuthError',
					error_code: '403',
					error_message: 'Forbidden',
					api_endpoint: '/portfolio',
					method_name: 'GET',
					reauth_attempted: true,
					reauth_success: false,
				},
				{
					id: 3,
					user_id: 3,
					user_email: 'c@x.com',
					timestamp: new Date().toISOString(),
					error_type: 'AuthError',
					error_code: '401',
					error_message: 'No retry',
					api_endpoint: '/orders',
					method_name: 'POST',
					reauth_attempted: false,
					reauth_success: false,
				},
			],
			total: 40,
			page: 1,
			page_size: 20,
			total_pages: 2,
		});

		render(withProviders(<MonitoringDashboardPage />));

		await waitFor(() => {
			expect(screen.getAllByText(/Active Sessions/i).length).toBeGreaterThan(0);
			expect(screen.getByText(/Schedule Compliance/i)).toBeInTheDocument();
			expect(screen.getByText('Forbidden')).toBeInTheDocument();
			expect(screen.getByText('User 2')).toBeInTheDocument();
		});

		const nextButtons = screen.getAllByRole('button', { name: 'Next' });
		fireEvent.click(nextButtons[2]);
		await waitFor(() => {
			expect(monitoringApi.getAuthErrors).toHaveBeenCalledWith(
				expect.objectContaining({ page: 2 })
			);
		});

		const previousButtons = screen.getAllByRole('button', { name: 'Previous' });
		fireEvent.click(previousButtons[previousButtons.length - 1]);
		await waitFor(() => {
			expect(monitoringApi.getAuthErrors).toHaveBeenCalledWith(
				expect.objectContaining({ page: 1 })
			);
		});
	});
});
