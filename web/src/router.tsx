import { createBrowserRouter } from 'react-router-dom';
import { LoginPage } from './routes/LoginPage';
import { SignupPage } from './routes/SignupPage';
import { AppShell } from './routes/AppShell';
import { DashboardHome } from './routes/dashboard/DashboardHome';
import { BuyingZonePage } from './routes/dashboard/BuyingZonePage';
import { OrdersPage } from './routes/dashboard/OrdersPage';
import { PaperTradingPage } from './routes/dashboard/PaperTradingPage';
import { PaperTradingHistoryPage } from './routes/dashboard/PaperTradingHistoryPage';
import { PnlPage } from './routes/dashboard/PnlPage';
import { TargetsPage } from './routes/dashboard/TargetsPage';
import { ActivityPage } from './routes/dashboard/ActivityPage';
import { SettingsPage } from './routes/dashboard/SettingsPage';
import { NotificationPreferencesPage } from './routes/dashboard/NotificationPreferencesPage';
import { NotificationsPage } from './routes/dashboard/NotificationsPage';
import { ServiceStatusPage } from './routes/dashboard/ServiceStatusPage';
import { TradingConfigPage } from './routes/dashboard/TradingConfigPage';
import { AdminUsersPage } from './routes/dashboard/AdminUsersPage';
import { MLTrainingPage } from './routes/dashboard/MLTrainingPage';
import { LogViewerPage } from './routes/dashboard/LogViewerPage';
import { ServiceSchedulePage } from './routes/dashboard/ServiceSchedulePage';
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
				{ path: 'paper-trading', element: <PaperTradingPage /> },
				{ path: 'paper-trading-history', element: <PaperTradingHistoryPage /> },
				{ path: 'pnl', element: <PnlPage /> },
				{ path: 'targets', element: <TargetsPage /> },
				{ path: 'activity', element: <ActivityPage /> },
				{ path: 'service', element: <ServiceStatusPage /> },
				{ path: 'trading-config', element: <TradingConfigPage /> },
				{ path: 'logs', element: <LogViewerPage /> },
				{ path: 'settings', element: <SettingsPage /> },
				{ path: 'notification-preferences', element: <NotificationPreferencesPage /> },
				{ path: 'notifications', element: <NotificationsPage /> },
				{ path: 'admin/users', element: <AdminUsersPage /> },
				{ path: 'admin/ml', element: <MLTrainingPage /> },
				{ path: 'admin/schedules', element: <ServiceSchedulePage /> },
			],
		},
	]);
}
