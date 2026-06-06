import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { LogIdCell } from '../dashboard/LogIdCell';

describe('LogIdCell', () => {
	beforeEach(() => {
		Object.assign(navigator, {
			clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
		});
	});

	it('renders numeric log id and copies on click', async () => {
		render(<LogIdCell log={{ id: 42 } as never} />);
		fireEvent.click(screen.getByRole('button', { title: 'Click to copy log ID' }));

		expect(navigator.clipboard.writeText).toHaveBeenCalledWith('42');
		await waitFor(() => {
			expect(screen.getByText('Copied!')).toBeInTheDocument();
		});
	});

	it('renders file:line format with colored segments', () => {
		render(<LogIdCell log={{ id: 'analysis.py:123' } as never} />);
		expect(screen.getByText('analysis.py')).toBeInTheDocument();
		expect(screen.getByText('123')).toBeInTheDocument();
	});

	it('handles clipboard copy failures gracefully', async () => {
		const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
		Object.assign(navigator, {
			clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
		});

		render(<LogIdCell log={{ id: 99 } as never} />);
		fireEvent.click(screen.getByRole('button', { title: 'Click to copy log ID' }));

		await waitFor(() => {
			expect(errorSpy).toHaveBeenCalled();
		});
		errorSpy.mockRestore();
	});
});
