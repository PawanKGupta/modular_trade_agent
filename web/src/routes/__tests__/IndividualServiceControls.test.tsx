import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IndividualServiceControls } from '../dashboard/IndividualServiceControls';
import { withProviders } from '@/test/utils';
import * as serviceApi from '@/api/service';
import { type IndividualServiceStatus } from '@/api/service';

// Mock the service API
vi.mock('@/api/service', async (importOriginal) => {
	const actual = await importOriginal<typeof import('@/api/service')>();
	return {
		...actual,
	startIndividualService: vi.fn(),
	stopIndividualService: vi.fn(),
	runTaskOnce: vi.fn(),
	};
});

const mockService: IndividualServiceStatus = {
	task_name: 'analysis',
	is_running: false,
	schedule_enabled: true,
	last_execution_at: null,
	current_run_started_at: null,
	last_execution_status: null,
	last_execution_duration: null,
	last_execution_details: null,
	next_execution_at: null,
	started_at: null,
};

describe('IndividualServiceControls', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('Bug #74: Warning symbol fix', () => {
		it('displays warning symbol (⚠) instead of [WARN]?', async () => {
			vi.mocked(serviceApi.runTaskOnce).mockResolvedValue({
				success: true,
				message: 'Task executed',
				has_conflict: true,
				conflict_message: 'Task already running elsewhere',
			});

			render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={false} />
				)
			);

			// Click Run Once button
			const runOnceButton = screen.getByText('Run Once');
			fireEvent.click(runOnceButton);

			// Should show warning with ⚠ symbol
			await waitFor(() => {
				expect(screen.getByText(/⚠/)).toBeInTheDocument();
				expect(screen.getByText(/Task already running elsewhere/i)).toBeInTheDocument();
			});

			// Should NOT show [WARN]?
			expect(screen.queryByText(/\[WARN\]\?/)).not.toBeInTheDocument();
		});

		it('warning message uses correct symbol and styling', async () => {
			vi.mocked(serviceApi.runTaskOnce).mockResolvedValue({
				success: true,
				message: 'Task executed',
				has_conflict: true,
				conflict_message: 'Minor conflict detected',
			});

			render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={false} />
				)
			);

			// Click Run Once button
			const runOnceButton = screen.getByText('Run Once');
			fireEvent.click(runOnceButton);

			// Should show warning with ⚠ symbol (not [WARN]?)
			await waitFor(() => {
				const warningElement = screen.getByText(/⚠/);
				expect(warningElement).toBeInTheDocument();
				// Should have yellow styling
				const warningContainer = warningElement.closest('div');
				expect(warningContainer?.className).toContain('bg-yellow-500/10');
			});
		});
	});

	describe('Button states when unified service is running', () => {
		it('disables Start Service button when unified service is running', () => {
			render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={true} />
				)
			);

			const startButton = screen.getByText('Start Service');
			expect(startButton).toBeDisabled();
		});

		it('disables Run Once for non-analysis tasks when unified service is running', () => {
			const buyOrdersService = { ...mockService, task_name: 'buy_orders' };

			render(
				withProviders(
					<IndividualServiceControls service={buyOrdersService} unifiedServiceRunning={true} />
				)
			);

			const runOnceButton = screen.getByText('Run Once');
			expect(runOnceButton).toBeDisabled();
		});

		it('allows Run Once for analysis task even when unified service is running', () => {
			const analysisService = { ...mockService, task_name: 'analysis' };

			render(
				withProviders(
					<IndividualServiceControls service={analysisService} unifiedServiceRunning={true} />
				)
			);

			const runOnceButton = screen.getByText('Run Once');
			// Analysis should be enabled even with unified service running
			expect(runOnceButton).not.toBeDisabled();
		});
	});

	describe('Service status display', () => {
		it('displays running badge when service is running', () => {
			const runningService = { ...mockService, is_running: true };

			render(
				withProviders(
					<IndividualServiceControls service={runningService} unifiedServiceRunning={false} />
				)
			);

			const runningBadges = screen.getAllByText('Running');
			expect(runningBadges[0].className).toContain('bg-green-500/20');
			expect(runningBadges[0].className).toContain('text-green-400');
		});

		it('displays running badge and disables actions when run-once is in progress', () => {
			const runOnceService = {
				...mockService,
				last_execution_status: 'running' as const,
			};

			render(
				withProviders(
					<IndividualServiceControls service={runOnceService} unifiedServiceRunning={false} />
				)
			);

			expect(screen.getAllByText('Running').length).toBeGreaterThanOrEqual(1);
			expect(screen.getByText('Current Run')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Start Service' })).toBeDisabled();
			expect(screen.getByRole('button', { name: /Running\.\.\./ })).toBeDisabled();
		});

		it('shows elapsed current-run duration from current_run_started_at while running', () => {
			vi.useFakeTimers();
			vi.setSystemTime(new Date('2026-06-03T16:00:45.000Z'));
			const startedAt = new Date('2026-06-03T16:00:00.000Z').toISOString();
			const runOnceService = {
				...mockService,
				last_execution_status: 'running' as const,
				last_execution_at: new Date('2026-06-03T15:55:00.000Z').toISOString(),
				current_run_started_at: startedAt,
				last_execution_duration: 0,
			};

			render(
				withProviders(
					<IndividualServiceControls service={runOnceService} unifiedServiceRunning={false} />
				)
			);

			expect(screen.getByText(/Running - 45\.0s/)).toBeInTheDocument();

			act(() => {
				vi.advanceTimersByTime(2000);
			});
			expect(screen.getByText(/Running - 47\.0s/)).toBeInTheDocument();
			vi.useRealTimers();
		});

		it('keeps conflict warning visible while run is still active', async () => {
			vi.useFakeTimers();
			vi.mocked(serviceApi.runTaskOnce).mockResolvedValue({
				success: true,
				message: 'Task started',
				has_conflict: true,
				conflict_message: 'Task started recently as individual service',
			});

			const { rerender } = render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={false} />
				)
			);

			fireEvent.click(screen.getByText('Run Once'));
			await waitFor(() => {
				expect(screen.getByText(/Task started recently/i)).toBeInTheDocument();
			});

			act(() => {
				vi.advanceTimersByTime(10_000);
			});

			rerender(
				withProviders(
					<IndividualServiceControls
						service={{
							...mockService,
							last_execution_status: 'running',
							current_run_started_at: new Date().toISOString(),
							last_execution_duration: 0,
						}}
						unifiedServiceRunning={false}
					/>
				)
			);

			expect(screen.getByText(/Task started recently/i)).toBeInTheDocument();
			vi.useRealTimers();
		});

		it('displays stopped badge when service is not running', () => {
			render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={false} />
				)
			);

			const stoppedBadge = screen.getByText('Stopped');
			expect(stoppedBadge.className).toContain('bg-gray-500/20');
			expect(stoppedBadge.className).toContain('text-gray-400');
		});

		it('displays disabled badge when schedule is disabled', () => {
			const disabledService = { ...mockService, schedule_enabled: false };

			render(
				withProviders(
					<IndividualServiceControls service={disabledService} unifiedServiceRunning={false} />
				)
			);

			expect(screen.getByText('Disabled')).toBeInTheDocument();
		});
	});

	describe('Service control actions', () => {
		it('starts and stops individual service', async () => {
			vi.mocked(serviceApi.startIndividualService).mockResolvedValue({
				success: true,
				message: 'Started',
			});
			vi.mocked(serviceApi.stopIndividualService).mockResolvedValue({
				success: true,
				message: 'Stopped',
			});

			const { rerender } = render(
				withProviders(
					<IndividualServiceControls service={mockService} unifiedServiceRunning={false} />
				)
			);

			const startBtn = screen.getByRole('button', { name: 'Start Service' });
			expect(startBtn).not.toBeDisabled();
			fireEvent.click(startBtn);
			await waitFor(() => {
				expect(serviceApi.startIndividualService).toHaveBeenCalledWith({ task_name: 'analysis' });
			});

			rerender(
				withProviders(
					<IndividualServiceControls
						service={{ ...mockService, is_running: true, started_at: new Date().toISOString() }}
						unifiedServiceRunning={false}
					/>
				)
			);
			fireEvent.click(screen.getByRole('button', { name: 'Stop Service' }));
			await waitFor(() => {
				expect(serviceApi.stopIndividualService).toHaveBeenCalledWith({ task_name: 'analysis' });
			});
		});
	});
});
