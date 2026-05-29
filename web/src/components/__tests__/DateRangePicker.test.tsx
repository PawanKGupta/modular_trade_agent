import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DateRangePicker, type DateRange } from '../DateRangePicker';

const defaultRange: DateRange = {
	startDate: '2025-01-01',
	endDate: '2025-01-31',
};

describe('DateRangePicker', () => {
	it('renders date inputs and updates start/end dates', () => {
		const onChange = vi.fn();
		render(<DateRangePicker value={defaultRange} onChange={onChange} />);

		expect(screen.getByLabelText('From:')).toHaveValue('2025-01-01');
		expect(screen.getByLabelText('To:')).toHaveValue('2025-01-31');

		fireEvent.change(screen.getByLabelText('From:'), { target: { value: '2025-01-05' } });
		expect(onChange).toHaveBeenCalledWith({ startDate: '2025-01-05', endDate: '2025-01-31' });

		fireEvent.change(screen.getByLabelText('To:'), { target: { value: '2025-01-20' } });
		expect(onChange).toHaveBeenCalledWith({ startDate: '2025-01-01', endDate: '2025-01-20' });
	});

	it('opens presets and applies 7-day range', () => {
		const onChange = vi.fn();
		render(<DateRangePicker value={defaultRange} onChange={onChange} />);

		fireEvent.click(screen.getByRole('button', { name: /Presets/i }));
		fireEvent.click(screen.getByRole('button', { name: '7 Days' }));

		expect(onChange).toHaveBeenCalledWith(
			expect.objectContaining({
				startDate: expect.any(String),
				endDate: expect.any(String),
			})
		);
	});

	it('applies All Time preset', () => {
		const onChange = vi.fn();
		render(<DateRangePicker value={defaultRange} onChange={onChange} />);

		fireEvent.click(screen.getByRole('button', { name: /Presets/i }));
		fireEvent.click(screen.getByRole('button', { name: 'All Time' }));

		expect(onChange).toHaveBeenCalled();
		const call = onChange.mock.calls[0][0] as DateRange;
		expect(call.startDate < call.endDate).toBe(true);
	});
});
