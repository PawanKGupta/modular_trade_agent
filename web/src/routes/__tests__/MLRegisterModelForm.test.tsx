import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MLRegisterModelForm } from '../dashboard/MLRegisterModelForm';

describe('MLRegisterModelForm', () => {
	it('renders form fields and initial states', () => {
		const onSubmit = vi.fn();
		const { container } = render(
			<MLRegisterModelForm onSubmit={onSubmit} isSubmitting={false} serverError={null} />
		);

		expect(screen.getByText(/Model Type/i)).toBeInTheDocument();
		expect(screen.getByRole('combobox')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('e.g. v0-legacy')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('/app/models/verdict_model_random_forest.pkl')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('e.g. 0.732')).toBeInTheDocument();
		expect(container.querySelector('input[type="date"]')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('e.g. Phase 5 dataset, walk-forward validated')).toBeInTheDocument();
		expect(screen.getByLabelText(/Auto-activate and deploy/i)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Register Model/i })).toBeInTheDocument();
	});

	it('handles input changes and submits payload', () => {
		const onSubmit = vi.fn();
		const { container } = render(
			<MLRegisterModelForm onSubmit={onSubmit} isSubmitting={false} serverError={null} />
		);

		// Type version
		const versionInput = screen.getByPlaceholderText('e.g. v0-legacy');
		fireEvent.change(versionInput, { target: { value: 'v3.0' } });

		// Type model path
		const pathInput = screen.getByPlaceholderText('/app/models/verdict_model_random_forest.pkl');
		fireEvent.change(pathInput, { target: { value: '/app/models/new_model.pkl' } });

		// Type accuracy
		const accuracyInput = screen.getByPlaceholderText('e.g. 0.732');
		fireEvent.change(accuracyInput, { target: { value: '0.85' } });

		// Select type
		const typeSelect = screen.getByRole('combobox');
		fireEvent.change(typeSelect, { target: { value: 'price_regressor' } });

		// Type training data through
		const throughDateInput = container.querySelector('input[type="date"]')!;
		fireEvent.change(throughDateInput, { target: { value: '2026-06-20' } });

		// Type notes
		const notesInput = screen.getByPlaceholderText('e.g. Phase 5 dataset, walk-forward validated');
		fireEvent.change(notesInput, { target: { value: 'Test registration notes' } });

		// Check auto-activate
		const autoActivateCheckbox = screen.getByLabelText(/Auto-activate and deploy/i);
		fireEvent.click(autoActivateCheckbox);

		// Submit form
		const submitButton = screen.getByRole('button', { name: /Register Model/i });
		fireEvent.click(submitButton);

		expect(onSubmit).toHaveBeenCalledWith({
			model_type: 'price_regressor',
			model_path: '/app/models/new_model.pkl',
			version: 'v3.0',
			accuracy: 0.85,
			training_data_through_date: '2026-06-20',
			notes: 'Test registration notes',
			auto_activate: true,
		});
	});

	it('handles null values for optional fields', () => {
		const onSubmit = vi.fn();
		render(<MLRegisterModelForm onSubmit={onSubmit} isSubmitting={false} serverError={null} />);

		const versionInput = screen.getByPlaceholderText('e.g. v0-legacy');
		fireEvent.change(versionInput, { target: { value: 'v1.0' } });

		const pathInput = screen.getByPlaceholderText('/app/models/verdict_model_random_forest.pkl');
		fireEvent.change(pathInput, { target: { value: '/app/models/test.pkl' } });

		// Submit with other inputs empty
		const submitButton = screen.getByRole('button', { name: /Register Model/i });
		fireEvent.click(submitButton);

		expect(onSubmit).toHaveBeenCalledWith({
			model_type: 'verdict_classifier',
			model_path: '/app/models/test.pkl',
			version: 'v1.0',
			accuracy: null,
			training_data_through_date: null,
			notes: null,
			auto_activate: false,
		});
	});

	it('displays server error if provided', () => {
		const onSubmit = vi.fn();
		render(
			<MLRegisterModelForm
				onSubmit={onSubmit}
				isSubmitting={false}
				serverError="Failed to locate model file"
			/>
		);

		const errorAlert = screen.getByRole('alert');
		expect(errorAlert).toBeInTheDocument();
		expect(errorAlert.textContent).toContain('Failed to locate model file');
	});

	it('disables submit button and shows loading text during submission', () => {
		const onSubmit = vi.fn();
		render(<MLRegisterModelForm onSubmit={onSubmit} isSubmitting={true} serverError={null} />);

		const submitButton = screen.getByRole('button', { name: /Registering…/i });
		expect(submitButton).toBeDisabled();
	});
});
