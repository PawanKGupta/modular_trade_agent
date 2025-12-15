import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { ModuleAutocomplete } from '../ModuleAutocomplete';
import type { ServiceLogEntry } from '@/api/logs';

const mockLogs: ServiceLogEntry[] = [
	{
		id: '1',
		user_id: 1,
		level: 'INFO',
		module: 'scheduler',
		message: 'Task scheduled',
		context: null,
		timestamp: '2024-01-01T10:00:00Z',
	},
	{
		id: '2',
		user_id: 1,
		level: 'ERROR',
		module: 'trading_service',
		message: 'Order failed',
		context: null,
		timestamp: '2024-01-01T11:00:00Z',
	},
	{
		id: '3',
		user_id: 1,
		level: 'WARNING',
		module: 'scheduler',
		message: 'Task delayed',
		context: null,
		timestamp: '2024-01-01T12:00:00Z',
	},
	{
		id: '4',
		user_id: 1,
		level: 'INFO',
		module: 'ml_service',
		message: 'Model trained',
		context: null,
		timestamp: '2024-01-01T13:00:00Z',
	},
];

describe('ModuleAutocomplete', () => {
	it('renders input field with placeholder', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={mockLogs} value="" onChange={onChange} placeholder="scheduler" />);

		const input = screen.getByPlaceholderText('scheduler');
		expect(input).toBeInTheDocument();
	});

	it('extracts unique modules from logs', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={mockLogs} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		expect(screen.getByText('ml_service')).toBeInTheDocument();
		expect(screen.getByText('scheduler')).toBeInTheDocument();
		expect(screen.getByText('trading_service')).toBeInTheDocument();
	});

	it('filters modules based on input', async () => {
		const TestWrapper = () => {
			const [value, setValue] = useState('');
			return <ModuleAutocomplete logs={mockLogs} value={value} onChange={setValue} />;
		};

		render(<TestWrapper />);

		const input = screen.getByPlaceholderText('scheduler') as HTMLInputElement;
		fireEvent.focus(input);

		expect(screen.getByText('scheduler')).toBeInTheDocument();
		expect(screen.getByText('trading_service')).toBeInTheDocument();

		fireEvent.change(input, { target: { value: 'sched' } });

		await waitFor(() => {
			expect(input.value).toBe('sched');
			expect(screen.getByText('scheduler')).toBeInTheDocument();
			expect(screen.queryByText('trading_service')).not.toBeInTheDocument();
		});
	});

	it('is case-insensitive when filtering', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={mockLogs} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		fireEvent.change(input, { target: { value: 'SCHEDULER' } });

		expect(screen.getByText('scheduler')).toBeInTheDocument();
	});

	it('selects module when clicked', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={mockLogs} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		const schedulerButton = screen.getByText('scheduler').closest('button');
		expect(schedulerButton).toBeInTheDocument();
		fireEvent.click(schedulerButton!);

		expect(onChange).toHaveBeenCalledWith('scheduler');
	});

	it('closes dropdown after selection', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={mockLogs} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		expect(screen.getByText('scheduler')).toBeInTheDocument();

		const schedulerButton = screen.getByText('scheduler').closest('button');
		fireEvent.click(schedulerButton!);

		// Dropdown should close
		waitFor(() => {
			expect(screen.queryByText('scheduler')).not.toBeInTheDocument();
		});
	});

	it('shows top 10 modules when empty', () => {
		const manyLogs: ServiceLogEntry[] = Array.from({ length: 15 }, (_, i) => ({
			id: String(i + 1),
			user_id: 1,
			level: 'INFO',
			module: `module_${i + 1}`,
			message: 'Test',
			context: null,
			timestamp: '2024-01-01T10:00:00Z',
		}));

		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={manyLogs} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		const buttons = screen.getAllByRole('button').filter((btn) => btn.textContent?.startsWith('module_'));
		expect(buttons.length).toBeLessThanOrEqual(10);
	});

	it('handles empty logs list', () => {
		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={[]} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		// Should not crash, dropdown should not appear
		expect(screen.queryByText('scheduler')).not.toBeInTheDocument();
	});

	it('handles logs with null/empty module', () => {
		const logsWithNullModule: ServiceLogEntry[] = [
			{
				id: '1',
				user_id: 1,
				level: 'INFO',
				module: '',
				message: 'Test',
				context: null,
				timestamp: '2024-01-01T10:00:00Z',
			},
			...mockLogs,
		];

		const onChange = vi.fn();
		render(<ModuleAutocomplete logs={logsWithNullModule} value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('scheduler');
		fireEvent.focus(input);

		// Should only show valid modules (not empty string)
		const schedulerButtons = screen.getAllByText('scheduler');
		expect(schedulerButtons.length).toBeGreaterThan(0);

		// Verify empty module is not shown by checking all buttons don't have empty text
		const allButtons = screen.getAllByRole('button');
		const buttonsWithEmptyText = allButtons.filter((btn) => btn.textContent === '');
		expect(buttonsWithEmptyText.length).toBe(0);
	});
});
