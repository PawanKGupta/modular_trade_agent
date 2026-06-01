import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LogTable } from '../dashboard/LogTable';

const log = {
	id: 1,
	user_id: 1,
	level: 'INFO',
	module: 'scheduler',
	message: 'Started job',
	context: { job: 'analysis' },
	timestamp: '2025-01-01T10:00:00.000Z',
};

describe('LogTable', () => {
	it('shows loading and empty states', () => {
		const { rerender } = render(<LogTable logs={[]} isLoading />);
		expect(screen.getByText(/Loading logs/i)).toBeInTheDocument();

		rerender(<LogTable logs={[]} />);
		expect(screen.getByText(/No logs found/i)).toBeInTheDocument();
	});

	it('renders logs with id column and refresh indicator', () => {
		render(
			<LogTable logs={[log]} showId isRefreshing searchTerm="analysis" />
		);

		expect(screen.getByText('Started job')).toBeInTheDocument();
		expect(screen.getByText(/Refreshing/i)).toBeInTheDocument();
		expect(screen.getByTitle('Click to copy log ID')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Show Context \(match\)/i })).toBeInTheDocument();
	});
});
