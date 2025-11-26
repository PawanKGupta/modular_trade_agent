import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TaskDetailsView } from '../dashboard/TaskDetailsView';

describe('TaskDetailsView', () => {
	it('renders key metrics correctly', () => {
		const details = {
			success: true,
			return_code: 0,
			timeout_seconds: 30,
			max_retries: 3,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText(/Success/i)).toBeInTheDocument();
		expect(screen.getByText(/Exit Code:/i)).toBeInTheDocument();
		expect(screen.getByText('0')).toBeInTheDocument();
		expect(screen.getByText(/Timeout:/i)).toBeInTheDocument();
		expect(screen.getByText('30s')).toBeInTheDocument();
		expect(screen.getByText(/Max Retries:/i)).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
	});

	it('displays failed status correctly', () => {
		const details = {
			success: false,
			return_code: 1,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText(/Failed/i)).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
	});

	it('auto-extracts and displays task metrics with correct labels', () => {
		const details = {
			sell_orders_placed: 5,
			buy_orders_placed: 3,
			orders_modified: 2,
			positions_closed: 1,
			results_count: 10,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Task Metrics')).toBeInTheDocument();
		expect(screen.getByText('5')).toBeInTheDocument();
		expect(screen.getByText('Sell Orders Placed')).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
		expect(screen.getByText('Buy Orders Placed')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
		expect(screen.getByText('Orders Modified')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
		expect(screen.getByText('Positions Closed')).toBeInTheDocument();
		expect(screen.getByText('10')).toBeInTheDocument();
		expect(screen.getByText('Results Count')).toBeInTheDocument();
	});

	it('auto-extracts metrics ending with _count, _placed, _modified, etc.', () => {
		const details = {
			items_processed: 100,
			records_inserted: 50,
			records_updated: 20,
			records_deleted: 5,
			operations_skipped: 10,
			operations_failed: 2,
			requests_retried: 3,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Task Metrics')).toBeInTheDocument();
		expect(screen.getByText('100')).toBeInTheDocument();
		expect(screen.getByText('Items Processed')).toBeInTheDocument();
		expect(screen.getByText('50')).toBeInTheDocument();
		expect(screen.getByText('Records Inserted')).toBeInTheDocument();
		expect(screen.getByText('20')).toBeInTheDocument();
		expect(screen.getByText('Records Updated')).toBeInTheDocument();
		expect(screen.getByText('5')).toBeInTheDocument();
		expect(screen.getByText('Records Deleted')).toBeInTheDocument();
		expect(screen.getByText('10')).toBeInTheDocument();
		expect(screen.getByText('Operations Skipped')).toBeInTheDocument();
		expect(screen.getByText('2')).toBeInTheDocument();
		expect(screen.getByText('Operations Failed')).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
		expect(screen.getByText('Requests Retried')).toBeInTheDocument();
	});

	it('does not show task metrics section when no metrics present', () => {
		const details = {
			success: true,
			return_code: 0,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.queryByText('Task Metrics')).not.toBeInTheDocument();
	});

	it('does not extract non-metric numeric fields', () => {
		const details = {
			duration: 123,
			timestamp: 1234567890,
			sell_orders_placed: 5,
		};

		render(<TaskDetailsView details={details} />);

		// sell_orders_placed should be in Task Metrics
		expect(screen.getByText('5')).toBeInTheDocument();
		expect(screen.getByText('Sell Orders Placed')).toBeInTheDocument();

		// duration and timestamp should NOT be in Task Metrics (no matching suffix)
		expect(screen.queryByText('Duration')).not.toBeInTheDocument();
		expect(screen.queryByText('Timestamp')).not.toBeInTheDocument();
	});

	it('displays analysis summary correctly', () => {
		const details = {
			analysis_summary: {
				processed: 100,
				inserted: 50,
				updated: 20,
				skipped: 5,
			},
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Analysis Summary')).toBeInTheDocument();
		expect(screen.getByText('100')).toBeInTheDocument();
		expect(screen.getByText('processed')).toBeInTheDocument();
		expect(screen.getByText('50')).toBeInTheDocument();
		expect(screen.getByText('inserted')).toBeInTheDocument();
		expect(screen.getByText('20')).toBeInTheDocument();
		expect(screen.getByText('updated')).toBeInTheDocument();
		expect(screen.getByText('5')).toBeInTheDocument();
		expect(screen.getByText('skipped')).toBeInTheDocument();
	});

	it('displays error details section when error fields present', () => {
		const details = {
			error_type: 'RuntimeError',
			error_message: 'Something went wrong',
			exception: 'RuntimeError: Something went wrong\n  at line 123',
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Error Details')).toBeInTheDocument();
		expect(screen.getByText(/Type:/i)).toBeInTheDocument();
		expect(screen.getByText('RuntimeError')).toBeInTheDocument();
		expect(screen.getByText(/Message:/i)).toBeInTheDocument();
		expect(screen.getByText(/Exception:/i)).toBeInTheDocument();
		// Both error_message and exception should be present
		const errorTexts = screen.getAllByText(/Something went wrong/);
		expect(errorTexts.length).toBeGreaterThanOrEqual(1);
	});

	it('does not display duplicate exception if same as error_message', () => {
		const details = {
			error_type: 'RuntimeError',
			error_message: 'Something went wrong',
			exception: 'Something went wrong', // Same as error_message
		};

		render(<TaskDetailsView details={details} />);

		// Should only show error_message section, not exception
		const messageHeaders = screen.getAllByText(/Message:/i);
		expect(messageHeaders).toHaveLength(1);
		expect(screen.queryByText(/Exception:/i)).not.toBeInTheDocument();
	});

	it('displays stdout_tail with log formatting', () => {
		const details = {
			stdout_tail: '2025-11-26 10:00:00 - INFO - Starting process\n2025-11-26 10:00:01 - SUCCESS - Process completed\n2025-11-26 10:00:02 - WARNING - Minor issue detected',
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Output Log')).toBeInTheDocument();
		expect(screen.getByText(/last 10 lines, 200 char limit/i)).toBeInTheDocument();
		expect(screen.getByText(/Starting process/)).toBeInTheDocument();
		expect(screen.getByText(/Process completed/)).toBeInTheDocument();
		expect(screen.getByText(/Minor issue detected/)).toBeInTheDocument();
	});

	it('displays stderr_tail with error styling', () => {
		const details = {
			stderr_tail: 'ERROR: Failed to connect\nTraceback (most recent call last):\n  File "test.py", line 1',
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText('Error Log')).toBeInTheDocument();
		expect(screen.getByText(/Failed to connect/)).toBeInTheDocument();
		expect(screen.getByText(/Traceback/)).toBeInTheDocument();
	});

	it('truncates long log lines to 200 characters', () => {
		const longLine = 'A'.repeat(250);
		const details = {
			stdout_tail: longLine,
		};

		render(<TaskDetailsView details={details} />);

		// Should show truncated indicator
		expect(screen.getByText(/\.\.\. \[\+50 chars - click to expand\]/i)).toBeInTheDocument();
	});

	it('shows only last 10 lines of logs', () => {
		const lines = Array.from({ length: 20 }, (_, i) => `Line ${i + 1}`).join('\n');
		const details = {
			stdout_tail: lines,
		};

		render(<TaskDetailsView details={details} />);

		// Should show indicator for hidden lines
		expect(screen.getByText(/\(10 earlier lines hidden\)/i)).toBeInTheDocument();

		// Should show lines 11-20
		expect(screen.getByText(/Line 20/)).toBeInTheDocument();
		expect(screen.getByText(/Line 11/)).toBeInTheDocument();

		// Should not show lines 1-10
		expect(screen.queryByText('Line 1')).not.toBeInTheDocument();
		expect(screen.queryByText('Line 10')).not.toBeInTheDocument();
	});

	it('displays additional fields in collapsible section', () => {
		const details = {
			success: true,
			custom_field: 'custom_value',
			another_field: 123,
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.getByText(/Additional Fields \(2\)/i)).toBeInTheDocument();
	});

	it('does not show additional fields section when empty', () => {
		const details = {
			success: true,
			return_code: 0,
			sell_orders_placed: 5, // This will be extracted to task metrics
		};

		render(<TaskDetailsView details={details} />);

		expect(screen.queryByText(/Additional Fields/i)).not.toBeInTheDocument();
	});

	it('handles empty details gracefully', () => {
		const details = {};

		render(<TaskDetailsView details={details} />);

		// Should render without errors
		expect(screen.queryByText('Task Metrics')).not.toBeInTheDocument();
		expect(screen.queryByText('Analysis Summary')).not.toBeInTheDocument();
		expect(screen.queryByText('Output Log')).not.toBeInTheDocument();
	});

	it('excludes extracted metrics from additional fields', () => {
		const details = {
			sell_orders_placed: 5,
			buy_orders_placed: 3,
			error_type: 'RuntimeError',
			error_message: 'Error occurred',
			custom_field: 'should_appear',
		};

		render(<TaskDetailsView details={details} />);

		// Task metrics should be in their own section
		expect(screen.getByText('Task Metrics')).toBeInTheDocument();

		// Error fields should be in error details section
		expect(screen.getByText('Error Details')).toBeInTheDocument();

		// Additional fields should only contain custom_field
		expect(screen.getByText(/Additional Fields \(1\)/i)).toBeInTheDocument();
	});
});
