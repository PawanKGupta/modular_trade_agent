import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IndividualServiceControls } from '../dashboard/IndividualServiceControls';
import { withProviders } from '@/test/utils';
import * as serviceApi from '@/api/service';
import { type IndividualServiceStatus } from '@/api/service';

// Mock the service API
vi.mock('@/api/service', () => ({
	startIndividualService: vi.fn(),
	stopIndividualService: vi.fn(),
	runTaskOnce: vi.fn(),
}));

const mockService: IndividualServiceStatus = {
	task_name: 'analysis',
	is_running: false,
	schedule_enabled: true,
	last_execution_at: null,
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

			const runningBadge = screen.getByText('Running');
			expect(runningBadge.className).toContain('bg-green-500/20');
			expect(runningBadge.className).toContain('text-green-400');
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
});
