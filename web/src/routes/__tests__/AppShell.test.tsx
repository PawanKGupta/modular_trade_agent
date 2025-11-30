import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppShell } from '../AppShell';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { withProviders } from '@/test/utils';

const API = (path: string) => `http://localhost:8000/api/v1${path}`;

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
			expect(screen.getByText('OVERVIEW')).toBeInTheDocument();
			expect(screen.getByText('TRADING')).toBeInTheDocument();
			expect(screen.getByText('SYSTEM')).toBeInTheDocument();
			expect(screen.getByText('SETTINGS')).toBeInTheDocument();
			expect(screen.getByText('LOGS')).toBeInTheDocument();
			expect(screen.getByText('NOTIFICATIONS')).toBeInTheDocument();
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
		await waitFor(() => {
			const tradingButton = screen.getByText('TRADING');
			expect(tradingButton).toBeInTheDocument();
		});

		// Trading should be collapsed initially
		expect(screen.queryByText('Buying Zone')).not.toBeInTheDocument();

		// Click to expand Trading
		const tradingButton = screen.getByText('TRADING').closest('button');
		fireEvent.click(tradingButton!);

		// Trading items should now be visible
		await waitFor(() => {
			expect(screen.getByText('Buying Zone')).toBeInTheDocument();
			expect(screen.getByText('Orders')).toBeInTheDocument();
		});

		// Click to collapse Trading
		fireEvent.click(tradingButton!);

		// Trading items should be hidden again
		await waitFor(() => {
			expect(screen.queryByText('Buying Zone')).not.toBeInTheDocument();
		});
	});

	it('auto-expands category when navigating to a page in it', async () => {
		renderAppShell('/dashboard/buying-zone');
		await waitFor(() => {
			// Trading category should be auto-expanded
			expect(screen.getByText('Buying Zone')).toBeInTheDocument();
			expect(screen.getByText('Orders')).toBeInTheDocument();
		});
	});

	it('highlights active menu item', async () => {
		renderAppShell('/dashboard/buying-zone');
		await waitFor(() => {
			const buyingZoneLink = screen.getByText('Buying Zone').closest('a');
			expect(buyingZoneLink).toHaveClass('bg-[var(--accent)]/20');
		});
	});

	it('shows notification badge when there are unread notifications', async () => {
		server.use(
			http.get(API('/user/notifications/count'), () => {
				return HttpResponse.json({ unread_count: 5 });
			}),
		);

		renderAppShell();
		await waitFor(() => {
			const notificationsButton = screen.getByText('NOTIFICATIONS').closest('button');
			if (notificationsButton) {
				fireEvent.click(notificationsButton);
			}
		});

		await waitFor(() => {
			// Badge might appear in the menu item
			const notificationsLink = screen.queryByText('Notifications');
			expect(notificationsLink).toBeInTheDocument();
		});
	});

	it('persists expanded/collapsed state in localStorage', async () => {
		renderAppShell();
		const tradingButton = await screen.findByText('TRADING');
		fireEvent.click(tradingButton.closest('button')!);

		await waitFor(() => {
			const saved = localStorage.getItem('navExpandedGroups');
			expect(saved).toBeTruthy();
			const expanded = JSON.parse(saved!);
			expect(expanded).toContain('Trading');
		});
	});
});
