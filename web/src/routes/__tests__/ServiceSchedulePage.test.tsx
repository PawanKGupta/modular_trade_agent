import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { ServiceSchedulePage } from '../dashboard/ServiceSchedulePage';
import * as adminApi from '@/api/admin';
import { useSessionStore } from '@/state/sessionStore';

vi.mock('@/api/admin', () => ({
	listServiceSchedules: vi.fn(),
	updateServiceSchedule: vi.fn(),
	enableServiceSchedule: vi.fn(),
	disableServiceSchedule: vi.fn(),
}));

const schedule = {
	id: 1,
	task_name: 'analysis',
	schedule_time: '09:30',
	enabled: true,
	is_hourly: false,
	is_continuous: false,
	end_time: null,
	schedule_type: 'daily' as const,
	description: 'Morning analysis',
	next_execution_at: new Date(Date.now() + 3600000).toISOString(),
};

describe('ServiceSchedulePage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		useSessionStore.setState({
			user: { id: 1, email: 'admin@example.com', roles: ['admin'] } as never,
			isAdmin: true,
		});
		vi.mocked(adminApi.listServiceSchedules).mockResolvedValue({ schedules: [schedule] });
		vi.mocked(adminApi.updateServiceSchedule).mockResolvedValue({ requires_restart: true });
		vi.mocked(adminApi.enableServiceSchedule).mockResolvedValue({ requires_restart: false });
		vi.mocked(adminApi.disableServiceSchedule).mockResolvedValue({ requires_restart: false });
	});

	it('denies access for non-admin users', () => {
		useSessionStore.setState({ user: null, isAdmin: false });
		render(withProviders(<ServiceSchedulePage />));
		expect(screen.getByText(/Access denied/i)).toBeInTheDocument();
	});

	it('renders schedules and allows edit/save flow', async () => {
		render(withProviders(<ServiceSchedulePage />));

		await waitFor(() => {
			expect(screen.getByText('Service Schedules')).toBeInTheDocument();
			expect(screen.getByText('Analysis')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
		fireEvent.change(screen.getByDisplayValue('09:30'), { target: { value: '10:00' } });
		fireEvent.click(screen.getByRole('button', { name: 'Save' }));

		await waitFor(() => {
			expect(adminApi.updateServiceSchedule).toHaveBeenCalledWith(
				'analysis',
				expect.objectContaining({ schedule_time: '10:00' })
			);
			expect(screen.getByText(/Redeploy the app or restart running unified services/i)).toBeInTheDocument();
		});
	});

	it('toggles enable/disable and cancels edit', async () => {
		render(withProviders(<ServiceSchedulePage />));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Disable' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Disable' }));
		await waitFor(() => expect(adminApi.disableServiceSchedule).toHaveBeenCalledWith('analysis'));

		fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
		fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
	});

	it('shows loading state', () => {
		vi.mocked(adminApi.listServiceSchedules).mockImplementation(() => new Promise(() => {}));
		render(withProviders(<ServiceSchedulePage />));
		expect(screen.getByText(/Loading schedules/i)).toBeInTheDocument();
	});

	it('enables a disabled schedule', async () => {
		const disabledSchedule = { ...schedule, enabled: false };
		vi.mocked(adminApi.listServiceSchedules).mockResolvedValue({ schedules: [disabledSchedule] });

		render(withProviders(<ServiceSchedulePage />));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Enable' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Enable' }));

		await waitFor(() => {
			expect(adminApi.enableServiceSchedule).toHaveBeenCalledWith('analysis');
		});
	});
});
