import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorLogTable } from '../dashboard/ErrorLogTable';

const sampleError = {
	id: 1,
	user_id: 1,
	error_type: 'ValueError',
	error_message: 'Bad data',
	traceback: 'Trace line 1',
	context: { key: 'value' },
	occurred_at: '2025-01-01T10:00:00.000Z',
	resolved: false,
	resolution_notes: null,
};

describe('ErrorLogTable', () => {
	it('shows loading and empty states', () => {
		const { rerender } = render(<ErrorLogTable errors={[]} isLoading />);
		expect(screen.getByText(/Loading error logs/i)).toBeInTheDocument();

		rerender(<ErrorLogTable errors={[]} />);
		expect(screen.getByText(/No error logs found/i)).toBeInTheDocument();
	});

	it('expands details and resolves unresolved errors for admins', () => {
		const onResolve = vi.fn();
		render(
			<ErrorLogTable errors={[sampleError]} isAdmin onResolve={onResolve} />
		);

		fireEvent.click(screen.getByRole('button', { name: /Show Details/i }));
		expect(screen.getByText('Trace line 1')).toBeInTheDocument();
		expect(screen.getByText(/"key"/)).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /Hide Details/i }));
		expect(screen.queryByText('Trace line 1')).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /Resolve/i }));
		expect(onResolve).toHaveBeenCalledWith(sampleError);
	});

	it('shows dash for resolved errors without resolve action', () => {
		render(
			<ErrorLogTable
				errors={[{ ...sampleError, id: 2, resolved: true, resolution_notes: 'Fixed' }]}
				isAdmin
				onResolve={vi.fn()}
			/>
		);

		expect(screen.getByText('Resolved')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /Resolve/i })).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /Show Details/i }));
		expect(screen.getByText('Fixed')).toBeInTheDocument();
	});
});
