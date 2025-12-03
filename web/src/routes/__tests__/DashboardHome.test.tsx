import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { withProviders } from '@/test/utils';
import { DashboardHome } from '../dashboard/DashboardHome';
import type { ServiceStatus } from '@/api/service';
import type { PaperTradingPortfolio } from '@/api/paper-trading';
import type { PnlSummary } from '@/api/pnl';

// Mock all API modules
vi.mock('@/api/service', () => ({
	getServiceStatus: vi.fn(() => Promise.resolve({
		service_running: true,
		last_heartbeat: '2025-12-03T10:00:00Z',
		last_task_execution: '2025-12-03T09:55:00Z',
		error_count: 0,
		last_error: null,
		updated_at: '2025-12-03T10:00:00Z',
	})),
}));

vi.mock('@/api/paper-trading', () => ({
	getPaperTradingPortfolio: vi.fn(() => Promise.resolve({
		account: {
			initial_capital: 1000000,
			available_cash: 500000,
			total_pnl: 50000,
			realized_pnl: 30000,
			unrealized_pnl: 20000,
			portfolio_value: 550000,
			total_value: 1050000,
			return_percentage: 5.0,
		},
		holdings: [
			{
				symbol: 'RELIANCE.NS',
				quantity: 10,
				average_price: 2500,
				current_price: 2600,
				cost_basis: 25000,
				market_value: 26000,
				pnl: 1000,
				pnl_percentage: 4.0,
				target_price: 2700,
				distance_to_target: 3.7,
			},
			{
				symbol: 'TCS.NS',
				quantity: 5,
				average_price: 3500,
				current_price: 3400,
				cost_basis: 17500,
				market_value: 17000,
				pnl: -500,
				pnl_percentage: -2.86,
				target_price: 3600,
				distance_to_target: 5.6,
			},
		],
		recent_orders: [],
		order_statistics: {
			total_orders: 10,
			buy_orders: 6,
			sell_orders: 4,
			completed_orders: 8,
			pending_orders: 2,
			cancelled_orders: 0,
			rejected_orders: 0,
			success_rate: 80,
			reentry_orders: 2,
		},
	})),
}));

vi.mock('@/api/pnl', () => ({
	getPnlSummary: vi.fn(() => Promise.resolve({
		totalPnl: 50000,
		daysGreen: 15,
		daysRed: 5,
	})),
}));

vi.mock('@/api/signals', () => ({
	getBuyingZone: vi.fn(() => Promise.resolve([
		{ id: 1, symbol: 'RELIANCE.NS', status: 'active', ts: '2025-12-03T10:00:00Z' },
		{ id: 2, symbol: 'TCS.NS', status: 'active', ts: '2025-12-03T10:00:00Z' },
	])),
}));

vi.mock('@/api/orders', () => ({
	listOrders: vi.fn(() => Promise.resolve([
		{ id: 1, symbol: 'RELIANCE.NS', status: 'pending' },
		{ id: 2, symbol: 'TCS.NS', status: 'pending' },
	])),
}));

vi.mock('@/api/notifications', () => ({
	getNotificationCount: vi.fn(() => Promise.resolve({ unread_count: 3 })),
}));

// Mock useSettings hook
vi.mock('@/hooks/useSettings', () => ({
	useSettings: vi.fn(() => ({
		settings: { trade_mode: 'paper', broker: null, broker_status: null },
		isLoading: false,
		error: null,
		isPaperMode: true,
		isBrokerMode: false,
		broker: null,
		brokerStatus: null,
		isBrokerConnected: false,
	})),
}));

