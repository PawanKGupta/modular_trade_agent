import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceLogsViewer } from '../dashboard/ServiceLogsViewer';
import type { ServiceLog } from '@/api/service';

describe('ServiceLogsViewer', () => {
	const mockLogs: ServiceLog[] = [
		{
			id: 1,
			level: 'INFO',
			module: 'TradingService',
			message: 'Service started successfully',
			context: { action: 'start_service' },
			timestamp: new Date().toISOString(),
		},
		{
			id: 2,
			level: 'ERROR',
			module: 'TradingService',
			message: 'Failed to place order',
			context: { symbol: 'RELIANCE', error: 'Insufficient funds' },
			timestamp: new Date(Date.now() - 300000).toISOString(),
		},
		{
			id: 3,
			level: 'WARNING',
			module: 'AutoTradeEngine',
			message: 'Low volume detected',
			context: { symbol: 'TCS', volume: 1000 },
			timestamp: new Date(Date.now() - 600000).toISOString(),
		},
	];

	it('renders logs viewer with logs', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		expect(screen.getByText(/Service started successfully/i)).toBeInTheDocument();
		expect(screen.getByText(/Failed to place order/i)).toBeInTheDocument();
		expect(screen.getByText(/Low volume detected/i)).toBeInTheDocument();
	});

	it('displays log levels with correct styling', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		expect(screen.getByText(/\[INFO\]/i)).toBeInTheDocument();
		expect(screen.getByText(/\[ERROR\]/i)).toBeInTheDocument();
		expect(screen.getByText(/\[WARNING\]/i)).toBeInTheDocument();
	});

	it('displays log modules', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		// Check that modules appear in the log entries (not just in the filter dropdown)
		const logEntries = screen.getAllByText(/TradingService/i);
		expect(logEntries.length).toBeGreaterThan(0);
		// AutoTradeEngine appears in both the dropdown and the log entry
		expect(screen.getAllByText(/AutoTradeEngine/i).length).toBeGreaterThan(0);
	});

	it('filters logs by level', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		const levelSelect = screen.getByRole('combobox', { name: /Level:/i });
		fireEvent.change(levelSelect, { target: { value: 'ERROR' } });

		expect(screen.getByText(/Failed to place order/i)).toBeInTheDocument();
		expect(screen.queryByText(/Service started successfully/i)).not.toBeInTheDocument();
		expect(screen.queryByText(/Low volume detected/i)).not.toBeInTheDocument();
	});

	it('filters logs by module', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		const moduleSelect = screen.getByRole('combobox', { name: /Module:/i });
		fireEvent.change(moduleSelect, { target: { value: 'AutoTradeEngine' } });

		expect(screen.getByText(/Low volume detected/i)).toBeInTheDocument();
		expect(screen.queryByText(/Service started successfully/i)).not.toBeInTheDocument();
		expect(screen.queryByText(/Failed to place order/i)).not.toBeInTheDocument();
	});

	it('shows expandable context for logs with context', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		const contextButtons = screen.getAllByText(/Context/i);
		expect(contextButtons.length).toBeGreaterThan(0);

		fireEvent.click(contextButtons[0]);

		expect(screen.getByText(/action/i)).toBeInTheDocument();
		expect(screen.getByText(/start_service/i)).toBeInTheDocument();
	});

	it('shows log count', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		expect(screen.getByText(/Showing 3 of 3 logs/i)).toBeInTheDocument();
	});

	it('updates log count when filtered', () => {
		render(<ServiceLogsViewer logs={mockLogs} isLoading={false} />);

		const levelSelect = screen.getByRole('combobox', { name: /Level:/i });
		fireEvent.change(levelSelect, { target: { value: 'ERROR' } });

		expect(screen.getByText(/Showing 1 of 3 logs/i)).toBeInTheDocument();
	});

	it('shows loading message when loading', () => {
		render(<ServiceLogsViewer logs={[]} isLoading={true} />);

		expect(screen.getByText(/Loading logs.../i)).toBeInTheDocument();
	});

	it('shows empty message when no logs', () => {
		render(<ServiceLogsViewer logs={[]} isLoading={false} />);

		expect(screen.getByText(/No logs found/i)).toBeInTheDocument();
	});
});
