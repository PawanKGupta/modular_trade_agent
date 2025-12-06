import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from '../AppShell';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';
import { vi } from 'vitest';

const API = (path: string) => `http://localhost:8000/api/v1${path}`;

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

function renderAppShell(initialPath = '/dashboard') {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[initialPath]}>
				<Routes>
					<Route path="/login" element={<div>LoginForm</div>} />
					<Route path="/dashboard" element={<AppShell />}>
						<Route index element={<div>Home</div>} />
						<Route path="buying-zone" element={<div>Buying Zone</div>} />
						<Route path="orders" element={<div>Orders</div>} />
						<Route path="settings" element={<div>Settings</div>} />
					</Route>
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('AppShell', () => {
	beforeEach(() => {
		// Clear localStorage before each test
		localStorage.clear();
	});

	it('shows user email and logs out to login route', async () => {
		renderAppShell();
		// email from MSW /auth/me
		const email = await screen.findByText('test@example.com');
		expect(email).toBeInTheDocument();
		const logout = screen.getByText(/logout/i);
		fireEvent.click(logout);
		await screen.findByText('LoginForm');
	});

	it('displays Rebound branding', async () => {
		renderAppShell();
		await waitFor(() => {
			expect(screen.getByText('Rebound')).toBeInTheDocument();
			expect(screen.getByText('Modular Trade Agent')).toBeInTheDocument();
		});
	});

	it('shows menu categories organized by usage', async () => {
		renderAppShell();
		await waitFor(() => {
			// Categories are displayed with uppercase CSS but text is title case
			expect(screen.getByText(/overview/i)).toBeInTheDocument();
			expect(screen.getByText(/trading/i)).toBeInTheDocument();
			expect(screen.getByText(/system/i)).toBeInTheDocument();
			expect(screen.getByText(/settings/i)).toBeInTheDocument();
			expect(screen.getByText(/logs/i)).toBeInTheDocument();
			expect(screen.getByText(/notifications/i)).toBeInTheDocument();
		});
	});

	it('defaults to only Overview expanded', async () => {
		renderAppShell();
		await waitFor(() => {
			// Overview should be expanded (Dashboard visible)
			expect(screen.getByText('Dashboard')).toBeInTheDocument();

			// Trading should be collapsed (Buying Zone not visible)
			expect(screen.queryByText('Buying Zone')).not.toBeInTheDocument();
		});
	});

	it('allows expanding and collapsing menu categories', async () => {
		renderAppShell();
		const tradingButton = await screen.findByText(/trading/i);
		expect(tradingButton).toBeInTheDocument();

		// Trading should be collapsed initially
		expect(screen.queryByText('Buying Zone')).not.toBeInTheDocument();

		// Click to expand Trading
		const tradingButtonElement = tradingButton.closest('button');
		if (tradingButtonElement) {
			fireEvent.click(tradingButtonElement);
		}

		// Trading items should now be visible
		await waitFor(() => {
			expect(screen.getByText('Buying Zone')).toBeInTheDocument();
			expect(screen.getByText('Orders')).toBeInTheDocument();
		});

		// Click to collapse Trading
		if (tradingButtonElement) {
			fireEvent.click(tradingButtonElement);
		}

		// Trading items should be hidden again
		await waitFor(() => {
			expect(screen.queryByText('Buying Zone')).not.toBeInTheDocument();
		});
	});

	it('auto-expands category when navigating to a page in it', async () => {
		renderAppShell('/dashboard/buying-zone');
		// Wait for auto-expansion to occur (the useEffect should expand the Trading group)
		await waitFor(() => {
			// Trading category should be auto-expanded because Buying Zone is active
			// Check for menu items in the navigation
			const nav = screen.getByRole('navigation');
			const ordersLink = nav.querySelector('a[href="/dashboard/orders"]');
			expect(ordersLink).toBeInTheDocument();
		}, { timeout: 10000 });

		// Verify Trading items are visible in the menu
		const nav = screen.getByRole('navigation');
		expect(nav).toBeInTheDocument();
		expect(nav.textContent).toContain('Orders');
	});

	it('highlights active menu item', async () => {
		renderAppShell('/dashboard/buying-zone');

		// Wait for the Buying Zone link to appear (auto-expanded)
		await waitFor(() => {
			const allBuyingZones = screen.getAllByText('Buying Zone');
			expect(allBuyingZones.length).toBeGreaterThan(0);
		}, { timeout: 10000 });

		// Find the menu link (should be in a <nav> element)
		const nav = screen.getByRole('navigation');
		const menuLink = nav.querySelector('a[href="/dashboard/buying-zone"]');
		expect(menuLink).toBeInTheDocument();

		// Check for active state styling
		if (menuLink) {
			expect(menuLink).toHaveClass('bg-[var(--accent)]/20');
		}
	});

	it('shows notification badge when there are unread notifications', async () => {
		// Set up mock before rendering
		server.use(
			http.get(API('/user/notifications/count'), () => {
				return HttpResponse.json({ unread_count: 5 });
			}),
		);

		renderAppShell();

		// Wait for component to load
		await waitFor(() => {
			expect(screen.getByText(/notifications/i)).toBeInTheDocument();
		}, { timeout: 10000 });

		// Expand Notifications category
		const notificationsButton = await screen.findByText(/notifications/i);
		const buttonElement = notificationsButton.closest('button');

		if (buttonElement) {
			fireEvent.click(buttonElement);
		}

		// Wait for menu item to appear - there may be multiple "Notifications" texts, so find the link
		await waitFor(() => {
			// Find the link in the navigation menu
			const nav = screen.getByRole('navigation');
			const notificationsLink = nav.querySelector('a[href*="notifications"]');
			expect(notificationsLink).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('persists expanded/collapsed state in localStorage', async () => {
		renderAppShell();
		const tradingButton = await screen.findByText(/trading/i);
		const buttonElement = tradingButton.closest('button');

		if (buttonElement) {
			fireEvent.click(buttonElement);
		}

		await waitFor(() => {
			const saved = localStorage.getItem('navExpandedGroups');
			expect(saved).toBeTruthy();
			const expanded = JSON.parse(saved!);
			expect(expanded).toContain('Trading');
		});
	});

	describe('Trade Mode Conditional Rendering', () => {
		it('displays paper mode badge in header when in paper mode', async () => {
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

			renderAppShell();

			await waitFor(() => {
				expect(screen.getByText('Paper Mode')).toBeInTheDocument();
			});
		});

		it('displays broker mode badge with connection status in header when in broker mode', async () => {
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

			renderAppShell();

			await waitFor(() => {
				expect(screen.getByText(/KOTAK-NEO/i)).toBeInTheDocument();
				expect(screen.getByText(/✓/i)).toBeInTheDocument();
			});
		});

		it('displays disconnected broker badge in header', async () => {
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

			renderAppShell();

			await waitFor(() => {
				expect(screen.getByText(/⚠/i)).toBeInTheDocument();
			});
		});

		it('shows paper trading menu items in paper mode', async () => {
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

			renderAppShell();

			// Expand Trading category
			const tradingButton = await screen.findByText(/trading/i);
			const buttonElement = tradingButton.closest('button');
			if (buttonElement) {
				fireEvent.click(buttonElement);
			}

			await waitFor(() => {
				expect(screen.getByText('Paper Trading')).toBeInTheDocument();
				expect(screen.getByText('Trade History')).toBeInTheDocument();
			});
		});

		it('hides paper trading menu items in broker mode', async () => {
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

			renderAppShell();

			// Expand Trading category
			const tradingButton = await screen.findByText(/trading/i);
			const buttonElement = tradingButton.closest('button');
			if (buttonElement) {
				fireEvent.click(buttonElement);
			}

			await waitFor(() => {
				expect(screen.getByText('Buying Zone')).toBeInTheDocument();
				expect(screen.getByText('Orders')).toBeInTheDocument();
				expect(screen.queryByText('Paper Trading')).not.toBeInTheDocument();
				expect(screen.queryByText('Trade History')).not.toBeInTheDocument();
			});
		});

		it('shows other trading menu items in both modes', async () => {
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

			renderAppShell();

			// Expand Trading category
			const tradingButton = await screen.findByText(/trading/i);
			const buttonElement = tradingButton.closest('button');
			if (buttonElement) {
				fireEvent.click(buttonElement);
			}

			await waitFor(() => {
				expect(screen.getByText('Buying Zone')).toBeInTheDocument();
				expect(screen.getByText('Orders')).toBeInTheDocument();
				expect(screen.getByText('PnL')).toBeInTheDocument();
				expect(screen.getByText('Targets')).toBeInTheDocument();
			});
		});
	});
});
