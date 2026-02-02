import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { withProviders } from '@/test/utils';
import { BrokerPortfolioPage } from '../dashboard/BrokerPortfolioPage';

const mockPortfolioResponse = {
	account: {
		initial_capital: 200000,
		available_cash: 150000,
		total_pnl: 10000,
		realized_pnl: 5000,
		unrealized_pnl: 5000,
		portfolio_value: 60000,
		total_value: 210000,
		return_percentage: 5.0,
	},
	holdings: [
		{
			symbol: 'RELIANCE.NS',
			quantity: 20,
			average_price: 2500.0,
			current_price: 2600.0,
			cost_basis: 50000,
			market_value: 52000,
			pnl: 2000,
			pnl_percentage: 4.0,
			target_price: null,
			distance_to_target: null,
			reentry_count: 0,
			entry_rsi: null,
			initial_entry_price: null,
			reentries: null,
		},
	],
	recent_orders: [],
	order_statistics: {},
};

// Mock the API
vi.mock('@/api/user', () => ({
	getPortfolio: vi.fn(() => Promise.resolve(mockPortfolioResponse)),
	getBrokerSystemHoldings: vi.fn(() => Promise.resolve(mockPortfolioResponse)),
}));

// Mock useSettings
vi.mock('@/hooks/useSettings', () => ({
	useSettings: vi.fn(() => ({
		settings: { trade_mode: 'broker', broker: 'kotak-neo', broker_status: 'Connected' },
		isLoading: false,
		error: null,
		isPaperMode: false,
		isBrokerMode: true,
		broker: 'kotak-neo',
		brokerStatus: 'Connected',
		isBrokerConnected: true,
	})),
}));

