import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getServiceStatus, getPositionCreationMetrics, getPositionsWithoutSellOrders, type ServiceStatus, type PositionsWithoutSellOrders } from '../../api/service';
import { getPortfolio, type PaperTradingPortfolio } from '../../api/user';
import { getPnlSummary, type PnlSummary } from '../../api/pnl';
import { getBuyingZone } from '../../api/signals';
import { listOrders } from '../../api/orders';
import { getNotificationCount } from '../../api/notifications';
import { useSettings } from '../../hooks/useSettings';
import { HolidayBanner } from '../../components/HolidayBanner';
import { PnlTrendChart } from '../../components/charts/PnlTrendChart';
import { PortfolioValueChart } from '../../components/charts/PortfolioValueChart';
import { MetricsCard } from '../../components/dashboard/MetricsCard';

function formatMoney(amount: number): string {
	return new Intl.NumberFormat('en-IN', {
		style: 'currency',
		currency: 'INR',
		maximumFractionDigits: 0,
	}).format(amount);
}

function formatPercent(value: number): string {
	return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatTimeAgo(dateString: string | null): string {
	if (!dateString) return 'Never';
	const date = new Date(dateString);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffMins = Math.floor(diffMs / 60000);
	const diffHours = Math.floor(diffMs / 3600000);
	const diffDays = Math.floor(diffMs / 86400000);

	if (diffMins < 1) return 'Just now';
	if (diffMins < 60) return `${diffMins}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	if (diffDays < 7) return `${diffDays}d ago`;
	return date.toLocaleDateString();
}

export function DashboardHome() {
	useEffect(() => {
		document.title = 'Dashboard';
	}, []);

	// Get user settings to determine trade mode
	const { isPaperMode, isBrokerMode, broker, brokerStatus, isBrokerConnected } = useSettings();

	// Fetch all dashboard data
	const serviceStatusQ = useQuery<ServiceStatus>({
		queryKey: ['service-status'],
		queryFn: getServiceStatus,
		refetchInterval: 15000, // Refresh every 15 seconds
	});

	// Fetch unified portfolio (paper or broker based on trade mode)
	const portfolioQ = useQuery<PaperTradingPortfolio>({
		queryKey: ['portfolio', isPaperMode ? 'paper' : 'broker'],
		queryFn: getPortfolio,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	const pnlQ = useQuery<PnlSummary>({
		queryKey: ['pnl-summary'],
		queryFn: () => getPnlSummary(),
		refetchInterval: 30000,
	});

	const signalsQ = useQuery({
		queryKey: ['signals-count'],
		queryFn: async () => {
			const signals = await getBuyingZone(100, null, 'active');
			return signals.length;
		},
		refetchInterval: 60000, // Refresh every minute
		retry: 1, // Only retry once
		staleTime: 30000, // Consider data fresh for 30 seconds
	});

	const ordersQ = useQuery({
		queryKey: ['orders-open'],
		queryFn: async () => {
			const orders = await listOrders({ status: 'pending' });
			return orders.length;
		},
		refetchInterval: 30000,
	});

	const notificationsQ = useQuery({
		queryKey: ['notifications-count'],
		queryFn: async () => {
			const data = await getNotificationCount();
			return data.unread_count;
		},
		refetchInterval: 30000,
	});

	const positionMetricsQ = useQuery({
		queryKey: ['position-creation-metrics'],
		queryFn: getPositionCreationMetrics,
		refetchInterval: 60000, // Refresh every minute
	});

	const positionsWithoutOrdersQ = useQuery<PositionsWithoutSellOrders>({
		queryKey: ['positions-without-sell-orders'],
		queryFn: getPositionsWithoutSellOrders,
		refetchInterval: 120000, // Refresh every 2 minutes (optimized for performance)
		staleTime: 60000, // Consider data fresh for 1 minute
		retry: 1, // Only retry once on failure
		retryDelay: 2000, // Wait 2 seconds before retry
		// Don't block dashboard loading - this is a background query
		refetchOnMount: false, // Don't refetch on mount if data exists
		refetchOnWindowFocus: false, // Don't refetch on window focus
	});

	const serviceStatus = serviceStatusQ.data;
	const portfolio = portfolioQ.data;
	const pnl = pnlQ.data;
	const activeSignalsCount = signalsQ.data ?? 0;
	const openOrdersCount = ordersQ.data ?? 0;
	const unreadNotificationsCount = notificationsQ.data ?? 0;

	const positionsWithoutOrders = positionsWithoutOrdersQ.data;
	const positionsWithoutOrdersCount = positionsWithoutOrders?.count ?? 0;
	const positionsWithoutOrdersError = positionsWithoutOrdersQ.error;

	// Don't block dashboard on positions without orders query (it can be slow)
	// Show dashboard immediately and let this query load in background
	// Only block on critical queries - let others load in background
	// Service status is critical (needed for service status card)
	// Portfolio is critical in paper mode (needed for portfolio cards)
	const isLoading =
		serviceStatusQ.isLoading ||
		(portfolioQ.isLoading && isPaperMode); // Only block on portfolio in paper mode

	if (isLoading) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-sm sm:text-base text-[var(--text)]">Loading dashboard...</div>
			</div>
		);
	}

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6">
			{/* Holiday Banner */}
			<HolidayBanner />

			{/* Header */}
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0">
				<h1 className="text-xl sm:text-2xl font-semibold text-[var(--text)]">Dashboard</h1>
				<div className="flex items-center gap-3">
					{/* Mode Badge */}
					{isPaperMode && (
						<div className="flex items-center gap-1.5 px-2 py-1 rounded bg-blue-500/20 border border-blue-500/30">
							<div className="w-2 h-2 bg-blue-400 rounded-full" />
							<span className="text-xs text-blue-400 font-medium">Paper Mode</span>
						</div>
					)}
					{isBrokerMode && (
						<div
							className={`flex items-center gap-1.5 px-2 py-1 rounded border ${
								isBrokerConnected
									? 'bg-green-500/20 border-green-500/30'
									: 'bg-yellow-500/20 border-yellow-500/30'
							}`}
						>
							<div
								className={`w-2 h-2 rounded-full ${
									isBrokerConnected ? 'bg-green-400' : 'bg-yellow-400'
								}`}
							/>
							<span
								className={`text-xs font-medium ${
									isBrokerConnected ? 'text-green-400' : 'text-yellow-400'
								}`}
							>
								{broker ? `${broker.toUpperCase()}` : 'Broker'} {isBrokerConnected ? 'Connected' : 'Disconnected'}
							</span>
						</div>
					)}
					<div className="flex items-center gap-2">
						<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
						<span className="text-xs text-[var(--muted)]">Live</span>
					</div>
				</div>
			</div>

			{/* Service Status Card */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
					<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Service Status</h2>
					<Link
						to="/dashboard/service"
						className="text-sm text-[var(--accent)] hover:underline min-h-[44px] flex items-center"
					>
						View Details →
					</Link>
				</div>
				<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
					{serviceStatusQ.isLoading ? (
						<div className="text-xs sm:text-sm text-[var(--muted)]">Loading status...</div>
					) : serviceStatus ? (
						<>
					<div className="flex items-center gap-2">
						<div
							className={`w-3 h-3 rounded-full ${
										serviceStatus.service_running ? 'bg-green-500' : 'bg-red-500'
							}`}
						/>
						<span className="text-sm sm:text-base text-[var(--text)]">
									{serviceStatus.service_running ? 'Running' : 'Stopped'}
						</span>
					</div>
							{serviceStatus.last_heartbeat && (
						<span className="text-xs sm:text-sm text-[var(--muted)]">
							Last heartbeat: {formatTimeAgo(serviceStatus.last_heartbeat)}
						</span>
					)}
							{serviceStatus.error_count > 0 && (
						<span className="text-xs sm:text-sm text-red-400">
							{serviceStatus.error_count} error{serviceStatus.error_count !== 1 ? 's' : ''}
						</span>
							)}
						</>
					) : (
						<div className="text-xs sm:text-sm text-yellow-400">
							Status unavailable (query may have failed)
						</div>
					)}
				</div>
			</div>

			{/* Broker Connection Status Card (only in broker mode) */}
			{isBrokerMode && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
						<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Broker Connection</h2>
						<Link
							to="/dashboard/settings"
							className="text-sm text-[var(--accent)] hover:underline min-h-[44px] flex items-center"
						>
							Configure →
						</Link>
					</div>
					<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
						<div className="flex items-center gap-2">
							<div
								className={`w-3 h-3 rounded-full ${
									isBrokerConnected ? 'bg-green-500' : 'bg-yellow-500'
								}`}
							/>
							<span className="text-sm sm:text-base text-[var(--text)]">
								{broker ? broker.toUpperCase() : 'Broker'}: {brokerStatus || 'Not Connected'}
							</span>
						</div>
						{!isBrokerConnected && (
							<span className="text-xs sm:text-sm text-yellow-400">
								Please configure broker credentials in settings
							</span>
						)}
					</div>
				</div>
			)}

			{/* Position Creation Health Card (only in broker mode) */}
			{isBrokerMode && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
						<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Position Creation Health</h2>
						<span className="text-xs sm:text-sm text-[var(--muted)]">Issue #1 Fix</span>
					</div>
					{positionMetricsQ.isLoading ? (
						<div className="text-xs sm:text-sm text-[var(--muted)]">Loading metrics...</div>
					) : !serviceStatus?.service_running ? (
						<div className="text-xs sm:text-sm text-[var(--muted)]">
							Service is not running. Start the service to track position creation metrics.
						</div>
					) : positionMetricsQ.data && positionMetricsQ.data.total_attempts > 0 ? (
						<div className="space-y-2">
							<div className="flex items-center justify-between">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Success Rate</span>
								<span
									className={`text-sm sm:text-base font-semibold ${
										positionMetricsQ.data.success_rate >= 95
											? 'text-green-400'
											: positionMetricsQ.data.success_rate >= 80
												? 'text-yellow-400'
												: 'text-red-400'
									}`}
								>
									{positionMetricsQ.data.success_rate.toFixed(1)}%
								</span>
							</div>
							<div className="grid grid-cols-2 gap-2 text-xs sm:text-sm">
								<div className="flex items-center gap-2">
									<div className="w-2 h-2 bg-green-400 rounded-full" />
									<span className="text-[var(--muted)]">Success:</span>
									<span className="text-[var(--text)] font-medium">{positionMetricsQ.data.success}</span>
								</div>
								{positionMetricsQ.data.failed_missing_repos > 0 && (
									<div className="flex items-center gap-2">
										<div className="w-2 h-2 bg-red-400 rounded-full" />
										<span className="text-[var(--muted)]">Missing Repos:</span>
										<span className="text-red-400 font-medium">{positionMetricsQ.data.failed_missing_repos}</span>
									</div>
								)}
								{positionMetricsQ.data.failed_missing_symbol > 0 && (
									<div className="flex items-center gap-2">
										<div className="w-2 h-2 bg-red-400 rounded-full" />
										<span className="text-[var(--muted)]">Missing Symbol:</span>
										<span className="text-red-400 font-medium">{positionMetricsQ.data.failed_missing_symbol}</span>
									</div>
								)}
								{positionMetricsQ.data.failed_exception > 0 && (
									<div className="flex items-center gap-2">
										<div className="w-2 h-2 bg-red-400 rounded-full" />
										<span className="text-[var(--muted)]">Exceptions:</span>
										<span className="text-red-400 font-medium">{positionMetricsQ.data.failed_exception}</span>
									</div>
								)}
							</div>
							<div className="text-xs text-[var(--muted)] pt-2 border-t border-[#1e293b]">
								Total Attempts: {positionMetricsQ.data.total_attempts}
							</div>
						</div>
					) : (
						<div className="text-xs sm:text-sm text-[var(--muted)]">
							No position creation attempts yet. Metrics will appear after buy orders execute.
						</div>
					)}
				</div>
			)}

			{/* Positions Without Sell Orders Card (only in broker mode) */}
			{isBrokerMode && (
				<div className="bg-[var(--panel)] border border-yellow-500/30 rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
						<h2 className="text-base sm:text-lg font-semibold text-[var(--text)] flex items-center gap-2">
							<span className="text-yellow-400">⚠️</span>
							Positions Without Sell Orders
						</h2>
						<span className="text-xs sm:text-sm text-[var(--muted)]">Issue #5</span>
					</div>
					{positionsWithoutOrdersQ.isLoading ? (
						<div className="text-xs sm:text-sm text-[var(--muted)]">Loading...</div>
					) : positionsWithoutOrdersError ? (
						<div className="text-xs sm:text-sm text-red-400">
							Error loading positions: {positionsWithoutOrdersError instanceof Error ? positionsWithoutOrdersError.message : 'Unknown error'}
						</div>
					) : positionsWithoutOrders && positionsWithoutOrders.positions.length > 0 ? (
						<div className="space-y-3">
							<div className="text-sm text-yellow-400 font-medium">
								{positionsWithoutOrdersCount} position{positionsWithoutOrdersCount !== 1 ? 's' : ''} without sell orders
							</div>
							<div className="space-y-2 max-h-64 overflow-y-auto">
								{positionsWithoutOrders.positions.slice(0, 10).map((pos, idx) => (
									<div
										key={`${pos.symbol}-${idx}`}
										className="bg-[#1e293b]/50 border border-[#1e293b] rounded p-2 text-xs sm:text-sm"
									>
										<div className="flex items-center justify-between mb-1">
											<span className="font-medium text-[var(--text)]">{pos.symbol}</span>
											<span className="text-[var(--muted)]">
												Qty: {pos.quantity} @ Rs {pos.entry_price.toFixed(2)}
											</span>
										</div>
										<div className="text-yellow-400/80 text-xs mt-1">{pos.reason}</div>
									</div>
								))}
								{positionsWithoutOrders.positions.length > 10 && (
									<div className="text-xs text-[var(--muted)] text-center pt-2">
										+{positionsWithoutOrders.positions.length - 10} more positions
									</div>
								)}
							</div>
							<div className="text-xs text-[var(--muted)] pt-2 border-t border-[#1e293b]">
								Check Telegram alerts or logs for details. System will retry placing orders automatically.
							</div>
						</div>
					) : (
						<div className="text-xs sm:text-sm text-[var(--muted)]">
							✓ All positions have sell orders
						</div>
					)}
				</div>
			)}

			{/* Stats Grid */}
			<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
				{/* Portfolio Value - Only show in paper mode */}
				{isPaperMode && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
						<div className="text-xs sm:text-sm text-[var(--muted)] mb-1">Portfolio Value</div>
						<div className="text-xl sm:text-2xl font-semibold text-[var(--text)]">
							{portfolio ? formatMoney(portfolio.account.total_value) : '—'}
						</div>
						{portfolio && (
							<div
								className={`text-xs sm:text-sm mt-1 ${
									portfolio.account.return_percentage >= 0
										? 'text-green-400'
										: 'text-red-400'
								}`}
							>
								{formatPercent(portfolio.account.return_percentage)}
							</div>
						)}
						<Link
							to="/dashboard/paper-trading"
							className="text-xs text-[var(--accent)] hover:underline mt-2 block min-h-[44px] flex items-center"
						>
							View Portfolio →
						</Link>
					</div>
				)}
				{/* Broker Portfolio Placeholder - Only show in broker mode */}
				{isBrokerMode && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
						<div className="text-xs sm:text-sm text-[var(--muted)] mb-1">Broker Portfolio</div>
						<div className="text-xl sm:text-2xl font-semibold text-[var(--text)]">—</div>
						<div className="text-xs sm:text-sm mt-1 text-[var(--muted)]">
							{isBrokerConnected ? 'Connected' : 'Not Connected'}
						</div>
						<Link
							to="/dashboard/settings"
							className="text-xs text-[var(--accent)] hover:underline mt-2 block min-h-[44px] flex items-center"
						>
							{isBrokerConnected ? 'View Portfolio →' : 'Configure Broker →'}
						</Link>
					</div>
				)}

				{/* Total P&L */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="text-xs sm:text-sm text-[var(--muted)] mb-1">Total P&L</div>
					<div
						className={`text-xl sm:text-2xl font-semibold ${
							pnl && pnl.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
						}`}
					>
						{pnl ? formatMoney(pnl.totalPnl) : '—'}
					</div>
					{pnl && (
						<div className="text-xs sm:text-sm text-[var(--muted)] mt-1">
							{pnl.daysGreen} green / {pnl.daysRed} red days
						</div>
					)}
					<Link
						to="/dashboard/pnl"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block min-h-[44px] flex items-center"
					>
						View P&L →
					</Link>
				</div>

				{/* Active Signals */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="text-xs sm:text-sm text-[var(--muted)] mb-1">Active Signals</div>
					<div className="text-xl sm:text-2xl font-semibold text-[var(--text)]">{activeSignalsCount}</div>
					<div className="text-xs sm:text-sm text-[var(--muted)] mt-1">Ready to trade</div>
					<Link
						to="/dashboard/buying-zone"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block min-h-[44px] flex items-center"
					>
						View Signals →
					</Link>
				</div>

				{/* Open Orders */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="text-xs sm:text-sm text-[var(--muted)] mb-1">Open Orders</div>
					<div className="text-xl sm:text-2xl font-semibold text-[var(--text)]">{openOrdersCount}</div>
					<div className="text-xs sm:text-sm text-[var(--muted)] mt-1">Pending execution</div>
					<Link
						to="/dashboard/orders"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block min-h-[44px] flex items-center"
					>
						View Orders →
					</Link>
				</div>
			</div>

			{/* Portfolio Details & Notifications */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4">
				{/* Portfolio Breakdown - Only show in paper mode */}
				{isPaperMode && portfolio && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
						<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
							<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Portfolio Breakdown</h2>
							<Link
								to="/dashboard/paper-trading"
								className="text-sm text-[var(--accent)] hover:underline min-h-[44px] flex items-center"
							>
								View All →
							</Link>
						</div>
						<div className="space-y-2 sm:space-y-3">
							<div className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-0">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Available Cash</span>
								<span className="text-sm sm:text-base text-[var(--text)] font-medium">
									{formatMoney(portfolio.account.available_cash)}
								</span>
							</div>
							<div className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-0">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Invested Value</span>
								<span className="text-sm sm:text-base text-[var(--text)] font-medium">
									{formatMoney(portfolio.account.portfolio_value)}
								</span>
							</div>
							<div className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-0">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Unrealized P&L</span>
								<span
									className={`text-sm sm:text-base font-medium ${
										portfolio.account.unrealized_pnl >= 0
											? 'text-green-400'
											: 'text-red-400'
									}`}
								>
									{formatMoney(portfolio.account.unrealized_pnl)} (
									{formatPercent(
										(portfolio.account.unrealized_pnl /
											portfolio.account.portfolio_value) *
											100
									)}
									)
								</span>
							</div>
							<div className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-0">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Realized P&L</span>
								<span
									className={`text-sm sm:text-base font-medium ${
										portfolio.account.realized_pnl >= 0
											? 'text-green-400'
											: 'text-red-400'
									}`}
								>
									{formatMoney(portfolio.account.realized_pnl)}
								</span>
							</div>
							<div className="flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-0 pt-2 border-t border-[#1e293b]">
								<span className="text-xs sm:text-sm text-[var(--muted)]">Holdings</span>
								<span className="text-sm sm:text-base text-[var(--text)] font-medium">
									{portfolio.holdings.length} position{portfolio.holdings.length !== 1 ? 's' : ''}
								</span>
							</div>
						</div>
					</div>
				)}

				{/* Charts Section */}
				{portfolio && (
					<>
						{/* P&L Trend Chart */}
						<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
							<PnlTrendChart height={300} />
						</div>

						{/* Portfolio Value Chart */}
						<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
							<PortfolioValueChart height={300} />
						</div>

						{/* Trading Metrics Card */}
						<MetricsCard periodDays={30} />
					</>
				)}

				{/* Quick Actions & Notifications */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
						<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Quick Actions</h2>
						{unreadNotificationsCount > 0 && (
							<Link
								to="/dashboard/notifications"
								className="text-sm text-[var(--accent)] hover:underline flex items-center gap-1 min-h-[44px]"
							>
								<span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
									{unreadNotificationsCount}
								</span>
								unread
							</Link>
						)}
					</div>
					<div className="space-y-2">
						<Link
							to="/dashboard/buying-zone"
							className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
						>
							📊 View Buying Zone
						</Link>
						{isPaperMode && (
							<Link
								to="/dashboard/paper-trading"
								className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
							>
								💼 Paper Trading Portfolio
							</Link>
						)}
						{isBrokerMode && (
							<Link
								to="/dashboard/settings"
								className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
							>
								🏦 Broker Portfolio {!isBrokerConnected && '(Not Connected)'}
							</Link>
						)}
						<Link
							to="/dashboard/orders"
							className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
						>
							📋 View Orders
						</Link>
						<Link
							to="/dashboard/service"
							className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
						>
							⚙️ Service Status
						</Link>
						<Link
							to="/dashboard/trading-config"
							className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
						>
							🔧 Trading Configuration
						</Link>
						{unreadNotificationsCount > 0 && (
							<Link
								to="/dashboard/notifications"
								className="block p-3 sm:p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)] text-sm sm:text-base min-h-[44px] flex items-center active:bg-[var(--hover)] transition-colors"
							>
								🔔 Notifications ({unreadNotificationsCount})
							</Link>
						)}
					</div>
				</div>
			</div>

			{/* Recent Holdings Preview - Only show in paper mode */}
			{isPaperMode && portfolio && portfolio.holdings.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-0 mb-3 sm:mb-4">
						<h2 className="text-base sm:text-lg font-semibold text-[var(--text)]">Top Holdings</h2>
						<Link
							to="/dashboard/paper-trading"
							className="text-sm text-[var(--accent)] hover:underline min-h-[44px] flex items-center"
						>
							View All →
						</Link>
					</div>
					{/* Mobile Card View */}
					<div className="block sm:hidden space-y-3">
						{portfolio.holdings.slice(0, 5).map((holding) => (
							<div
								key={holding.symbol}
								className="bg-[var(--bg)] border border-[#1e293b]/50 rounded-lg p-3 space-y-2"
							>
								<div className="flex items-center justify-between">
									<span className="text-sm font-semibold text-[var(--text)]">
										{holding.symbol}
									</span>
									<span className="text-xs text-[var(--muted)]">Qty: {holding.quantity}</span>
								</div>
								<div className="grid grid-cols-2 gap-2 text-xs">
									<div>
										<span className="text-[var(--muted)]">Avg:</span>{' '}
										<span className="text-[var(--text)]">
											{formatMoney(holding.average_price)}
										</span>
									</div>
									<div>
										<span className="text-[var(--muted)]">Current:</span>{' '}
										<span className="text-[var(--text)]">
											{formatMoney(holding.current_price)}
										</span>
									</div>
									<div>
										<span className="text-[var(--muted)]">P&L:</span>{' '}
										<span
											className={
												holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}
										>
											{formatMoney(holding.pnl)}
										</span>
									</div>
									<div>
										<span className="text-[var(--muted)]">P&L%:</span>{' '}
										<span
											className={
												holding.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'
											}
										>
											{formatPercent(holding.pnl_percentage)}
										</span>
									</div>
								</div>
							</div>
						))}
					</div>
					{/* Desktop Table View */}
					<div className="hidden sm:block overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-[#1e293b] text-left text-[var(--muted)]">
									<th className="pb-2 text-xs sm:text-sm">Symbol</th>
									<th className="pb-2 text-xs sm:text-sm">Quantity</th>
									<th className="pb-2 text-xs sm:text-sm">Avg Price</th>
									<th className="pb-2 text-xs sm:text-sm">Current</th>
									<th className="pb-2 text-xs sm:text-sm">P&L</th>
									<th className="pb-2 text-xs sm:text-sm">P&L %</th>
								</tr>
							</thead>
							<tbody>
								{portfolio.holdings.slice(0, 5).map((holding) => (
									<tr key={holding.symbol} className="border-b border-[#1e293b]/50">
										<td className="py-2 text-xs sm:text-sm text-[var(--text)] font-medium">
											{holding.symbol}
										</td>
										<td className="py-2 text-xs sm:text-sm text-[var(--text)]">
											{holding.quantity}
										</td>
										<td className="py-2 text-xs sm:text-sm text-[var(--text)]">
											{formatMoney(holding.average_price)}
										</td>
										<td className="py-2 text-xs sm:text-sm text-[var(--text)]">
											{formatMoney(holding.current_price)}
										</td>
										<td
											className={`py-2 text-xs sm:text-sm ${
												holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatMoney(holding.pnl)}
										</td>
										<td
											className={`py-2 text-xs sm:text-sm ${
												holding.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatPercent(holding.pnl_percentage)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</div>
			)}
		</div>
	);
}
