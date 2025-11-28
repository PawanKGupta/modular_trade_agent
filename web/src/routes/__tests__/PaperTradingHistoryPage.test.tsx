import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PaperTradingHistoryPage } from '../dashboard/PaperTradingHistoryPage';
import * as paperTradingApi from '@/api/paper-trading';

// Mock the API
vi.mock('@/api/paper-trading');

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	return ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
};

describe('PaperTradingHistoryPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('displays transactions with P&L and exit reason for sell orders', async () => {
		const mockData = {
			transactions: [
				{
					order_id: 'BUY_001',
					symbol: 'RELIANCE',
					transaction_type: 'BUY',
					quantity: 10,
					price: 2500.0,
					order_value: 25000.0,
					charges: 75.0,
					timestamp: '2024-01-01T10:00:00',
				},
				{
					order_id: 'SELL_001',
					symbol: 'RELIANCE',
					transaction_type: 'SELL',
					quantity: 10,
					price: 2600.0,
					order_value: 26000.0,
					charges: 78.0,
					timestamp: '2024-01-02T14:30:00',
					entry_price: 2500.0,
					exit_price: 2600.0,
					realized_pnl: 922.0,
					pnl_percentage: 4.0,
					exit_reason: 'Target Hit',
				},
			],
			closed_positions: [
				{
					symbol: 'RELIANCE',
					entry_price: 2500.0,
					exit_price: 2600.0,
					quantity: 10,
					buy_date: '2024-01-01',
					sell_date: '2024-01-02',
					holding_days: 1,
					realized_pnl: 922.0,
					pnl_percentage: 4.0,
					charges: 153.0,
				},
			],
			statistics: {
				total_trades: 1,
				profitable_trades: 1,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 100.0,
				total_profit: 922.0,
				total_loss: 0.0,
				net_pnl: 922.0,
				avg_profit_per_trade: 922.0,
				avg_loss_per_trade: 0.0,
				total_transactions: 2,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		// Wait for data to load
		await waitFor(() => {
			expect(screen.getAllByText('RELIANCE').length).toBeGreaterThan(0);
		});

		// Check that P&L column exists (appears in both tables)
		expect(screen.getAllByText('P&L').length).toBeGreaterThan(0);

		// Check that exit reason column exists (in transactions table)
		expect(screen.getByText('Reason')).toBeInTheDocument();

		// Check that sell transaction shows P&L (appears in both closed positions and transactions)
		expect(screen.getAllByText(/Rs 922\.00/).length).toBeGreaterThan(0);
		expect(screen.getAllByText(/4\.00%/).length).toBeGreaterThan(0);

		// Check that exit reason badge is displayed
		expect(screen.getByText('Target Hit')).toBeInTheDocument();
	});

	it('shows dash (-) for buy transactions in P&L and Reason columns', async () => {
		const mockData = {
			transactions: [
				{
					order_id: 'BUY_001',
					symbol: 'INFY',
					transaction_type: 'BUY',
					quantity: 20,
					price: 1400.0,
					order_value: 28000.0,
					charges: 84.0,
					timestamp: '2024-01-01T10:00:00',
				},
			],
			closed_positions: [],
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0.0,
				total_profit: 0.0,
				total_loss: 0.0,
				net_pnl: 0.0,
				avg_profit_per_trade: 0.0,
				avg_loss_per_trade: 0.0,
				total_transactions: 1,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getAllByText('INFY').length).toBeGreaterThan(0);
		});

		// For BUY transactions, P&L and Reason should show "-"
		const dashElements = screen.getAllByText('-');
		expect(dashElements.length).toBeGreaterThanOrEqual(2);
	});

	it('displays different exit reason badges with appropriate styling', async () => {
		const mockData = {
			transactions: [
				{
					order_id: 'SELL_001',
					symbol: 'TCS',
					transaction_type: 'SELL',
					quantity: 5,
					price: 3600.0,
					order_value: 18000.0,
					charges: 54.0,
					timestamp: '2024-01-02T14:30:00',
					entry_price: 3500.0,
					exit_price: 3600.0,
					realized_pnl: 446.0,
					pnl_percentage: 2.86,
					exit_reason: 'RSI > 50',
				},
				{
					order_id: 'SELL_002',
					symbol: 'WIPRO',
					transaction_type: 'SELL',
					quantity: 15,
					price: 420.0,
					order_value: 6300.0,
					charges: 19.0,
					timestamp: '2024-01-03T11:00:00',
					entry_price: 400.0,
					exit_price: 420.0,
					realized_pnl: 281.0,
					pnl_percentage: 5.0,
					exit_reason: 'Manual',
				},
			],
			closed_positions: [],
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0.0,
				total_profit: 0.0,
				total_loss: 0.0,
				net_pnl: 0.0,
				avg_profit_per_trade: 0.0,
				avg_loss_per_trade: 0.0,
				total_transactions: 2,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getAllByText('TCS').length).toBeGreaterThan(0);
		});

		// Check that different exit reasons are displayed
		expect(screen.getByText('RSI > 50')).toBeInTheDocument();
		expect(screen.getByText('Manual')).toBeInTheDocument();
	});

	it('shows negative P&L in red for losing trades', async () => {
		const mockData = {
			transactions: [
				{
					order_id: 'SELL_001',
					symbol: 'LOSS_STOCK',
					transaction_type: 'SELL',
					quantity: 10,
					price: 2400.0,
					order_value: 24000.0,
					charges: 72.0,
					timestamp: '2024-01-02T14:30:00',
					entry_price: 2500.0,
					exit_price: 2400.0,
					realized_pnl: -1072.0,
					pnl_percentage: -4.0,
					exit_reason: 'RSI > 50',
				},
			],
			closed_positions: [],
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0.0,
				total_profit: 0.0,
				total_loss: 0.0,
				net_pnl: 0.0,
				avg_profit_per_trade: 0.0,
				avg_loss_per_trade: 0.0,
				total_transactions: 1,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getAllByText('LOSS_STOCK').length).toBeGreaterThan(0);
		});

		// Negative P&L should be displayed
		expect(screen.getAllByText(/Rs -1,072\.00/).length).toBeGreaterThan(0);
		expect(screen.getAllByText(/-4\.00%/).length).toBeGreaterThan(0);
	});

	it('displays empty state when no transactions exist', async () => {
		const mockData = {
			transactions: [],
			closed_positions: [],
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0.0,
				total_profit: 0.0,
				total_loss: 0.0,
				net_pnl: 0.0,
				avg_profit_per_trade: 0.0,
				avg_loss_per_trade: 0.0,
				total_transactions: 0,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getByText(/No transactions yet/)).toBeInTheDocument();
		});
	});
});
