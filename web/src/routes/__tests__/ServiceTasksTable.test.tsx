import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ServiceTasksTable } from '../dashboard/ServiceTasksTable';
import { type TaskExecution } from '@/api/service';

// Helper to create mock tasks
const createMockTasks = (count: number): TaskExecution[] => {
	return Array.from({ length: count }, (_, i) => ({
		id: `task-${i + 1}`,
		task_name: `task_${i + 1}`,
		executed_at: new Date(2024, 0, 1, 10, i).toISOString(),
		status: i % 3 === 0 ? 'success' : i % 3 === 1 ? 'failed' : 'skipped',
		duration_seconds: Math.random() * 10,
		details: i % 2 === 0 ? { some: 'details' } : null,
	}));
};

describe('ServiceTasksTable', () => {
	describe('Bug #75: Pagination functionality', () => {
		it('displays first 10 tasks by default', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Should show "Showing 1-10 of 25 tasks"
			expect(screen.getByText(/Showing 1-10 of 25 tasks/i)).toBeInTheDocument();

			// Should display first 10 tasks
			expect(screen.getByText('task_1')).toBeInTheDocument();
			expect(screen.getByText('task_10')).toBeInTheDocument();
			// Should NOT display task 11
			expect(screen.queryByText('task_11')).not.toBeInTheDocument();
		});

		it('allows changing page size to 25', () => {
			const tasks = createMockTasks(50);
			const { container } = render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Change page size to 25
			const pageSizeSelect = container.querySelector('select') as HTMLSelectElement;
			fireEvent.change(pageSizeSelect, { target: { value: '25' } });

			// Should show "Showing 1-25 of 50 tasks"
			expect(screen.getByText(/Showing 1-25 of 50 tasks/i)).toBeInTheDocument();

			// Should display first 25 tasks
			expect(screen.getByText('task_1')).toBeInTheDocument();
			expect(screen.getByText('task_25')).toBeInTheDocument();
			// Should NOT display task 26
			expect(screen.queryByText('task_26')).not.toBeInTheDocument();
		});

		it('allows changing page size to 50', () => {
			const tasks = createMockTasks(60);
			const { container } = render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Change page size to 50
			const pageSizeSelect = container.querySelector('select') as HTMLSelectElement;
			fireEvent.change(pageSizeSelect, { target: { value: '50' } });

			// Should show "Showing 1-50 of 60 tasks"
			expect(screen.getByText(/Showing 1-50 of 60 tasks/i)).toBeInTheDocument();
		});

		it('navigates to next page', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Click next page button
			const nextButton = screen.getByTitle('Next page');
			fireEvent.click(nextButton);

			// Should show page 2
			expect(screen.getByText(/Page 2 of 3/i)).toBeInTheDocument();
			expect(screen.getByText(/Showing 11-20 of 25 tasks/i)).toBeInTheDocument();

			// Should display tasks 11-20
			expect(screen.getByText('task_11')).toBeInTheDocument();
			expect(screen.getByText('task_20')).toBeInTheDocument();
			// Should NOT display task 10 or 21
			expect(screen.queryByText('task_10')).not.toBeInTheDocument();
			expect(screen.queryByText('task_21')).not.toBeInTheDocument();
		});

		it('navigates to previous page', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Go to page 2
			const nextButton = screen.getByTitle('Next page');
			fireEvent.click(nextButton);

			// Then go back to page 1
			const prevButton = screen.getByTitle('Previous page');
			fireEvent.click(prevButton);

			// Should show page 1
			expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
			expect(screen.getByText(/Showing 1-10 of 25 tasks/i)).toBeInTheDocument();
		});

		it('navigates to first page', () => {
			const tasks = createMockTasks(30);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Go to page 3
			const nextButton = screen.getByTitle('Next page');
			fireEvent.click(nextButton);
			fireEvent.click(nextButton);

			// Click first page button
			const firstButton = screen.getByTitle('First page');
			fireEvent.click(firstButton);

			// Should show page 1
			expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
		});

		it('navigates to last page', () => {
			const tasks = createMockTasks(30);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Click last page button
			const lastButton = screen.getByTitle('Last page');
			fireEvent.click(lastButton);

			// Should show last page (page 3)
			expect(screen.getByText(/Page 3 of 3/i)).toBeInTheDocument();
			expect(screen.getByText(/Showing 21-30 of 30 tasks/i)).toBeInTheDocument();
		});

		it('disables first/prev buttons on first page', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			const firstButton = screen.getByTitle('First page');
			const prevButton = screen.getByTitle('Previous page');

			expect(firstButton).toBeDisabled();
			expect(prevButton).toBeDisabled();
		});

		it('disables next/last buttons on last page', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Go to last page
			const lastButton = screen.getByTitle('Last page');
			fireEvent.click(lastButton);

			const nextButton = screen.getByTitle('Next page');
			expect(nextButton).toBeDisabled();
			expect(lastButton).toBeDisabled();
		});

		it('resets to page 1 when page size changes', () => {
			const tasks = createMockTasks(50);
			const { container } = render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Go to page 2
			const nextButton = screen.getByTitle('Next page');
			fireEvent.click(nextButton);
			expect(screen.getByText(/Page 2 of 5/i)).toBeInTheDocument();

			// Change page size
			const pageSizeSelect = container.querySelector('select') as HTMLSelectElement;
			fireEvent.change(pageSizeSelect, { target: { value: '25' } });

			// Should reset to page 1
			expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument();
		});

		it('displays correct page count', () => {
			const tasks = createMockTasks(25);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// 25 tasks with 10 per page = 3 pages
			expect(screen.getByText(/Page 1 of 3/i)).toBeInTheDocument();
		});

		it('handles partial last page correctly', () => {
			const tasks = createMockTasks(23);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// Go to last page
			const lastButton = screen.getByTitle('Last page');
			fireEvent.click(lastButton);

			// Should show "Showing 21-23 of 23 tasks"
			expect(screen.getByText(/Showing 21-23 of 23 tasks/i)).toBeInTheDocument();
		});
	});

	describe('Table display', () => {
		it('shows loading state', () => {
			render(<ServiceTasksTable tasks={[]} isLoading={true} />);
			expect(screen.getByText(/Loading tasks\.\.\./i)).toBeInTheDocument();
		});

		it('shows empty state when no tasks', () => {
			render(<ServiceTasksTable tasks={[]} isLoading={false} />);
			expect(screen.getByText(/No task executions found/i)).toBeInTheDocument();
		});

		it('displays task information correctly', () => {
			const tasks = createMockTasks(5);
			render(<ServiceTasksTable tasks={tasks} isLoading={false} />);

			// The table now uses accordion-style details/summary, no visible headers
			// Should display task names in the accordion summaries
			expect(screen.getByText('task_1')).toBeInTheDocument();
			expect(screen.getByText('task_2')).toBeInTheDocument();

			// Should display statuses (multiple can exist, so use getAllByText and check at least one)
			const successElements = screen.getAllByText('SUCCESS');
			expect(successElements.length).toBeGreaterThan(0);
			const failedElements = screen.getAllByText('FAILED');
			expect(failedElements.length).toBeGreaterThan(0);
		});
	});
});
