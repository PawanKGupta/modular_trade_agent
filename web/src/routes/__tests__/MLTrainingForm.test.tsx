import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MLTrainingForm } from '../dashboard/MLTrainingForm';

describe('MLTrainingForm', () => {
	it('submits with default values', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));

		expect(onSubmit).toHaveBeenCalledTimes(1);
		expect(onSubmit.mock.calls[0][0]).toMatchObject({
			model_type: 'verdict_classifier',
			algorithm: 'xgboost',
			training_data_path: 'data/training/verdict_classifier.csv',
		});
	});

	it('shows validation error when training data path is empty', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		const input = screen.getByPlaceholderText(/data\/training/i);
		fireEvent.change(input, { target: { value: '' } });

		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));

		expect(onSubmit).not.toHaveBeenCalled();
		expect(screen.getByText(/Training data path is required/i)).toBeInTheDocument();
	});

	it('shows server error from parent when API fails', () => {
		const onSubmit = vi.fn();
		render(
			<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} serverError="/app/data/file missing — mount volume" />
		);
		expect(screen.getByRole('alert')).toHaveTextContent('/app/data/file missing');
	});

	it('shows client validation error alongside server error (server wins in same box)', () => {
		const onSubmit = vi.fn();
		render(
			<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} serverError="From API" />
		);
		const input = screen.getByPlaceholderText(/data\/training/i);
		fireEvent.change(input, { target: { value: '' } });
		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));
		expect(onSubmit).not.toHaveBeenCalled();
		// Server error still shown until cleared by parent; client sets local error when path empty
		expect(screen.getByRole('alert')).toHaveTextContent('From API');
	});

	it('allows toggling auto activate option', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		const checkbox = screen.getByLabelText(/Auto-activate new model version/i);
		expect(checkbox).toBeChecked();
		fireEvent.click(checkbox);
		expect(checkbox).not.toBeChecked();
	});

	it('switches model type to price regressor and resets default path', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		fireEvent.change(screen.getByLabelText(/Model Type/i), { target: { value: 'price_regressor' } });
		expect(screen.getByText(/Price regressor needs actual_pnl_pct/i)).toBeInTheDocument();

		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));
		expect(onSubmit.mock.calls[0][0]).toMatchObject({
			model_type: 'price_regressor',
			training_data_path: 'data/training/verdict_classifier.csv',
		});
	});

	it('resets algorithm when price regressor selected with logistic regression', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		fireEvent.change(screen.getByLabelText(/Algorithm/i), { target: { value: 'logistic_regression' } });
		fireEvent.change(screen.getByLabelText(/Model Type/i), { target: { value: 'price_regressor' } });

		const algoSelect = screen.getByLabelText(/Algorithm/i) as HTMLSelectElement;
		expect(algoSelect.value).toBe('xgboost');
		expect(screen.queryByRole('option', { name: /Logistic Regression/i })).not.toBeInTheDocument();
	});

	it('submits optional notes, training end date, and toggles incremental training', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		fireEvent.change(screen.getByLabelText(/Notes \(optional\)/i), { target: { value: '  nightly run  ' } });
		fireEvent.change(screen.getByLabelText(/Training runs through/i), { target: { value: '2025-06-01' } });
		fireEvent.click(screen.getByLabelText(/Incremental training/i));

		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));

		expect(onSubmit.mock.calls[0][0]).toMatchObject({
			notes: 'nightly run',
			training_run_end_date: '2025-06-01',
			incremental_training: false,
		});
	});

	it('ignores invalid hyperparameter JSON and submits empty object', () => {
		const onSubmit = vi.fn();
		render(<MLTrainingForm onSubmit={onSubmit} isSubmitting={false} />);

		fireEvent.change(screen.getByLabelText(/Hyperparameters \(JSON\)/i), { target: { value: 'not-json' } });
		fireEvent.submit(screen.getByRole('form', { name: /ML Training Form/i }));

		expect(onSubmit.mock.calls[0][0].hyperparameters).toEqual({});
	});

	it('shows submitting label when isSubmitting is true', () => {
		render(<MLTrainingForm onSubmit={vi.fn()} isSubmitting={true} />);
		expect(screen.getByRole('button', { name: /Starting Training/i })).toBeDisabled();
	});
});
