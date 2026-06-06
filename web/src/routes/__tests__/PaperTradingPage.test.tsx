import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PaperTradingPage } from '../dashboard/PaperTradingPage';
import * as paperTradingApi from '@/api/paper-trading';

const portfolioMock = {
	account: {
		initial_capital: 100000,
		available_cash: 85000,
		total_pnl: 5000,
		realized_pnl: 2000,
		unrealized_pnl: 3000,
		portfolio_value: 20000,
		total_value: 105000,
		return_percentage: 5.0,
	},
	holdings: [
		{
			symbol: 'APOLLOHOSP',
			quantity: 100,
			average_price: 150.0,
			current_price: 158.5,
			cost_basis: 15000,
			market_value: 15850,
			pnl: 850,
			pnl_percentage: 5.67,
			target_price: 160.0,
			distance_to_target: 0.94,
			reentry_count: 1,
			entry_rsi: 28.5,
			reentries: [
				{ qty: 50, price: 145, level: 'L1', rsi: 25, time: '2024-11-20T09:00:00' },
			],
		},
		{
			symbol: 'TATASTEEL',
			quantity: 200,
			average_price: 120.0,
			current_price: 127.0,
			cost_basis: 24000,
			market_value: 25400,
			pnl: 1400,
			pnl_percentage: 5.83,
			target_price: 130.0,
			distance_to_target: -2.36,
		},
	],
	recent_orders: {
		items: [
			{
				order_id: 'ord_1',
				symbol: 'APOLLOHOSP',
				transaction_type: 'BUY',
				order_type: 'MARKET',
				quantity: 100,
				status: 'COMPLETE',
				execution_price: 150.0,
				created_at: '2024-11-26T09:00:00',
				executed_at: '2024-11-26T09:00:01',
				metadata: { entry_type: 'REENTRY', rsi_value: 28, rsi_level: 1 },
			},
			{
				order_id: 'ord_2',
				symbol: 'TATASTEEL',
				transaction_type: 'BUY',
				order_type: 'LIMIT',
				quantity: 200,
				status: 'COMPLETE',
				execution_price: 120.0,
				created_at: '2024-11-26T09:15:00',
				executed_at: '2024-11-26T09:30:00',
			},
			{
				order_id: 'ord_3',
				symbol: 'RELIANCE',
				transaction_type: 'SELL',
				order_type: 'MARKET',
				quantity: 50,
				status: 'PENDING',
				execution_price: null,
				created_at: '2024-11-26T10:00:00',
				executed_at: null,
			},
		],
		total: 25,
		total_pages: 3,
		page: 1,
		page_size: 10,
	},
	order_statistics: {
		total_orders: 3,
		buy_orders: 2,
		sell_orders: 1,
		completed_orders: 2,
		pending_orders: 1,
		cancelled_orders: 0,
		rejected_orders: 0,
		reentry_orders: 1,
		fill_rate: 100,
		sell_fill_rate: 100,
		trade_win_rate: 50,
		closed_positions: 2,
		winning_positions: 1,
		success_rate: 66.67,
	},
};

vi.mock('@/api/paper-trading', () => ({
	getPaperTradingPortfolio: vi.fn(),
	getPaperTradingHistory: vi.fn(() => Promise.resolve({
		transactions: [],
		closed_positions: [],
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
	})),
}));

