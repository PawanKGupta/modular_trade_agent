import { createBrowserRouter, Navigate } from 'react-router-dom';
import { LoginPage } from './routes/LoginPage';
import { SignupPage } from './routes/SignupPage';
import { ForgotPasswordPage } from './routes/ForgotPasswordPage';
import { ResetPasswordPage } from './routes/ResetPasswordPage';
import { VerifyEmailPage } from './routes/VerifyEmailPage';
import { ResendVerificationPage } from './routes/ResendVerificationPage';
import { AppShell } from './routes/AppShell';
import { DashboardHome } from './routes/dashboard/DashboardHome';
import { BuyingZonePage } from './routes/dashboard/BuyingZonePage';
import { OrdersPage } from './routes/dashboard/OrdersPage';
import { PaperTradingPage } from './routes/dashboard/PaperTradingPage';
import { PaperTradingHistoryPage } from './routes/dashboard/PaperTradingHistoryPage';
import { BrokerPortfolioPage } from './routes/dashboard/BrokerPortfolioPage';
import { BrokerOrdersPage } from './routes/dashboard/BrokerOrdersPage';
import { BrokerTradingHistoryPage } from './routes/dashboard/BrokerTradingHistoryPage';
import { PnlPage } from './routes/dashboard/PnlPage';
import { TargetsPage } from './routes/dashboard/TargetsPage';
import { SettingsPage } from './routes/dashboard/SettingsPage';
import { NotificationPreferencesPage } from './routes/dashboard/NotificationPreferencesPage';
import { NotificationsPage } from './routes/dashboard/NotificationsPage';
import { ServiceStatusPage } from './routes/dashboard/ServiceStatusPage';
import { TradingConfigPage } from './routes/dashboard/TradingConfigPage';
import { AdminUsersPage } from './routes/dashboard/AdminUsersPage';
import { MLTrainingPage } from './routes/dashboard/MLTrainingPage';
import { LogViewerPage } from './routes/dashboard/LogViewerPage';
import { ServiceSchedulePage } from './routes/dashboard/ServiceSchedulePage';
import { MonitoringDashboardPage } from './routes/dashboard/MonitoringDashboardPage';
import { BillingPage } from './routes/dashboard/BillingPage';
import { AdminBillingPage } from './routes/dashboard/AdminBillingPage';
import { RequireAuth } from './routes/RequireAuth';
import { HelpLayout } from './routes/help/HelpLayout';
import { HelpHomePage } from './routes/help/HelpHomePage';
import { HelpGetStartedPage } from './routes/help/HelpGetStartedPage';
import { HelpKotakApiPage } from './routes/help/HelpKotakApiPage';
import { HelpConnectKotakPage } from './routes/help/HelpConnectKotakPage';
import { HelpBillingPage } from './routes/help/HelpBillingPage';
import { HelpFaqPage } from './routes/help/HelpFaqPage';

export function createAppRouter() {
	return createBrowserRouter([
		{ path: '/', element: <LoginPage /> },
		{ path: '/login', element: <LoginPage /> },
		{ path: '/signup', element: <SignupPage /> },
		{ path: '/forgot-password', element: <ForgotPasswordPage /> },
		{ path: '/reset-password', element: <ResetPasswordPage /> },
		{ path: '/verify-email', element: <VerifyEmailPage /> },
		{ path: '/resend-verification', element: <ResendVerificationPage /> },
		{
			path: '/help',
			element: <HelpLayout />,
			children: [
				{ index: true, element: <HelpHomePage /> },
				{ path: 'get-started', element: <HelpGetStartedPage /> },
				{ path: 'kotak-api', element: <HelpKotakApiPage /> },
				{ path: 'connect-kotak', element: <HelpConnectKotakPage /> },
				{ path: 'billing', element: <HelpBillingPage /> },
				{ path: 'faq', element: <HelpFaqPage /> },
			],
		},
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
				{ path: 'broker-portfolio', element: <BrokerPortfolioPage /> },
				{ path: 'broker-orders', element: <BrokerOrdersPage /> },
				{ path: 'broker-history', element: <BrokerTradingHistoryPage /> },
				{ path: 'pnl', element: <PnlPage /> },
				{ path: 'targets', element: <TargetsPage /> },
				{ path: 'service', element: <ServiceStatusPage /> },
				{ path: 'trading-config', element: <TradingConfigPage /> },
				{ path: 'logs', element: <LogViewerPage /> },
				{ path: 'activity', element: <Navigate to="/dashboard/logs" replace /> },
				{ path: 'settings', element: <SettingsPage /> },
				{ path: 'billing', element: <BillingPage /> },
				{ path: 'notification-preferences', element: <NotificationPreferencesPage /> },
				{ path: 'notifications', element: <NotificationsPage /> },
				{ path: 'admin/users', element: <AdminUsersPage /> },
				{ path: 'admin/ml', element: <MLTrainingPage /> },
				{ path: 'admin/schedules', element: <ServiceSchedulePage /> },
				{ path: 'admin/monitoring', element: <MonitoringDashboardPage /> },
				{ path: 'admin/billing', element: <AdminBillingPage /> },
			],
		},
	]);
}
