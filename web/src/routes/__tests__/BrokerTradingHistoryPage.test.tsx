import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { BrokerTradingHistoryPage } from '../dashboard/BrokerTradingHistoryPage';
import * as brokerApi from '@/api/broker';
import * as exportApi from '@/api/export';

vi.mock('@/api/broker', () => ({
	getBrokerHistory: vi.fn(),
}));

vi.mock('@/api/export', () => ({
	exportTradeHistory: vi.fn(),
}));

const mockHistory = {
	statistics: { total_trades: 5, closed_positions: 2, win_rate: 60 },
	closed_positions: [
		{
			id: 1,
			symbol: 'RELIANCE',
			quantity: 10,
			avg_price: 2500,
			exit_price: 2600,
			realized_pnl: 1000,
		},
	],
	transactions: [
		{
			id: 1,
			symbol: 'INFY',
			side: 'buy' as const,
			quantity: 5,
			execution_price: 1400,
			placed_at: '2025-01-01T10:00:00',
		},
		{
			id: 2,
			symbol: 'TCS',
			side: 'sell' as const,
			quantity: 3,
			execution_price: null,
			placed_at: null,
		},
	],
};

describe('BrokerTradingHistoryPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(brokerApi.getBrokerHistory).mockResolvedValue(mockHistory);
		vi.mocked(exportApi.exportTradeHistory).mockResolvedValue(undefined);
	});

	it('renders statistics and tables', async () => {
		render(withProviders(<BrokerTradingHistoryPage />));

		await waitFor(() => {
			expect(screen.getByText('Broker Trading History')).toBeInTheDocument();
			expect(screen.getByText(/Total Trades: 5/)).toBeInTheDocument();
			expect(screen.getByText('RELIANCE')).toBeInTheDocument();
			expect(screen.getByText('INFY')).toBeInTheDocument();
			expect(screen.getByText('TCS')).toBeInTheDocument();
		});
	});

	it('shows error state when query fails', async () => {
		vi.mocked(brokerApi.getBrokerHistory).mockRejectedValue(new Error('fail'));
		render(withProviders(<BrokerTradingHistoryPage />));

		await waitFor(() => {
			expect(screen.getByText(/Failed to load broker history/i)).toBeInTheDocument();
		});
	});

	it('toggles export panel and refreshes data', async () => {
		render(withProviders(<BrokerTradingHistoryPage />));

		await waitFor(() => expect(screen.getByText('RELIANCE')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: /Export/i }));
		expect(screen.getByText('Export Trade History')).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
		expect(brokerApi.getBrokerHistory).toHaveBeenCalledTimes(2);
	});

	it('shows empty states for no positions or transactions', async () => {
		vi.mocked(brokerApi.getBrokerHistory).mockResolvedValue({
			statistics: { total_trades: 0, closed_positions: 0, win_rate: 0 },
			closed_positions: [],
			transactions: [],
		});
		render(withProviders(<BrokerTradingHistoryPage />));

		await waitFor(() => {
			expect(screen.getByText('No closed positions')).toBeInTheDocument();
			expect(screen.getByText('No transactions')).toBeInTheDocument();
		});
	});
});
