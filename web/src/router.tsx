import { createBrowserRouter } from 'react-router-dom';
import { LoginPage } from './routes/LoginPage';
import { SignupPage } from './routes/SignupPage';
import { AppShell } from './routes/AppShell';
import { DashboardHome } from './routes/dashboard/DashboardHome';
import { BuyingZonePage } from './routes/dashboard/BuyingZonePage';
import { OrdersPage } from './routes/dashboard/OrdersPage';
import { PnlPage } from './routes/dashboard/PnlPage';
import { TargetsPage } from './routes/dashboard/TargetsPage';
import { ActivityPage } from './routes/dashboard/ActivityPage';
import { SettingsPage } from './routes/dashboard/SettingsPage';
import { RequireAuth } from './routes/RequireAuth';

export function createAppRouter() {
	return createBrowserRouter([
		{ path: '/', element: <LoginPage /> },
		{ path: '/login', element: <LoginPage /> },
		{ path: '/signup', element: <SignupPage /> },
		{
			path: '/dashboard',
			element: (
				<RequireAuth>
					<AppShell />
				</RequireAuth>
			),
			children: [
				{ index: true, element: <DashboardHome /> },
				{ path: 'buying-zone', element: <BuyingZonePage /> },
				{ path: 'orders', element: <OrdersPage /> },
				{ path: 'pnl', element: <PnlPage /> },
				{ path: 'targets', element: <TargetsPage /> },
				{ path: 'activity', element: <ActivityPage /> },
				{ path: 'settings', element: <SettingsPage /> },
			],
		},
	]);
}
