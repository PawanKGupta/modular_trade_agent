import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuickFilters } from '../dashboard/QuickFilters';

describe('QuickFilters', () => {
	it('applies quick filters and clears', () => {
		const onFilter = vi.fn();
		const onClear = vi.fn();
		render(<QuickFilters onFilter={onFilter} onClear={onClear} />);

		fireEvent.click(screen.getByRole('button', { name: 'Last Hour' }));
		expect(onFilter).toHaveBeenCalledWith(
			expect.objectContaining({ startTime: expect.any(String), endTime: expect.any(String) })
		);

		fireEvent.click(screen.getByRole('button', { name: 'Errors Only' }));
		expect(onFilter).toHaveBeenCalledWith({ level: 'ERROR' });

		fireEvent.click(screen.getByRole('button', { name: 'Today' }));
		fireEvent.click(screen.getByRole('button', { name: 'This Week' }));
		expect(onFilter).toHaveBeenCalledWith({ daysBack: 7 });

		fireEvent.click(screen.getByRole('button', { name: 'Clear Filters' }));
		expect(onClear).toHaveBeenCalled();
	});
});
