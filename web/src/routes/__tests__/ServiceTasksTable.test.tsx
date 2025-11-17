import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceTasksTable } from '../dashboard/ServiceTasksTable';
import type { TaskExecution } from '@/api/service';

describe('ServiceTasksTable', () => {
	const mockTasks: TaskExecution[] = [
		{
			id: 1,
			task_name: 'premarket_retry',
			executed_at: new Date().toISOString(),
			status: 'success',
			duration_seconds: 1.5,
			details: { symbols_processed: 5 },
		},
		{
			id: 2,
			task_name: 'analysis',
			executed_at: new Date(Date.now() - 300000).toISOString(),
			status: 'failed',
			duration_seconds: 2.3,
			details: { error: 'Network timeout' },
		},
		{
			id: 3,
			task_name: 'buy_orders',
			executed_at: new Date(Date.now() - 600000).toISOString(),
			status: 'skipped',
			duration_seconds: 0.0,
			details: null,
		},
	];

	it('renders task table with tasks', () => {
		render(<ServiceTasksTable tasks={mockTasks} isLoading={false} />);

		expect(screen.getByText(/premarket_retry/i)).toBeInTheDocument();
		expect(screen.getByText(/analysis/i)).toBeInTheDocument();
		expect(screen.getByText(/buy_orders/i)).toBeInTheDocument();
	});

	it('displays task status with correct styling', () => {
		render(<ServiceTasksTable tasks={mockTasks} isLoading={false} />);

		expect(screen.getByText(/SUCCESS/i)).toBeInTheDocument();
		expect(screen.getByText(/FAILED/i)).toBeInTheDocument();
		expect(screen.getByText(/SKIPPED/i)).toBeInTheDocument();
	});

	it('displays task duration', () => {
		render(<ServiceTasksTable tasks={mockTasks} isLoading={false} />);

		expect(screen.getByText(/1.50s/i)).toBeInTheDocument();
		expect(screen.getByText(/2.30s/i)).toBeInTheDocument();
		expect(screen.getByText(/0.00s/i)).toBeInTheDocument();
	});

	it('shows expandable details for tasks with details', () => {
		render(<ServiceTasksTable tasks={mockTasks} isLoading={false} />);

		const detailsButtons = screen.getAllByText(/View/i);
		expect(detailsButtons.length).toBeGreaterThan(0);

		fireEvent.click(detailsButtons[0]);

		expect(screen.getByText(/symbols_processed/i)).toBeInTheDocument();
	});

	it('shows dash for tasks without details', () => {
		render(<ServiceTasksTable tasks={mockTasks} isLoading={false} />);

		const dashes = screen.getAllByText(/—/i);
		expect(dashes.length).toBeGreaterThan(0);
	});

	it('shows loading message when loading', () => {
		render(<ServiceTasksTable tasks={[]} isLoading={true} />);

		expect(screen.getByText(/Loading tasks.../i)).toBeInTheDocument();
	});

	it('shows empty message when no tasks', () => {
		render(<ServiceTasksTable tasks={[]} isLoading={false} />);

		expect(screen.getByText(/No task executions found/i)).toBeInTheDocument();
	});
});