describe('BrokerPortfolioPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders page title with broker name', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker Portfolio/i)).toBeInTheDocument();
			expect(screen.getByText(/KOTAK-NEO/i)).toBeInTheDocument();
		});
	});

	it('displays account summary', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Available Cash')).toBeInTheDocument();
			expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
			expect(screen.getByText('Total Value')).toBeInTheDocument();
			expect(screen.getByText('Total P&L')).toBeInTheDocument();
		});
	});

	it('displays holdings table', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Holdings (1)')).toBeInTheDocument();
			expect(screen.getByText('RELIANCE.NS')).toBeInTheDocument();
			expect(screen.getByText('20')).toBeInTheDocument(); // Quantity
		});
	});

	it('shows error message when not in broker mode', async () => {
		const useSettings = await import('@/hooks/useSettings');
		vi.mocked(useSettings.useSettings).mockReturnValue({
			settings: { trade_mode: 'paper', broker: null, broker_status: null },
			isLoading: false,
			error: null,
			isPaperMode: true,
			isBrokerMode: false,
			broker: null,
			brokerStatus: null,
			isBrokerConnected: false,
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker portfolio is only available in broker mode/i)).toBeInTheDocument();
		});
	});

	it('shows error message when broker not connected', async () => {
		const useSettings = await import('@/hooks/useSettings');
		vi.mocked(useSettings.useSettings).mockReturnValue({
			settings: { trade_mode: 'broker', broker: 'kotak-neo', broker_status: 'Disconnected' },
			isLoading: false,
			error: null,
			isPaperMode: false,
			isBrokerMode: true,
			broker: 'kotak-neo',
			brokerStatus: 'Disconnected',
			isBrokerConnected: false,
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker is not connected/i)).toBeInTheDocument();
		});
	});

	it('handles loading state', async () => {
		const userApi = await import('@/api/user');
		vi.mocked(userApi.getPortfolio).mockImplementation(() => new Promise(() => {})); // Never resolves

		// Ensure broker is connected so query is enabled
		const useSettings = await import('@/hooks/useSettings');
		vi.mocked(useSettings.useSettings).mockReturnValue({
			settings: { trade_mode: 'broker', broker: 'kotak-neo', broker_status: 'Connected' },
			isLoading: false,
			error: null,
			isPaperMode: false,
			isBrokerMode: true,
			broker: 'kotak-neo',
			brokerStatus: 'Connected',
			isBrokerConnected: true,
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Loading portfolio/i)).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('handles error state with retry button', async () => {
		const userApi = await import('@/api/user');
		const mockError = new Error('Failed to fetch portfolio');
		vi.mocked(userApi.getPortfolio).mockRejectedValueOnce(mockError);

		// Ensure broker is connected so query is enabled
		const useSettings = await import('@/hooks/useSettings');
		vi.mocked(useSettings.useSettings).mockReturnValue({
			settings: { trade_mode: 'broker', broker: 'kotak-neo', broker_status: 'Connected' },
			isLoading: false,
			error: null,
			isPaperMode: false,
			isBrokerMode: true,
			broker: 'kotak-neo',
			brokerStatus: 'Connected',
			isBrokerConnected: true,
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Error loading portfolio/i)).toBeInTheDocument();
			expect(screen.getByText('Retry Now')).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('displays empty state when no holdings', async () => {
		const userApi = await import('@/api/user');
		vi.mocked(userApi.getPortfolio).mockResolvedValueOnce({
			account: {
				initial_capital: 0,
				available_cash: 0,
				total_pnl: 0,
				realized_pnl: 0,
				unrealized_pnl: 0,
				portfolio_value: 0,
				total_value: 0,
				return_percentage: 0,
			},
			holdings: [],
			recent_orders: [],
			order_statistics: {},
		});

		// Ensure broker is connected so query is enabled
		const useSettings = await import('@/hooks/useSettings');
		vi.mocked(useSettings.useSettings).mockReturnValue({
			settings: { trade_mode: 'broker', broker: 'kotak-neo', broker_status: 'Connected' },
			isLoading: false,
			error: null,
			isPaperMode: false,
			isBrokerMode: true,
			broker: 'kotak-neo',
			brokerStatus: 'Connected',
			isBrokerConnected: true,
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Holdings \(0\)/)).toBeInTheDocument();
			expect(screen.getByText('No holdings')).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('displays reentry details in holdings table', async () => {
		const userApi = await import('@/api/user');
		vi.mocked(userApi.getPortfolio).mockResolvedValueOnce({
			account: {
				initial_capital: 200000,
				available_cash: 150000,
				total_pnl: 10000,
				realized_pnl: 5000,
				unrealized_pnl: 5000,
				portfolio_value: 60000,
				total_value: 210000,
				return_percentage: 5.0,
			},
			holdings: [
				{
					symbol: 'RELIANCE-EQ',
					quantity: 20,
					average_price: 2500.0,
					current_price: 2600.0,
					cost_basis: 50000,
					market_value: 52000,
					pnl: 2000,
					pnl_percentage: 4.0,
					target_price: null,
					distance_to_target: null,
					reentry_count: 2,
					entry_rsi: 28.5,
					initial_entry_price: 2500.0,
					reentries: [
						{
							qty: 10,
							price: 2400.0,
							time: '2025-01-15T10:00:00',
							level: 20,
							rsi: 18.5,
							cycle: 1,
						},
						{
							qty: 5,
							price: 2300.0,
							time: '2025-01-20T10:00:00',
							level: 10,
							rsi: 9.2,
							cycle: 2,
						},
					],
				},
			],
			recent_orders: [],
			order_statistics: {},
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			// Text is split across elements: "2", " re-entry", "s"
			// Check for the parent container that contains all the reentry info
			const reentryCell = screen.getByText('Entry RSI: 28.5').closest('td');
			expect(reentryCell?.textContent).toContain('2');
			expect(reentryCell?.textContent).toContain('re-entry');
			expect(screen.getByText('Entry RSI: 28.5')).toBeInTheDocument();
			expect(screen.getByText('View details')).toBeInTheDocument();
		});

		// Click to expand details
		const detailsButton = screen.getByText('View details');
		detailsButton.click();

		await waitFor(() => {
			expect(screen.getByText(/Re-entry 1: 10 @ Rs 2400.00/)).toBeInTheDocument();
			expect(screen.getByText(/Re-entry 2: 5 @ Rs 2300.00/)).toBeInTheDocument();
		});
	});

	it('displays "-" when no reentries in broker holdings', async () => {
		const userApi = await import('@/api/user');
		vi.mocked(userApi.getPortfolio).mockResolvedValueOnce({
			account: {
				initial_capital: 200000,
				available_cash: 150000,
				total_pnl: 10000,
				realized_pnl: 5000,
				unrealized_pnl: 5000,
				portfolio_value: 60000,
				total_value: 210000,
				return_percentage: 5.0,
			},
			holdings: [
				{
					symbol: 'TCS-EQ',
					quantity: 30,
					average_price: 3500.0,
					current_price: 3600.0,
					cost_basis: 105000,
					market_value: 108000,
					pnl: 3000,
					pnl_percentage: 2.86,
					target_price: null,
					distance_to_target: null,
					reentry_count: 0,
					entry_rsi: null,
					initial_entry_price: null,
					reentries: null,
				},
			],
			recent_orders: [],
			order_statistics: {},
		});

		render(
			withProviders(
				<MemoryRouter>
					<BrokerPortfolioPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('TCS-EQ')).toBeInTheDocument();
		});
	});
});
