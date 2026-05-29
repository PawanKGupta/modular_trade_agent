import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MLTrainingJobsTable } from '../dashboard/MLTrainingJobsTable';

describe('MLTrainingJobsTable', () => {
	it('shows loading and empty states', () => {
		const { rerender } = render(<MLTrainingJobsTable jobs={[]} isLoading />);
		expect(screen.getByText(/Loading training jobs/i)).toBeInTheDocument();

		rerender(<MLTrainingJobsTable jobs={[]} isLoading={false} />);
		expect(screen.getByText(/No training jobs yet/i)).toBeInTheDocument();
	});

	it('renders failed job error message', () => {
		render(
			<MLTrainingJobsTable
				jobs={[
					{
						id: 3,
						model_type: 'lgbm',
						algorithm: 'lightgbm',
						status: 'failed',
						error_message: 'Out of memory',
						accuracy: null,
						started_at: '2025-01-01T10:00:00.000Z',
					},
				]}
				isLoading={false}
			/>
		);

		expect(screen.getByText('Out of memory')).toBeInTheDocument();
		expect(screen.getByText('failed')).toBeInTheDocument();
	});
});
