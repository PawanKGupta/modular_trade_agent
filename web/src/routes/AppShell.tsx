import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSessionStore } from '@/state/sessionStore';
import { getNotificationCount } from '@/api/notifications';
import { clsx } from 'clsx';
import { ReboundLogo } from '@/components/ReboundLogo';
import { useSettings } from '@/hooks/useSettings';

interface NavItem {
	path: string;
	label: string;
	icon: string;
	isSubItem?: boolean;
	badge?: number;
}

interface NavGroup {
	title?: string;
	items: NavItem[];
}

export function AppShell() {
	const location = useLocation();
	const navigate = useNavigate();
	const { user, isAdmin, logout, refresh } = useSessionStore();

	const { data: notificationCount } = useQuery({
		queryKey: ['notificationCount'],
		queryFn: getNotificationCount,
		refetchInterval: 30000, // Refetch every 30 seconds
	});

	// Get user settings to determine trade mode
	const { isPaperMode, isBrokerMode, broker, isBrokerConnected } = useSettings();

	// Load expanded groups from localStorage, default only Overview expanded
	const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
		if (typeof window !== 'undefined') {
			const saved = localStorage.getItem('navExpandedGroups');
			if (saved) {
				try {
					return new Set(JSON.parse(saved));
				} catch {
					// If parsing fails, default to only Overview expanded
				}
			}
		}
		// Default: only Overview expanded, all others collapsed
		return new Set(['Overview']);
	});

	useEffect(() => {
		// Ensure we load profile on first mount
		refresh().catch(() => {});
	}, [location.pathname]);

	const toggleGroup = (groupTitle: string) => {
		setExpandedGroups((prev) => {
			const newSet = new Set(prev);
			if (newSet.has(groupTitle)) {
				newSet.delete(groupTitle);
			} else {
				newSet.add(groupTitle);
			}
			localStorage.setItem('navExpandedGroups', JSON.stringify(Array.from(newSet)));
			return newSet;
		});
	};

	const isActive = (path: string) => {
		if (path === '/dashboard') {
			return location.pathname === '/dashboard';
		}
		return location.pathname.startsWith(path);
	};

	// Build navigation groups with conditional items based on trade mode
	const navGroups: NavGroup[] = useMemo(() => {
		const tradingItems: NavItem[] = [
			{ path: '/dashboard/buying-zone', label: 'Buying Zone', icon: '🎯' },
			{ path: '/dashboard/orders', label: 'Orders', icon: '📦' },
		];

		// Show paper trading items in paper mode, broker portfolio in broker mode
		if (isPaperMode) {
			tradingItems.push(
				{ path: '/dashboard/paper-trading', label: 'Paper Trading', icon: '📝' },
				{ path: '/dashboard/paper-trading-history', label: 'Trade History', icon: '📜', isSubItem: true }
			);
		} else if (isBrokerMode) {
			tradingItems.push(
				{ path: '/dashboard/broker-portfolio', label: 'Broker Portfolio', icon: '🏦' },
				{ path: '/dashboard/broker-orders', label: 'Broker Orders', icon: '📋' }
			);
		}

		tradingItems.push(
			{ path: '/dashboard/pnl', label: 'PnL', icon: '💰' },
			{ path: '/dashboard/targets', label: 'Targets', icon: '🎪' }
		);

		return [
			{
				title: 'Overview',
				items: [{ path: '/dashboard', label: 'Dashboard', icon: '📊' }],
			},
			{
				title: 'Trading',
				items: tradingItems,
			},
		{
			title: 'System',
			items: [
				{ path: '/dashboard/service', label: 'Service Status', icon: '⚡' },
			],
		},
		{
			title: 'Settings',
			items: [
				{ path: '/dashboard/trading-config', label: 'Trading Config', icon: '⚙️' },
				{ path: '/dashboard/settings', label: 'Broker Settings', icon: '🔧' },
				{ path: '/dashboard/notification-preferences', label: 'Notification Settings', icon: '🔕' },
			],
		},
		{
			title: 'Logs',
			items: [
				{ path: '/dashboard/logs', label: 'System Logs', icon: '📄' },
				{ path: '/dashboard/activity', label: 'Activity Log', icon: '📋' },
			],
		},
		{
			title: 'Notifications',
			items: [
				{ path: '/dashboard/notifications', label: 'Notifications', icon: '🔔', badge: notificationCount?.unread_count },
			],
		},
		];
	}, [isPaperMode, notificationCount?.unread_count]);

	const adminItems: NavItem[] = [
		{ path: '/dashboard/admin/users', label: 'Users', icon: '👥' },
		{ path: '/dashboard/admin/ml', label: 'ML Training', icon: '🤖' },
		{ path: '/dashboard/admin/schedules', label: 'Schedules', icon: '📅' },
	];

	// Auto-expand group if current page is in it
	useEffect(() => {
		navGroups.forEach((group) => {
			if (group.items.some((item) => isActive(item.path))) {
				setExpandedGroups((prev) => {
					if (!prev.has(group.title || '')) {
						const newSet = new Set(prev);
						newSet.add(group.title || '');
						localStorage.setItem('navExpandedGroups', JSON.stringify(Array.from(newSet)));
						return newSet;
					}
					return prev;
				});
			}
		});
		// Also check admin items
		if (isAdmin && adminItems.some((item) => isActive(item.path))) {
			setExpandedGroups((prev) => {
				if (!prev.has('Administration')) {
					const newSet = new Set(prev);
					newSet.add('Administration');
					localStorage.setItem('navExpandedGroups', JSON.stringify(Array.from(newSet)));
					return newSet;
				}
				return prev;
			});
		}
	}, [location.pathname, isAdmin]);

	const [sidebarOpen, setSidebarOpen] = useState(false);

	return (
		<div className="min-h-screen flex flex-col sm:grid sm:grid-cols-[260px_1fr]">
			{/* Mobile Menu Button */}
			<button
				onClick={() => setSidebarOpen(!sidebarOpen)}
				className="sm:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-[var(--panel)] border border-[#1e293b]/50 text-[var(--text)] hover:bg-[#1e293b]/50 transition-colors"
				aria-label="Toggle menu"
			>
				<span className="text-xl">{sidebarOpen ? '✕' : '☰'}</span>
			</button>

			{/* Mobile Overlay */}
			{sidebarOpen && (
				<div
					className="sm:hidden fixed inset-0 bg-black/50 z-40"
					onClick={() => setSidebarOpen(false)}
				/>
			)}

			<aside
				className={clsx(
					'bg-[var(--panel)] border-r border-[#1e293b]/50 flex flex-col h-screen fixed sm:sticky top-0 z-40 transition-transform duration-300',
					'sm:translate-x-0',
					sidebarOpen ? 'translate-x-0' : '-translate-x-full sm:translate-x-0',
					'w-[260px]'
				)}
			>
				{/* Logo/Brand Section */}
				<div className="p-4 sm:p-6 border-b border-[#1e293b]/50">
					<div className="flex items-center gap-3">
						<div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--accent)]/10 to-blue-600/10 flex items-center justify-center p-1.5 border border-[var(--accent)]/20 hover:border-[var(--accent)]/40 transition-colors">
							<ReboundLogo size={28} variant="full" />
						</div>
						<div>
							<div className="font-semibold text-sm sm:text-base text-[var(--text)] leading-tight">Rebound</div>
							<div className="text-xs text-[var(--muted)]">Modular Trade Agent</div>
						</div>
					</div>
				</div>

				{/* Navigation */}
				<nav className="flex-1 overflow-y-auto overflow-x-hidden p-2 space-y-0 scroll-smooth">
					{navGroups.map((group, groupIdx) => {
						const isExpanded = expandedGroups.has(group.title || '');
						const hasItems = group.items.length > 0;

						return (
							<div key={groupIdx} className="space-y-0">
								{group.title && (
									<button
										onClick={() => toggleGroup(group.title!)}
										disabled={!hasItems}
										className={clsx(
											'w-full flex items-center justify-between px-2 py-2 sm:py-1 rounded-md text-xs font-semibold text-[var(--muted)] uppercase tracking-wider',
											'hover:bg-[#1e293b]/30 transition-colors duration-150 min-h-[44px] sm:min-h-0',
											!hasItems && 'cursor-default'
										)}
									>
										<span>{group.title}</span>
										{hasItems && (
											<span className={clsx(
												'text-[var(--muted)] transition-transform duration-200',
												isExpanded && 'rotate-90'
											)}>
												▶
											</span>
										)}
									</button>
								)}
								{isExpanded && (
									<div className="space-y-0">
										{group.items.map((item) => {
											const active = isActive(item.path);
											return (
												<Link
													key={item.path}
													to={item.path}
													onClick={() => setSidebarOpen(false)}
													className={clsx(
														'flex items-center gap-2 px-2 py-2.5 sm:py-1.5 rounded-md text-sm font-medium transition-all duration-200',
														'relative group focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--panel)]',
														'min-h-[44px] sm:min-h-0',
														item.isSubItem && 'ml-5',
														active
															? 'bg-[var(--accent)]/20 text-[var(--accent)] shadow-sm'
															: 'text-[var(--text)]/80 hover:bg-[#1e293b]/50 hover:text-[var(--text)]'
													)}
												>
													{/* Active indicator bar */}
													{active && (
														<div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[var(--accent)] rounded-r-full" />
													)}

													<span className="text-sm flex-shrink-0 transition-transform duration-200 group-hover:scale-110">
														{item.icon}
													</span>
													<span className="flex-1">{item.label}</span>

													{item.badge !== undefined && item.badge > 0 && (
														<span className="px-1.5 py-0.5 text-xs font-semibold rounded-full bg-red-500/90 text-white min-w-[18px] text-center animate-pulse">
															{item.badge > 99 ? '99+' : item.badge}
														</span>
													)}
												</Link>
											);
										})}
									</div>
								)}
							</div>
						);
					})}

					{isAdmin && (
						<>
							<div className="h-px bg-[#1e293b]/50 my-1 mx-2" />
							<div className="space-y-0">
								<button
									onClick={() => toggleGroup('Administration')}
									className={clsx(
										'w-full flex items-center justify-between px-2 py-2 sm:py-1 rounded-md text-xs font-semibold text-[var(--muted)] uppercase tracking-wider',
										'hover:bg-[#1e293b]/30 transition-colors duration-150 min-h-[44px] sm:min-h-0'
									)}
								>
									<span>Administration</span>
									<span className={clsx(
										'text-[var(--muted)] transition-transform duration-200',
										expandedGroups.has('Administration') && 'rotate-90'
									)}>
										▶
									</span>
								</button>
								{expandedGroups.has('Administration') && (
									<div className="space-y-0">
										{adminItems.map((item) => {
											const active = isActive(item.path);
											return (
												<Link
													key={item.path}
													to={item.path}
													onClick={() => setSidebarOpen(false)}
													className={clsx(
														'flex items-center gap-2 px-2 py-2.5 sm:py-1.5 rounded-md text-sm font-medium transition-all duration-200',
														'relative group focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--panel)]',
														'min-h-[44px] sm:min-h-0',
														active
															? 'bg-[var(--accent)]/20 text-[var(--accent)] shadow-sm'
															: 'text-[var(--text)]/80 hover:bg-[#1e293b]/50 hover:text-[var(--text)]'
													)}
												>
													{active && (
														<div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[var(--accent)] rounded-r-full" />
													)}
													<span className="text-sm flex-shrink-0 transition-transform duration-200 group-hover:scale-110">
														{item.icon}
													</span>
													<span className="flex-1">{item.label}</span>
												</Link>
											);
										})}
									</div>
								)}
							</div>
						</>
					)}
				</nav>

				{/* User Section */}
				<div className="p-3 sm:p-4 border-t border-[#1e293b]/50">
					<div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#1e293b]/30 hover:bg-[#1e293b]/50 transition-colors group">
						<div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--accent)] to-blue-600 flex items-center justify-center text-sm font-semibold text-white shadow-lg flex-shrink-0">
							{user?.email?.charAt(0).toUpperCase() || 'U'}
						</div>
						<div className="flex-1 min-w-0">
							<div className="text-xs sm:text-sm font-medium text-[var(--text)] truncate">
								{user?.email || 'User'}
							</div>
							<div className="text-xs text-[var(--muted)] flex items-center gap-1">
								<span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
								Active
							</div>
						</div>
						<button
							onClick={() => {
								logout();
								navigate('/login');
							}}
							className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 px-3 py-2 sm:py-1.5 text-xs font-medium rounded-md bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-500/50 min-h-[36px] sm:min-h-0"
							title="Logout"
						>
							Logout
						</button>
					</div>
				</div>
			</aside>
			<main className="bg-[var(--bg)] min-h-screen flex-1 sm:flex-none">
				<div className="sticky top-0 z-10 bg-[var(--bg)]/80 backdrop-blur-sm border-b border-[#1e293b]/50 px-3 sm:px-6 py-3 sm:py-4">
					<div className="flex items-center justify-between gap-2 sm:gap-4">
						{/* Mode Badge */}
						<div className="flex items-center gap-2">
							{isPaperMode && (
								<div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-500/20 border border-blue-500/30">
									<div className="w-2 h-2 bg-blue-400 rounded-full" />
									<span className="text-xs text-blue-400 font-medium">Paper Mode</span>
								</div>
							)}
							{isBrokerMode && (
								<div
									className={`flex items-center gap-1.5 px-2.5 py-1 rounded border ${
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
										{broker ? broker.toUpperCase() : 'Broker'} {isBrokerConnected ? '✓' : '⚠'}
									</span>
								</div>
							)}
						</div>
						<div className="flex items-center gap-2 sm:gap-4">
							<Link
								to="/dashboard/notifications"
								className="relative p-2.5 sm:p-2 rounded-lg hover:bg-[#1e293b]/50 transition-colors text-[var(--text)]/80 hover:text-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--bg)] min-h-[44px] sm:min-h-0 flex items-center justify-center"
								title="Notifications"
							>
								<span className="text-lg sm:text-xl">🔔</span>
								{notificationCount && notificationCount.unread_count > 0 && (
									<span className="absolute top-0 right-0 px-1.5 py-0.5 text-xs font-semibold rounded-full bg-red-500 text-white min-w-[18px] text-center animate-pulse">
										{notificationCount.unread_count > 99 ? '99+' : notificationCount.unread_count}
									</span>
								)}
							</Link>
						</div>
					</div>
				</div>
				<div className="p-0 sm:p-6">
					<Outlet />
				</div>
			</main>
		</div>
	);
}
