import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { withProviders } from '@/test/utils';
import { BrokerOrdersPage } from '../dashboard/BrokerOrdersPage';

// Mock the API
vi.mock('@/api/user', () => ({
	getBrokerOrders: vi.fn(() =>
		Promise.resolve([
			{
				broker_order_id: 'ORDER123',
				symbol: 'RELIANCE.NS',
				side: 'buy',
				quantity: 10,
				price: 2500.0,
				status: 'pending',
				created_at: '2024-12-03T10:00:00Z',
				execution_price: null,
				execution_qty: null,
			},
			{
				broker_order_id: 'ORDER456',
				symbol: 'TCS.NS',
				side: 'sell',
				quantity: 5,
				price: 3500.0,
				status: 'closed',
				created_at: '2024-12-03T09:00:00Z',
				execution_price: 3500.0,
				execution_qty: 5,
			},
		])
	),
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

describe('BrokerOrdersPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders page title with broker name', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker Orders/i)).toBeInTheDocument();
			expect(screen.getByText(/KOTAK-NEO/i)).toBeInTheDocument();
		});
	});

	it('displays orders table', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('RELIANCE.NS')).toBeInTheDocument();
			expect(screen.getByText('TCS.NS')).toBeInTheDocument();
			expect(screen.getByText('ORDER123')).toBeInTheDocument();
		});
	});

	it('filters orders by status', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('RELIANCE.NS')).toBeInTheDocument();
		});

		// Click on "Closed" tab - use getByRole to find the button specifically
		const closedTab = screen.getByRole('button', { name: /Closed/i });
		closedTab.click();

		await waitFor(() => {
			expect(screen.queryByText('RELIANCE.NS')).not.toBeInTheDocument();
			expect(screen.getByText('TCS.NS')).toBeInTheDocument();
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
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker orders are only available in broker mode/i)).toBeInTheDocument();
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
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Broker is not connected/i)).toBeInTheDocument();
		});
	});

	it('handles error state with retry button', async () => {
		const userApi = await import('@/api/user');
		const mockError = new Error('Failed to fetch orders');
		vi.mocked(userApi.getBrokerOrders).mockRejectedValueOnce(mockError);

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
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Failed to load orders/i)).toBeInTheDocument();
			expect(screen.getByText('Retry Now')).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('displays empty state when no orders', async () => {
		const userApi = await import('@/api/user');
		vi.mocked(userApi.getBrokerOrders).mockResolvedValueOnce([]);

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
					<BrokerOrdersPage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('No orders found')).toBeInTheDocument();
		}, { timeout: 10000 });
	});
});
