import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getServiceStatus, type ServiceStatus } from '../../api/service';
import { getPaperTradingPortfolio, type PaperTradingPortfolio } from '../../api/paper-trading';
import { getPnlSummary, type PnlSummary } from '../../api/pnl';
import { getBuyingZone } from '../../api/signals';
import { listOrders } from '../../api/orders';
import { getNotificationCount } from '../../api/notifications';

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

	// Fetch all dashboard data
	const serviceStatusQ = useQuery<ServiceStatus>({
		queryKey: ['service-status'],
		queryFn: getServiceStatus,
		refetchInterval: 15000, // Refresh every 15 seconds
	});

	const portfolioQ = useQuery<PaperTradingPortfolio>({
		queryKey: ['paper-trading-portfolio'],
		queryFn: getPaperTradingPortfolio,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	const pnlQ = useQuery<PnlSummary>({
		queryKey: ['pnl-summary'],
		queryFn: getPnlSummary,
		refetchInterval: 30000,
	});

	const signalsQ = useQuery({
		queryKey: ['signals-count'],
		queryFn: async () => {
			const signals = await getBuyingZone(100, null, 'active');
			return signals.length;
		},
		refetchInterval: 60000, // Refresh every minute
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

	const serviceStatus = serviceStatusQ.data;
	const portfolio = portfolioQ.data;
	const pnl = pnlQ.data;
	const activeSignalsCount = signalsQ.data ?? 0;
	const openOrdersCount = ordersQ.data ?? 0;
	const unreadNotificationsCount = notificationsQ.data ?? 0;

	const isLoading =
		serviceStatusQ.isLoading ||
		portfolioQ.isLoading ||
		pnlQ.isLoading ||
		signalsQ.isLoading ||
		ordersQ.isLoading ||
		notificationsQ.isLoading;

	if (isLoading) {
		return (
			<div className="p-4">
				<div className="text-[var(--text)]">Loading dashboard...</div>
			</div>
		);
	}

	return (
		<div className="p-4 space-y-6">
			{/* Header */}
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-semibold text-[var(--text)]">Dashboard</h1>
				<div className="flex items-center gap-2">
					<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
					<span className="text-xs text-[var(--muted)]">Live</span>
				</div>
			</div>

			{/* Service Status Card */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-lg font-semibold text-[var(--text)]">Service Status</h2>
					<Link
						to="/dashboard/service"
						className="text-sm text-[var(--accent)] hover:underline"
					>
						View Details →
					</Link>
				</div>
				<div className="flex items-center gap-4">
					<div className="flex items-center gap-2">
						<div
							className={`w-3 h-3 rounded-full ${
								serviceStatus?.service_running ? 'bg-green-500' : 'bg-red-500'
							}`}
						/>
						<span className="text-[var(--text)]">
							{serviceStatus?.service_running ? 'Running' : 'Stopped'}
						</span>
					</div>
					{serviceStatus?.last_heartbeat && (
						<span className="text-sm text-[var(--muted)]">
							Last heartbeat: {formatTimeAgo(serviceStatus.last_heartbeat)}
						</span>
					)}
					{serviceStatus && serviceStatus.error_count > 0 && (
						<span className="text-sm text-red-400">
							{serviceStatus.error_count} error{serviceStatus.error_count !== 1 ? 's' : ''}
						</span>
					)}
				</div>
			</div>

			{/* Stats Grid */}
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
				{/* Portfolio Value */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="text-sm text-[var(--muted)] mb-1">Portfolio Value</div>
					<div className="text-2xl font-semibold text-[var(--text)]">
						{portfolio ? formatMoney(portfolio.account.total_value) : '—'}
					</div>
					{portfolio && (
						<div
							className={`text-sm mt-1 ${
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
						className="text-xs text-[var(--accent)] hover:underline mt-2 block"
					>
						View Portfolio →
					</Link>
				</div>

				{/* Total P&L */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="text-sm text-[var(--muted)] mb-1">Total P&L</div>
					<div
						className={`text-2xl font-semibold ${
							pnl && pnl.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
						}`}
					>
						{pnl ? formatMoney(pnl.totalPnl) : '—'}
					</div>
					{pnl && (
						<div className="text-sm text-[var(--muted)] mt-1">
							{pnl.daysGreen} green / {pnl.daysRed} red days
						</div>
					)}
					<Link
						to="/dashboard/pnl"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block"
					>
						View P&L →
					</Link>
				</div>

				{/* Active Signals */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="text-sm text-[var(--muted)] mb-1">Active Signals</div>
					<div className="text-2xl font-semibold text-[var(--text)]">{activeSignalsCount}</div>
					<div className="text-sm text-[var(--muted)] mt-1">Ready to trade</div>
					<Link
						to="/dashboard/buying-zone"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block"
					>
						View Signals →
					</Link>
				</div>

				{/* Open Orders */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="text-sm text-[var(--muted)] mb-1">Open Orders</div>
					<div className="text-2xl font-semibold text-[var(--text)]">{openOrdersCount}</div>
					<div className="text-sm text-[var(--muted)] mt-1">Pending execution</div>
					<Link
						to="/dashboard/orders"
						className="text-xs text-[var(--accent)] hover:underline mt-2 block"
					>
						View Orders →
					</Link>
				</div>
			</div>

			{/* Portfolio Details & Notifications */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
				{/* Portfolio Breakdown */}
				{portfolio && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
						<div className="flex items-center justify-between mb-4">
							<h2 className="text-lg font-semibold text-[var(--text)]">Portfolio Breakdown</h2>
							<Link
								to="/dashboard/paper-trading"
								className="text-sm text-[var(--accent)] hover:underline"
							>
								View All →
							</Link>
						</div>
						<div className="space-y-3">
							<div className="flex justify-between">
								<span className="text-[var(--muted)]">Available Cash</span>
								<span className="text-[var(--text)] font-medium">
									{formatMoney(portfolio.account.available_cash)}
								</span>
							</div>
							<div className="flex justify-between">
								<span className="text-[var(--muted)]">Invested Value</span>
								<span className="text-[var(--text)] font-medium">
									{formatMoney(portfolio.account.portfolio_value)}
								</span>
							</div>
							<div className="flex justify-between">
								<span className="text-[var(--muted)]">Unrealized P&L</span>
								<span
									className={`font-medium ${
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
							<div className="flex justify-between">
								<span className="text-[var(--muted)]">Realized P&L</span>
								<span
									className={`font-medium ${
										portfolio.account.realized_pnl >= 0
											? 'text-green-400'
											: 'text-red-400'
									}`}
								>
									{formatMoney(portfolio.account.realized_pnl)}
								</span>
							</div>
							<div className="flex justify-between pt-2 border-t border-[#1e293b]">
								<span className="text-[var(--muted)]">Holdings</span>
								<span className="text-[var(--text)] font-medium">
									{portfolio.holdings.length} position{portfolio.holdings.length !== 1 ? 's' : ''}
								</span>
							</div>
						</div>
					</div>
				)}

				{/* Quick Actions & Notifications */}
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="flex items-center justify-between mb-4">
						<h2 className="text-lg font-semibold text-[var(--text)]">Quick Actions</h2>
						{unreadNotificationsCount > 0 && (
							<Link
								to="/dashboard/notifications"
								className="text-sm text-[var(--accent)] hover:underline flex items-center gap-1"
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
							className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
						>
							📊 View Buying Zone
						</Link>
						<Link
							to="/dashboard/paper-trading"
							className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
						>
							💼 Paper Trading Portfolio
						</Link>
						<Link
							to="/dashboard/orders"
							className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
						>
							📋 View Orders
						</Link>
						<Link
							to="/dashboard/service"
							className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
						>
							⚙️ Service Status
						</Link>
						<Link
							to="/dashboard/trading-config"
							className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
						>
							🔧 Trading Configuration
						</Link>
						{unreadNotificationsCount > 0 && (
							<Link
								to="/dashboard/notifications"
								className="block p-2 bg-[var(--bg)] rounded hover:bg-[var(--hover)] text-[var(--text)]"
							>
								🔔 Notifications ({unreadNotificationsCount})
							</Link>
						)}
					</div>
				</div>
			</div>

			{/* Recent Holdings Preview */}
			{portfolio && portfolio.holdings.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
					<div className="flex items-center justify-between mb-4">
						<h2 className="text-lg font-semibold text-[var(--text)]">Top Holdings</h2>
						<Link
							to="/dashboard/paper-trading"
							className="text-sm text-[var(--accent)] hover:underline"
						>
							View All →
						</Link>
					</div>
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-[#1e293b] text-left text-[var(--muted)]">
									<th className="pb-2">Symbol</th>
									<th className="pb-2">Quantity</th>
									<th className="pb-2">Avg Price</th>
									<th className="pb-2">Current</th>
									<th className="pb-2">P&L</th>
									<th className="pb-2">P&L %</th>
								</tr>
							</thead>
							<tbody>
								{portfolio.holdings.slice(0, 5).map((holding) => (
									<tr key={holding.symbol} className="border-b border-[#1e293b]/50">
										<td className="py-2 text-[var(--text)] font-medium">{holding.symbol}</td>
										<td className="py-2 text-[var(--text)]">{holding.quantity}</td>
										<td className="py-2 text-[var(--text)]">
											{formatMoney(holding.average_price)}
										</td>
										<td className="py-2 text-[var(--text)]">
											{formatMoney(holding.current_price)}
										</td>
										<td
											className={`py-2 ${
												holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatMoney(holding.pnl)}
										</td>
										<td
											className={`py-2 ${
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
