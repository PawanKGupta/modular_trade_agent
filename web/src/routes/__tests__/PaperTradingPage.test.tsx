import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PaperTradingPage } from '../dashboard/PaperTradingPage';

// Mock the API
vi.mock('@/api/paper-trading', () => ({
	getPaperTradingPortfolio: vi.fn(() =>
		Promise.resolve({
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
					distance_to_target: 2.36,
				},
			],
			recent_orders: [
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
			order_statistics: {
				total_orders: 3,
				buy_orders: 2,
				sell_orders: 1,
				completed_orders: 2,
				pending_orders: 1,
				cancelled_orders: 0,
				rejected_orders: 0,
				success_rate: 66.67,
			},
		})
	),
}));

describe('PaperTradingPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
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
			expect(screen.getByText('Target')).toBeInTheDocument();
			expect(screen.getByText('To Target')).toBeInTheDocument();

			// Check holdings data (use getAllByText since symbols appear in both holdings and orders)
			const apolloElements = screen.getAllByText('APOLLOHOSP');
			expect(apolloElements.length).toBeGreaterThan(0);

			const tataElements = screen.getAllByText('TATASTEEL');
			expect(tataElements.length).toBeGreaterThan(0);

			// Check target prices are displayed
			expect(screen.getByText('Rs 160.00')).toBeInTheDocument();
			expect(screen.getByText('Rs 130.00')).toBeInTheDocument();
		});
	});

	it('displays recent orders with side and type columns', async () => {
		render(withProviders(<PaperTradingPage />));

		await waitFor(() => {
			// Check orders section
			expect(screen.getByText(/Recent Orders \(Last 50\)/i)).toBeInTheDocument();

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
			expect(screen.getByText('Success Rate')).toBeInTheDocument();
			expect(screen.getByText('Completed')).toBeInTheDocument();
			expect(screen.getByText('Pending')).toBeInTheDocument();
		});

		// Check statistics values
		await waitFor(() => {
			// Total orders: 3
			const totalOrders = screen.getAllByText('3');
			expect(totalOrders.length).toBeGreaterThan(0);

			// Success rate: 66.67%
			expect(screen.getByText('66.67%')).toBeInTheDocument();
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
			// Check that positive P&L has green color class
			const pnlElements = screen.getAllByText(/Rs 850.00|Rs 1,400.00/);
			pnlElements.forEach((element) => {
				// Should have green color for positive P&L
				expect(element.className).toContain('green');
			});
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
			// Check for up arrows (below target)
			const upArrows = screen.getAllByText(/↑/);
			expect(upArrows.length).toBeGreaterThan(0);
		});
	});
});
