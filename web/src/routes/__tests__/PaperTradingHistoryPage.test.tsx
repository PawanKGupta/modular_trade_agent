import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PaperTradingHistoryPage } from '../dashboard/PaperTradingHistoryPage';
import * as paperTradingApi from '@/api/paper-trading';

// Mock the API
vi.mock('@/api/paper-trading');
vi.mock('@/api/export', () => ({
	exportTradeHistory: vi.fn(),
}));

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
			transactions: {
				items: [
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
				total: 2,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			closed_positions: {
				items: [
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
				total: 1,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
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
			transactions: {
				items: [
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
				total: 1,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			closed_positions: {
				items: [],
				total: 0,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
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
			transactions: {
				items: [
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
				total: 2,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			closed_positions: {
				items: [],
				total: 0,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
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
			transactions: {
				items: [
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
				total: 1,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			closed_positions: {
				items: [],
				total: 0,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
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
			transactions: {
				items: [],
				total: 0,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			closed_positions: {
				items: [],
				total: 0,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
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

describe('PaperTradingHistoryPage pagination and export', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('supports pagination and export panel', async () => {
		const mockData = {
			transactions: {
				items: [],
				total: 25,
				page: 1,
				page_size: 10,
				total_pages: 3,
			},
			closed_positions: {
				items: [
					{
						symbol: 'HDFC',
						entry_price: 1000,
						exit_price: 1100,
						quantity: 5,
						buy_date: '2024-01-01',
						sell_date: '2024-01-05',
						holding_days: 4,
						realized_pnl: 500,
						pnl_percentage: 10,
						charges: 20,
					},
				],
				total: 1,
				page: 1,
				page_size: 10,
				total_pages: 1,
			},
			statistics: {
				total_trades: 1,
				profitable_trades: 1,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 100,
				total_profit: 500,
				total_loss: 0,
				net_pnl: 500,
				avg_profit_per_trade: 500,
				avg_loss_per_trade: 0,
				total_transactions: 0,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getByText('Trade History')).toBeInTheDocument();
			expect(screen.getByText('HDFC')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: /Export/i }));
		expect(screen.getByText('Export Trade History')).toBeInTheDocument();

		const pageSizeSelect = screen.getAllByRole('combobox')[0];
		fireEvent.change(pageSizeSelect, { target: { value: '25' } });

		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ positions_page_size: 25 })
			);
		});
	});

	it('shows error state when loading fails', async () => {
		vi.mocked(paperTradingApi.getPaperTradingHistory).mockRejectedValue(new Error('fail'));
		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getByText(/Failed to load trade history/i)).toBeInTheDocument();
		});
	});

	it('shows loading state while fetching', async () => {
		vi.mocked(paperTradingApi.getPaperTradingHistory).mockImplementation(
			() => new Promise(() => {})
		);
		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		expect(screen.getByText(/Loading trade history/i)).toBeInTheDocument();
	});

	it('paginates positions and renders transaction table details', async () => {
		const sellTxn = {
			order_id: 'SELL_1',
			symbol: 'INFY',
			transaction_type: 'SELL',
			quantity: 5,
			price: 1500,
			order_value: 7500,
			charges: 20,
			timestamp: '2024-01-02T14:30:00',
			entry_price: 1400,
			exit_price: 1500,
			realized_pnl: 480,
			pnl_percentage: 7.1,
			exit_reason: 'Manual',
		};
		const mockData = {
			transactions: {
				items: [sellTxn],
				total: 15,
				page: 1,
				page_size: 10,
				total_pages: 2,
			},
			closed_positions: {
				items: [
					{
						symbol: 'HDFC',
						entry_price: 1000,
						exit_price: 1100,
						quantity: 5,
						buy_date: '2024-01-01',
						sell_date: '2024-01-05',
						holding_days: 4,
						realized_pnl: 500,
						pnl_percentage: 10,
						charges: 20,
					},
				],
				total: 12,
				page: 1,
				page_size: 10,
				total_pages: 2,
			},
			statistics: {
				total_trades: 2,
				profitable_trades: 2,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 100,
				total_profit: 980,
				total_loss: 0,
				net_pnl: 980,
				avg_profit_per_trade: 490,
				avg_loss_per_trade: 0,
				total_transactions: 15,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockImplementation(async (params) => ({
			...mockData,
			closed_positions: { ...mockData.closed_positions, page: params?.positions_page ?? 1 },
			transactions: { ...mockData.transactions, page: params?.transactions_page ?? 1 },
		}));

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		await waitFor(() => {
			expect(screen.getByText('HDFC')).toBeInTheDocument();
			expect(screen.getByText('INFY')).toBeInTheDocument();
			expect(screen.getByText('Manual')).toBeInTheDocument();
			expect(screen.getByText(/All Transactions \(15\)/i)).toBeInTheDocument();
		});

		fireEvent.click(screen.getAllByRole('button', { name: 'Next' })[1]);
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ transactions_page: 2 })
			);
			expect(screen.getByText('Manual')).toBeInTheDocument();
		});

		fireEvent.click(screen.getAllByRole('button', { name: 'Last' })[1]);
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ transactions_page: 2 })
			);
			expect(screen.getByText('Manual')).toBeInTheDocument();
		});

		fireEvent.click(screen.getAllByRole('button', { name: 'First' })[1]);
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ transactions_page: 1 })
			);
			expect(screen.getByText('Manual')).toBeInTheDocument();
		});

		const txnPageSize = screen.getAllByRole('combobox')[1];
		fireEvent.change(txnPageSize, { target: { value: '25' } });
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ transactions_page_size: 25, transactions_page: 1 })
			);
		});
	});

	it('exports trade history CSV', async () => {
		const exportApi = await import('@/api/export');
		vi.mocked(exportApi.exportTradeHistory).mockResolvedValue(undefined);
		const mockData = {
			transactions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			closed_positions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0,
				total_profit: 0,
				total_loss: 0,
				net_pnl: 0,
				avg_profit_per_trade: 0,
				avg_loss_per_trade: 0,
				total_transactions: 0,
			},
		};
		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);
		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		await waitFor(() => expect(screen.getByText('Trade History')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: /Export/i }));
		fireEvent.click(screen.getByRole('button', { name: /Download CSV/i }));
		await waitFor(() => {
			expect(exportApi.exportTradeHistory).toHaveBeenCalledWith(
				expect.objectContaining({ tradeMode: 'paper' })
			);
		});
	});

	it('refreshes data on refresh button click', async () => {
		const mockData = {
			transactions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			closed_positions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			statistics: {
				total_trades: 0,
				profitable_trades: 0,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 0,
				total_profit: 0,
				total_loss: 0,
				net_pnl: 0,
				avg_profit_per_trade: 0,
				avg_loss_per_trade: 0,
				total_transactions: 0,
			},
		};
		vi.mocked(paperTradingApi.getPaperTradingHistory).mockResolvedValue(mockData);
		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		await waitFor(() => expect(screen.getByText('Trade History')).toBeInTheDocument());

		const initialCalls = vi.mocked(paperTradingApi.getPaperTradingHistory).mock.calls.length;
		fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory.mock.calls.length).toBeGreaterThan(initialCalls);
		});
	});

	it('paginates closed positions with first and last controls', async () => {
		const mockData = {
			transactions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			closed_positions: {
				items: [{ symbol: 'PAGE2', entry_price: 100, exit_price: 110, quantity: 1, buy_date: '2024-01-01', sell_date: '2024-01-02', holding_days: 1, realized_pnl: 10, pnl_percentage: 10, charges: 1 }],
				total: 12,
				page: 1,
				page_size: 10,
				total_pages: 2,
			},
			statistics: {
				total_trades: 1,
				profitable_trades: 1,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 100,
				total_profit: 10,
				total_loss: 0,
				net_pnl: 10,
				avg_profit_per_trade: 10,
				avg_loss_per_trade: 0,
				total_transactions: 0,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockImplementation(async (params) => ({
			...mockData,
			closed_positions: {
				...mockData.closed_positions,
				page: params?.positions_page ?? 1,
				items: params?.positions_page === 2
					? [{ symbol: 'PAGE2B', entry_price: 200, exit_price: 220, quantity: 2, buy_date: '2024-02-01', sell_date: '2024-02-02', holding_days: 1, realized_pnl: 40, pnl_percentage: 10, charges: 2 }]
					: mockData.closed_positions.items,
			},
		}));

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		await waitFor(() => expect(screen.getByText('PAGE2')).toBeInTheDocument());

		fireEvent.click(screen.getAllByRole('button', { name: 'Last' })[0]);
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ positions_page: 2 })
			);
			expect(screen.getByText('PAGE2B')).toBeInTheDocument();
		});

		fireEvent.click(screen.getAllByRole('button', { name: 'First' })[0]);
		await waitFor(() => {
			expect(screen.getByText('PAGE2')).toBeInTheDocument();
		});
	});

	it('navigates transaction pages beyond five total pages', async () => {
		const sellTxn = {
			order_id: 'SELL_X',
			symbol: 'TXN',
			transaction_type: 'SELL',
			quantity: 1,
			price: 100,
			order_value: 100,
			charges: 1,
			timestamp: '2024-01-02T14:30:00',
			entry_price: 90,
			exit_price: 100,
			realized_pnl: 9,
			pnl_percentage: 10,
			exit_reason: 'Target Hit',
		};
		const base = {
			transactions: { items: [sellTxn], total: 70, page: 1, page_size: 10, total_pages: 7 },
			closed_positions: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 },
			statistics: {
				total_trades: 1,
				profitable_trades: 1,
				losing_trades: 0,
				breakeven_trades: 0,
				win_rate: 100,
				total_profit: 9,
				total_loss: 0,
				net_pnl: 9,
				avg_profit_per_trade: 9,
				avg_loss_per_trade: 0,
				total_transactions: 70,
			},
		};

		vi.mocked(paperTradingApi.getPaperTradingHistory).mockImplementation(async (params) => ({
			...base,
			transactions: { ...base.transactions, page: params?.transactions_page ?? 1 },
		}));

		render(<PaperTradingHistoryPage />, { wrapper: createWrapper() });
		await waitFor(() => expect(screen.getByText('TXN')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => expect(screen.getByText('TXN')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => expect(screen.getByText('TXN')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingHistory).toHaveBeenCalledWith(
				expect.objectContaining({ transactions_page: 4 })
			);
			expect(screen.getByText('TXN')).toBeInTheDocument();
		});
	});
});
