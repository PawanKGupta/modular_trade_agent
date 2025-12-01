import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { ConfigPresets } from '../dashboard/ConfigPresets';
import { CONFIG_PRESETS } from '@/api/trading-config';

describe('ConfigPresets', () => {
	it('renders all presets', () => {
		const onApply = vi.fn();
		render(<ConfigPresets onApply={onApply} />);

		expect(screen.getByText(/Configuration Presets/i)).toBeInTheDocument();
		expect(screen.getByText(/Conservative/i)).toBeInTheDocument();
		expect(screen.getByText(/Moderate/i)).toBeInTheDocument();
		expect(screen.getByText(/Aggressive/i)).toBeInTheDocument();
	});

	it('displays preset descriptions', () => {
		const onApply = vi.fn();
		render(<ConfigPresets onApply={onApply} />);

		expect(screen.getByText(/Lower risk, fewer positions/i)).toBeInTheDocument();
		expect(screen.getByText(/Balanced risk and position sizing/i)).toBeInTheDocument();
		expect(screen.getByText(/Higher risk, more positions/i)).toBeInTheDocument();
	});

	it('calls onApply when preset is clicked', () => {
		const onApply = vi.fn();
		render(<ConfigPresets onApply={onApply} />);

		const conservativeCard = screen.getByText(/Conservative/i).closest('div');
		const conservativeButton = within(conservativeCard as HTMLElement).getByRole('button', { name: /Apply Preset/i });
		fireEvent.click(conservativeButton);

		expect(onApply).toHaveBeenCalledWith(CONFIG_PRESETS[0].config);
	});

	it('applies correct preset config', () => {
		const onApply = vi.fn();
		render(<ConfigPresets onApply={onApply} />);

		const buttons = screen.getAllByRole('button', { name: /Apply Preset/i });

		// Click moderate preset
		fireEvent.click(buttons[1]);
		expect(onApply).toHaveBeenCalledWith(CONFIG_PRESETS[1].config);

		// Click aggressive preset
		fireEvent.click(buttons[2]);
		expect(onApply).toHaveBeenCalledWith(CONFIG_PRESETS[2].config);
	});
});
