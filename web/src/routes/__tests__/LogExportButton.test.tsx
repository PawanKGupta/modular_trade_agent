import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LogExportButton, exportLogsToCsv, exportLogsToJson } from '../dashboard/LogExportButton';

describe('LogExportButton', () => {
	const logs = [
		{
			id: 1,
			user_id: 1,
			level: 'INFO',
			module: 'scheduler,test',
			message: 'Hello "world"',
			context: { key: 'value' },
			timestamp: '2025-01-01T10:00:00.000Z',
		},
	];

	beforeEach(() => {
		vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
		vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
		vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
		vi.spyOn(window, 'alert').mockImplementation(() => {});
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('exports CSV and JSON when logs exist', () => {
		render(<LogExportButton logs={logs} />);

		fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
		fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));

		expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
	});

	it('disables export buttons when no logs', () => {
		render(<LogExportButton logs={[]} />);

		expect(screen.getByRole('button', { name: 'Export CSV' })).toBeDisabled();
		expect(screen.getByRole('button', { name: 'Export JSON' })).toBeDisabled();
	});

	it('alerts when exporting empty log lists', () => {
		exportLogsToCsv([]);
		exportLogsToJson([]);
		expect(window.alert).toHaveBeenCalledTimes(2);
		expect(window.alert).toHaveBeenCalledWith('No logs to export');
	});

	it('exports logs without context payload', () => {
		render(
			<LogExportButton
				logs={[
					{
						id: 2,
						user_id: 1,
						level: 'ERROR',
						module: 'worker',
						message: 'plain message',
						context: null,
						timestamp: '2025-01-02T10:00:00.000Z',
					},
				]}
			/>
		);

		fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
		expect(URL.createObjectURL).toHaveBeenCalled();
	});
});
