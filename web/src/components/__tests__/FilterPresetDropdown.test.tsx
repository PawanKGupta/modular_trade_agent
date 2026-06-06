import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FilterPresetDropdown } from '../FilterPresetDropdown';

describe('FilterPresetDropdown', () => {
	const presets = {
		'My Preset': { status: 'active' },
		'Another': { limit: 50 },
	};

	it('loads a preset from dropdown', () => {
		const onLoadPreset = vi.fn();
		render(
			<FilterPresetDropdown
				presets={presets}
				onLoadPreset={onLoadPreset}
				onSavePreset={vi.fn()}
				onDeletePreset={vi.fn()}
				currentFilters={{ status: 'all' }}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Filter Presets/i }));
		fireEvent.click(screen.getByText('My Preset'));
		expect(onLoadPreset).toHaveBeenCalledWith({ status: 'active' });
	});

	it('validates and saves a new preset', async () => {
		const onSavePreset = vi.fn().mockResolvedValue(true);
		render(
			<FilterPresetDropdown
				presets={presets}
				onLoadPreset={vi.fn()}
				onSavePreset={onSavePreset}
				onDeletePreset={vi.fn()}
				currentFilters={{ status: 'pending' }}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Filter Presets/i }));
		fireEvent.click(screen.getByRole('button', { name: /Save Current Filters/i }));

		fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
		expect(screen.getByText('Please enter a preset name')).toBeInTheDocument();

		fireEvent.change(screen.getByPlaceholderText(/Preset name/i), { target: { value: 'My Preset' } });
		fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
		expect(screen.getByText('Preset name already exists')).toBeInTheDocument();

		fireEvent.change(screen.getByPlaceholderText(/Preset name/i), { target: { value: 'New One' } });
		fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

		await waitFor(() => {
			expect(onSavePreset).toHaveBeenCalledWith('New One', { status: 'pending' });
		});
	});

	it('deletes preset after confirmation', async () => {
		const onDeletePreset = vi.fn().mockResolvedValue(true);
		vi.spyOn(window, 'confirm').mockReturnValue(true);

		render(
			<FilterPresetDropdown
				presets={presets}
				onLoadPreset={vi.fn()}
				onSavePreset={vi.fn()}
				onDeletePreset={onDeletePreset}
				currentFilters={{}}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Filter Presets/i }));
		fireEvent.click(screen.getAllByTitle('Delete preset')[0]);

		await waitFor(() => {
			expect(onDeletePreset).toHaveBeenCalledWith('My Preset');
		});
	});

	it('shows empty preset list and handles save failure and cancel', async () => {
		const onSavePreset = vi.fn().mockResolvedValue(false);
		render(
			<FilterPresetDropdown
				presets={{}}
				onLoadPreset={vi.fn()}
				onSavePreset={onSavePreset}
				onDeletePreset={vi.fn()}
				currentFilters={{ status: 'pending' }}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Filter Presets/i }));
		expect(screen.getByText('No saved presets')).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /Save Current Filters/i }));
		fireEvent.change(screen.getByPlaceholderText(/Preset name/i), { target: { value: 'Fail Me' } });
		fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
		await waitFor(() => expect(screen.getByText('Failed to save preset')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
		expect(screen.queryByPlaceholderText(/Preset name/i)).not.toBeInTheDocument();
	});

	it('closes dropdown when clicking outside overlay', () => {
		render(
			<FilterPresetDropdown
				presets={presets}
				onLoadPreset={vi.fn()}
				onSavePreset={vi.fn()}
				onDeletePreset={vi.fn()}
				currentFilters={{}}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: /Filter Presets/i }));
		expect(screen.getByText('My Preset')).toBeInTheDocument();

		const overlay = document.querySelector('.fixed.inset-0');
		expect(overlay).toBeTruthy();
		fireEvent.click(overlay!);
		expect(screen.queryByText('My Preset')).not.toBeInTheDocument();
	});
});
