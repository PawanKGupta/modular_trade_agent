import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ExportButton } from '../ExportButton';

describe('ExportButton', () => {
	it('calls onExport and shows exporting state', async () => {
		const onExport = vi.fn().mockResolvedValue(undefined);
		render(<ExportButton onExport={onExport} label="Download CSV" />);

		fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }));

		await waitFor(() => {
			expect(onExport).toHaveBeenCalledTimes(1);
			expect(screen.getByRole('button', { name: 'Download CSV' })).not.toBeDisabled();
		});
	});

	it('shows error message when export fails', async () => {
		const onExport = vi.fn().mockRejectedValue(new Error('Network error'));
		render(<ExportButton onExport={onExport} />);

		fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

		await waitFor(() => {
			expect(screen.getByText('Network error')).toBeInTheDocument();
		});
	});

	it('respects disabled prop', () => {
		const onExport = vi.fn();
		render(<ExportButton onExport={onExport} disabled />);
		expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
	});
});