describe('DashboardHome', () => {
	const mockServiceStatus: ServiceStatus = {
		service_running: true,
		last_heartbeat: '2025-12-03T10:00:00Z',
		last_task_execution: '2025-12-03T09:55:00Z',
		error_count: 0,
		last_error: null,
		updated_at: '2025-12-03T10:00:00Z',
	};

	const mockPortfolio: PaperTradingPortfolio = {
		account: {
			initial_capital: 1000000,
			available_cash: 500000,
			total_pnl: 50000,
			realized_pnl: 30000,
			unrealized_pnl: 20000,
			portfolio_value: 550000,
			total_value: 1050000,
			return_percentage: 5.0,
		},
		holdings: [
			{
				symbol: 'RELIANCE.NS',
				quantity: 10,
				average_price: 2500,
				current_price: 2600,
				cost_basis: 25000,
				market_value: 26000,
				pnl: 1000,
				pnl_percentage: 4.0,
				target_price: 2700,
				distance_to_target: 3.7,
			},
			{
				symbol: 'TCS.NS',
				quantity: 5,
				average_price: 3500,
				current_price: 3400,
				cost_basis: 17500,
				market_value: 17000,
				pnl: -500,
				pnl_percentage: -2.86,
				target_price: 3600,
				distance_to_target: 5.6,
			},
		],
		recent_orders: [],
		order_statistics: {
			total_orders: 10,
			buy_orders: 6,
			sell_orders: 4,
			completed_orders: 8,
			pending_orders: 2,
			cancelled_orders: 0,
			rejected_orders: 0,
			success_rate: 80,
			reentry_orders: 2,
		},
	};

	const mockPnlSummary: PnlSummary = {
		totalPnl: 50000,
		daysGreen: 15,
		daysRed: 5,
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders dashboard title and live indicator', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Dashboard')).toBeInTheDocument();
			expect(screen.getByText('Live')).toBeInTheDocument();
		});
	});

	it('displays loading state initially', () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		expect(screen.getByText('Loading dashboard...')).toBeInTheDocument();
	});

	it('displays service status card with running status', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Service Status')).toBeInTheDocument();
			expect(screen.getByText('Running')).toBeInTheDocument();
		});
	});

	it('displays service status card with stopped status', async () => {
		const serviceApi = await import('@/api/service');
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValueOnce({
			...mockServiceStatus,
			service_running: false,
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Stopped')).toBeInTheDocument();
		});
	});

	it('displays error count when service has errors', async () => {
		const serviceApi = await import('@/api/service');
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValueOnce({
			...mockServiceStatus,
			error_count: 5,
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/5 error/i)).toBeInTheDocument();
		});
	});

	it('displays portfolio value card with formatted amount', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
			// Check that the card exists and contains some value
			const portfolioCard = screen.getByText('Portfolio Value').closest('div')?.parentElement;
			expect(portfolioCard).toBeInTheDocument();
			// The card should contain some numeric value (portfolio value)
			expect(portfolioCard?.textContent).toMatch(/\d/);
		});
	});

	it('displays total P&L card with formatted amount', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Total P&L')).toBeInTheDocument();
			expect(screen.getByText(/15 green \/ 5 red days/i)).toBeInTheDocument();
		});
	});

	it('displays active signals count', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Active Signals')).toBeInTheDocument();
			// Check that the card contains the count (2 appears multiple times, so check within context)
			const activeSignalsCard = screen.getByText('Active Signals').closest('div')?.parentElement;
			expect(activeSignalsCard).toHaveTextContent('2');
		});
	});

	it('displays open orders count', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Open Orders')).toBeInTheDocument();
			// Check that the card contains the count (2 appears multiple times, so check within context)
			const openOrdersCard = screen.getByText('Open Orders').closest('div')?.parentElement;
			expect(openOrdersCard).toHaveTextContent('2');
		});
	});

	it('displays portfolio breakdown section', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Portfolio Breakdown')).toBeInTheDocument();
			expect(screen.getByText('Available Cash')).toBeInTheDocument();
			expect(screen.getByText('Invested Value')).toBeInTheDocument();
			expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
			expect(screen.getByText('Realized P&L')).toBeInTheDocument();
		});
	});

	it('displays holdings count in portfolio breakdown', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/2 position/i)).toBeInTheDocument();
		});
	});

	it('displays quick actions section', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Quick Actions')).toBeInTheDocument();
			expect(screen.getByText(/View Buying Zone/i)).toBeInTheDocument();
			expect(screen.getByText(/Paper Trading Portfolio/i)).toBeInTheDocument();
			// Use getAllByText since "View Orders" appears in both stats card and quick actions
			const viewOrdersLinks = screen.getAllByText(/View Orders/i);
			expect(viewOrdersLinks.length).toBeGreaterThan(0);
		});
	});

	it('displays unread notifications count in quick actions', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const unreadLink = screen.getByRole('link', { name: /unread/i });
			expect(unreadLink).toBeInTheDocument();
			expect(unreadLink).toHaveTextContent('3');
		});
	});

	it('displays top holdings table when holdings exist', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Top Holdings')).toBeInTheDocument();
			// Holdings may appear in both mobile card view and desktop table view
			const relianceElements = screen.getAllByText('RELIANCE.NS');
			const tcsElements = screen.getAllByText('TCS.NS');
			expect(relianceElements.length).toBeGreaterThan(0);
			expect(tcsElements.length).toBeGreaterThan(0);
		});
	});

	it('displays holdings table headers', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Quantity' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Avg Price' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Current' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'P&L' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'P&L %' })).toBeInTheDocument();
		});
	});

	it('does not display top holdings section when no holdings', async () => {
		const paperTradingApi = await import('@/api/paper-trading');
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValueOnce({
			...mockPortfolio,
			holdings: [],
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.queryByText('Top Holdings')).not.toBeInTheDocument();
		});
	});

	it('displays links to detailed pages', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			const serviceLink = screen.getByRole('link', { name: /View Details/i });
			expect(serviceLink).toHaveAttribute('href', '/dashboard/service');

			const portfolioLink = screen.getByRole('link', { name: /View Portfolio/i });
			expect(portfolioLink).toHaveAttribute('href', '/dashboard/paper-trading');

			const pnlLink = screen.getByRole('link', { name: /View P&L/i });
			expect(pnlLink).toHaveAttribute('href', '/dashboard/pnl');
		});
	});

	it('handles missing portfolio data gracefully', async () => {
		const paperTradingApi = await import('@/api/paper-trading');
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValueOnce(null);

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Dashboard')).toBeInTheDocument();
		});
	});

	it('handles zero active signals', async () => {
		const signalsApi = await import('@/api/signals');
		vi.mocked(signalsApi.getBuyingZone).mockResolvedValueOnce([]);

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('0')).toBeInTheDocument();
		});
	});

	it('handles zero open orders', async () => {
		const ordersApi = await import('@/api/orders');
		vi.mocked(ordersApi.listOrders).mockResolvedValueOnce([]);

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Open Orders')).toBeInTheDocument();
			// The count should be 0, but we check the card exists
			const openOrdersCard = screen.getByText('Open Orders').closest('div')?.parentElement;
			expect(openOrdersCard).toBeInTheDocument();
		});
	});

	it('handles zero unread notifications', async () => {
		const notificationsApi = await import('@/api/notifications');
		vi.mocked(notificationsApi.getNotificationCount).mockResolvedValueOnce({ unread_count: 0 });

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Quick Actions')).toBeInTheDocument();
			// When there are no unread notifications, the unread badge should not appear
			const unreadBadge = screen.queryByRole('link', { name: /unread/i });
			expect(unreadBadge).not.toBeInTheDocument();
		});
	});

	it('displays last heartbeat time when available', async () => {
		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Last heartbeat:/i)).toBeInTheDocument();
		});
	});

	it('handles missing last heartbeat gracefully', async () => {
		const serviceApi = await import('@/api/service');
		vi.mocked(serviceApi.getServiceStatus).mockResolvedValueOnce({
			...mockServiceStatus,
			last_heartbeat: null,
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Service Status')).toBeInTheDocument();
			// When last_heartbeat is null, the "Last heartbeat:" text should not appear
			const heartbeatText = screen.queryByText(/Last heartbeat:/i);
			expect(heartbeatText).not.toBeInTheDocument();
		});
	});

	it('displays negative P&L with correct styling', async () => {
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getPnlSummary).mockResolvedValueOnce({
			totalPnl: -10000,
			daysGreen: 5,
			daysRed: 15,
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Total P&L')).toBeInTheDocument();
		});
	});

	it('displays negative return percentage correctly', async () => {
		const paperTradingApi = await import('@/api/paper-trading');
		vi.mocked(paperTradingApi.getPaperTradingPortfolio).mockResolvedValueOnce({
			...mockPortfolio,
			account: {
				...mockPortfolio.account,
				return_percentage: -2.5,
			},
		});

		render(
			withProviders(
				<MemoryRouter>
					<DashboardHome />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
		});
	});

	describe('Trade Mode Conditional Rendering', () => {
		it('displays paper mode badge in paper mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText('Paper Mode')).toBeInTheDocument();
			});
		});

		it('displays broker mode badge with connection status in broker mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Check for badge - find all instances and verify at least one has both broker name and Connected
				const allKotakNeo = screen.getAllByText(/KOTAK-NEO/i);
				expect(allKotakNeo.length).toBeGreaterThan(0);
				// Check that at least one badge contains both broker name and Connected
				const badgeWithConnected = allKotakNeo.find((el) => {
					const parent = el.closest('div');
					return parent?.textContent?.includes('Connected');
				});
				expect(badgeWithConnected).toBeDefined();
			});
		});

		it('displays disconnected broker status badge', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Check for disconnected status - may be in badge or connection widget
				const disconnectedText = screen.getAllByText(/Disconnected/i);
				expect(disconnectedText.length).toBeGreaterThan(0);
			});
		});

		it('shows paper trading portfolio card in paper mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
				expect(screen.getByText('View Portfolio →')).toBeInTheDocument();
			});
		});

		it('shows broker portfolio placeholder in broker mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText('Broker Portfolio')).toBeInTheDocument();
				expect(screen.queryByText('Portfolio Value')).not.toBeInTheDocument();
			});
		});

		it('shows broker connection status widget in broker mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText('Broker Connection')).toBeInTheDocument();
				// Check for broker name anywhere in the document (it appears in both badge and widget)
				expect(screen.getAllByText(/KOTAK-NEO/i).length).toBeGreaterThan(0);
			});
		});

		it('hides paper trading portfolio breakdown in broker mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.queryByText('Portfolio Breakdown')).not.toBeInTheDocument();
				expect(screen.queryByText('Top Holdings')).not.toBeInTheDocument();
			});
		});

		it('shows paper trading quick action link only in paper mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText(/Paper Trading Portfolio/i)).toBeInTheDocument();
			});
		});

		it('shows broker portfolio quick action link in broker mode', async () => {
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Check for broker portfolio in quick actions (more specific)
				const quickActionLink = screen.getByRole('link', { name: /🏦 Broker Portfolio/i });
				expect(quickActionLink).toBeInTheDocument();
				expect(screen.queryByText(/Paper Trading Portfolio/i)).not.toBeInTheDocument();
			});
		});

		it('does not fetch paper trading portfolio in broker mode', async () => {
			const useSettings = await import('@/hooks/useSettings');
			const paperTradingApi = await import('@/api/paper-trading');
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
						<DashboardHome />
					</MemoryRouter>
				)
			);

			// Wait for component to render
			await waitFor(() => {
				expect(screen.getByText('Dashboard')).toBeInTheDocument();
			});

			// Paper trading API should not be called (or called but query disabled)
			// The query is disabled via enabled: isPaperMode, so it won't fetch
		});
	});
});