describe('PaperTradingPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValue(portfolioMock);
	});

	it('renders page title and live indicator', async () => {
		render(withProviders(<PaperTradingPage />));

		// Check page title
		await waitFor(() => {
			expect(screen.getByText('Paper Trading Portfolio')).toBeInTheDocument();
		});

		// Check live indicator
		await waitFor(() => {
			expect(screen.getByText(/Live/i)).toBeInTheDocument();
			expect(screen.getByText(/Last update:/i)).toBeInTheDocument();
		});
	});

	it('displays account summary with all metrics', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText('Account Summary')).toBeInTheDocument();
			expect(screen.getByText('Initial Capital')).toBeInTheDocument();
			expect(screen.getByText('Available Cash')).toBeInTheDocument();
			expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
			expect(screen.getByText('Total Value')).toBeInTheDocument();
			expect(screen.getByText('Total P&L')).toBeInTheDocument();
			expect(screen.getByText('Realized P&L')).toBeInTheDocument();
			expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
		});

		// Check formatted values
		await waitFor(() => {
			expect(screen.getByText('Rs 1,00,000.00')).toBeInTheDocument();
			expect(screen.getByText('Rs 85,000.00')).toBeInTheDocument();
		});
	});

	it('displays holdings with target price and distance columns', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			// Check holdings section
			expect(screen.getByText(/Holdings \(2\)/i)).toBeInTheDocument();

			// Check table headers include new columns
			// Note: these columns are hidden on small screens
			expect(screen.getByRole('columnheader', { name: 'Target', hidden: true })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'To Target', hidden: true })).toBeInTheDocument();

			// Check holdings data (use getAllByText since symbols appear in both holdings and orders)
			const apolloElements = screen.getAllByText('APOLLOHOSP');
			expect(apolloElements.length).toBeGreaterThan(0);

			const tataElements = screen.getAllByText('TATASTEEL');
			expect(tataElements.length).toBeGreaterThan(0);

			// Check target prices are displayed (formatted with toLocaleString without Rs prefix)
			expect(screen.getByText('160.00')).toBeInTheDocument();
			expect(screen.getByText('130.00')).toBeInTheDocument();
		});
	});

	it('displays recent orders with side and type columns', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			// Check orders section
			expect(screen.getByText(/Recent Orders \(25\)/i)).toBeInTheDocument();

			// Check table headers include both Side and Type columns
			expect(screen.getByText('Side')).toBeInTheDocument();
			const typeHeaders = screen.getAllByText('Type');
			expect(typeHeaders.length).toBeGreaterThan(0);

			// Check order data - transaction types (BUY/SELL)
			const buyTags = screen.getAllByText('BUY');
			expect(buyTags.length).toBe(2); // 2 buy orders

			const sellTags = screen.getAllByText('SELL');
			expect(sellTags.length).toBe(1); // 1 sell order

			// Check order types (MARKET/LIMIT)
			const marketTags = screen.getAllByText('MARKET');
			expect(marketTags.length).toBe(2); // 2 market orders

			const limitTags = screen.getAllByText('LIMIT');
			expect(limitTags.length).toBe(1); // 1 limit order
		});
	});

	it('displays order statistics', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText('Order Statistics')).toBeInTheDocument();
			expect(screen.getByText('Total Orders')).toBeInTheDocument();
			expect(screen.getByText('Buy Orders')).toBeInTheDocument();
			expect(screen.getByText('Sell Orders')).toBeInTheDocument();
			expect(screen.getByText('Fill Rate')).toBeInTheDocument();
			expect(screen.getByText('Trade Win Rate')).toBeInTheDocument();
			expect(screen.getByText('Sell Fill Rate')).toBeInTheDocument();
			expect(screen.getByText('Completed')).toBeInTheDocument();
			expect(screen.getByText('Pending')).toBeInTheDocument();
		});

		// Check statistics values (match mock order_statistics)
		await waitFor(() => {
			const totalOrdersCell = screen.getByText('Total Orders').parentElement;
			expect(totalOrdersCell?.children[1]).toHaveTextContent('3');

			const buyOrdersCell = screen.getByText('Buy Orders').parentElement;
			expect(buyOrdersCell?.children[1]).toHaveTextContent('2');

			const sellOrdersCell = screen.getByText('Sell Orders').parentElement;
			expect(sellOrdersCell?.children[1]).toHaveTextContent('1');

			const fillRateCell = screen.getByText('Fill Rate').parentElement;
			expect(fillRateCell?.children[1]).toHaveTextContent('100.00%');

			const tradeWinCell = screen.getByText('Trade Win Rate').parentElement;
			expect(tradeWinCell?.children[1]).toHaveTextContent('50.00%');

			const sellFillCell = screen.getByText('Sell Fill Rate').parentElement;
			expect(sellFillCell?.children[1]).toHaveTextContent('100.00%');
		});
	});

	it('shows loading state initially', () => {
		render(withProviders(<PaperTradingPage />));
		expect(screen.getByText('Loading portfolio...')).toBeInTheDocument();
	});

	it('shows refresh button', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			const refreshButton = screen.getByRole('button', { name: /Refresh/i });
			expect(refreshButton).toBeInTheDocument();
		});
	});

	it('applies correct color coding to P&L values', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			// P&L values in holdings table use toLocaleString('en-IN') which formats with commas
			// Check that positive P&L has green color class
			// Values are formatted as "850.00" and "1,400.00" (no Rs prefix)
			const pnl850 = screen.getByText('850.00');
			const pnl1400 = screen.getByText('1,400.00');

			// Should have green color class for positive P&L
			expect(pnl850.closest('td')?.className).toContain('green');
			expect(pnl1400.closest('td')?.className).toContain('green');
		});
	});

	it('shows order status badges with appropriate colors', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			const completeStatus = screen.getAllByText('COMPLETE');
			expect(completeStatus.length).toBeGreaterThan(0);

			const pendingStatus = screen.getAllByText('PENDING');
			expect(pendingStatus.length).toBeGreaterThan(0);
		});
	});

	it('shows distance to target with arrows', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			const upArrows = screen.getAllByText(/↑/);
			expect(upArrows.length).toBeGreaterThan(0);
			expect(screen.getAllByText(/✓/).length).toBeGreaterThan(0);
		});
	});

	it('shows re-entry details in holdings and orders', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText(/1 re-entry/i)).toBeInTheDocument();
			expect(screen.getByText(/Entry RSI: 28.5/i)).toBeInTheDocument();
			expect(screen.getAllByText('Re-entry').length).toBeGreaterThan(0);
		});

		fireEvent.click(screen.getByText('View details'));
		expect(screen.getByText(/Re-entry 1:/i)).toBeInTheDocument();
	});

	it('paginates recent orders and changes page size', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText(/Recent Orders \(25\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Showing 1 to 10 of 25 orders/i)).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingPortfolio).toHaveBeenCalledWith(
				expect.objectContaining({ page: 2, page_size: 10 })
			);
		});

		await waitFor(() => {
			expect(screen.getByText(/Recent Orders \(25\)/i)).toBeInTheDocument();
		});

		const pageSizeSelect = screen.getAllByRole('combobox')[0];
		fireEvent.change(pageSizeSelect, { target: { value: '25' } });
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingPortfolio).toHaveBeenCalledWith(
				expect.objectContaining({ page: 1, page_size: 25 })
			);
		});
	});

	it('shows error state with retry', async () => {
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockRejectedValue(new Error('network'));
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText(/Error loading portfolio/i)).toBeInTheDocument();
		});

		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValue(portfolioMock);
		fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
		await waitFor(() => {
			expect(screen.getByText('Paper Trading Portfolio')).toBeInTheDocument();
		});
	});

	it('shows empty portfolio message when data is null', async () => {
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValue(null as never);
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText(/No portfolio data available/i)).toBeInTheDocument();
		});
	});

	it('shows empty holdings state', async () => {
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValue({
			...portfolioMock,
			holdings: [],
		});
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			expect(screen.getByText('No holdings')).toBeInTheDocument();
		});
	});

	it('refreshes portfolio on button click', async () => {
		render(withProviders(<PaperTradingPage />));
		await waitFor(() => expect(screen.getByText('Paper Trading Portfolio')).toBeInTheDocument());

		const initialCalls = vi.mocked(paperTradingApi.getPaperTradingPortfolio).mock.calls.length;
		fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingPortfolio.mock.calls.length).toBeGreaterThan(initialCalls);
		});
	});

	it('jumps to last page of recent orders when many pages exist', async () => {
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockImplementation(async (params) => ({
			...portfolioMock,
			recent_orders: {
				items: [{ ...portfolioMock.recent_orders.items[0], order_id: `p${params?.page ?? 1}` }],
				total: 60,
				total_pages: 6,
				page: params?.page ?? 1,
				page_size: params?.page_size ?? 10,
			},
		}));

		render(withProviders(<PaperTradingPage />));
		await waitFor(() => expect(screen.getByText(/Recent Orders \(60\)/i)).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Last' }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingPortfolio).toHaveBeenCalledWith(
				expect.objectContaining({ page: 6 })
			);
			expect(screen.getByText(/Showing 51 to 60 of 60/i)).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: '4' }));
		await waitFor(() => {
			expect(paperTradingApi.getPaperTradingPortfolio).toHaveBeenCalledWith(
				expect.objectContaining({ page: 4 })
			);
		});
	});
});
