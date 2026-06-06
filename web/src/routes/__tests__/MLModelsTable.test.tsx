import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MLModelsTable } from '../dashboard/MLModelsTable';

describe('MLModelsTable', () => {
	it('shows loading and empty states', () => {
		const { rerender } = render(
			<MLModelsTable models={[]} isLoading onActivate={vi.fn()} />
		);
		expect(screen.getByText(/Loading models/i)).toBeInTheDocument();

		rerender(<MLModelsTable models={[]} isLoading={false} onActivate={vi.fn()} />);
		expect(screen.getByText(/No trained models yet/i)).toBeInTheDocument();
	});

	it('renders models and handles activate click', () => {
		const onActivate = vi.fn();
		render(
			<MLModelsTable
				models={[
					{
						id: 7,
						model_type: 'xgboost',
						version: 'v1',
						training_data_through_date: '2025-01-01',
						accuracy: 0.912,
						is_active: false,
						created_at: '2025-01-02T10:00:00.000Z',
					},
				]}
				isLoading={false}
				onActivate={onActivate}
			/>
		);

		expect(screen.getByText('xgboost')).toBeInTheDocument();
		expect(screen.getByText('91.20%')).toBeInTheDocument();
		fireEvent.click(screen.getByRole('button', { name: 'Activate' }));
		expect(onActivate).toHaveBeenCalledWith(7);
	});
});
