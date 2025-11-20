import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useSessionStore } from '@/state/sessionStore';

export function AppShell() {
	const location = useLocation();
	const navigate = useNavigate();
	const { user, isAdmin, logout, refresh } = useSessionStore();

	useEffect(() => {
		// Ensure we load profile on first mount
		refresh().catch(() => {});
	}, [location.pathname]);

	return (
		<div className="min-h-screen grid grid-cols-[240px_1fr]">
			<aside className="bg-[var(--panel)] p-4">
				<div className="font-semibold mb-3 text-[var(--text)]">Trade Agent</div>
				<nav className="flex flex-col gap-2 text-sm">
					<Link to="/dashboard" className="text-[var(--text)] hover:text-[var(--accent)]">Overview</Link>
					<Link to="/dashboard/buying-zone" className="text-[var(--text)] hover:text-[var(--accent)]">Buying Zone</Link>
					<Link to="/dashboard/orders" className="text-[var(--text)] hover:text-[var(--accent)]">Orders</Link>
					<Link to="/dashboard/paper-trading" className="text-[var(--text)] hover:text-[var(--accent)]">Paper Trading</Link>
					<Link to="/dashboard/pnl" className="text-[var(--text)] hover:text-[var(--accent)]">PnL</Link>
					<Link to="/dashboard/targets" className="text-[var(--text)] hover:text-[var(--accent)]">Targets</Link>
					<Link to="/dashboard/activity" className="text-[var(--text)] hover:text-[var(--accent)]">Activity</Link>
					<Link to="/dashboard/service" className="text-[var(--text)] hover:text-[var(--accent)]">Service Status</Link>
					<Link to="/dashboard/logs" className="text-[var(--text)] hover:text-[var(--accent)]">Logs</Link>
					<Link to="/dashboard/trading-config" className="text-[var(--text)] hover:text-[var(--accent)]">Trading Config</Link>
					<Link to="/dashboard/settings" className="text-[var(--text)] hover:text-[var(--accent)]">Settings</Link>
					{isAdmin && (
						<>
							<Link to="/dashboard/admin/users" className="text-[var(--text)] hover:text-[var(--accent)]">Admin - Users</Link>
							<Link to="/dashboard/admin/ml" className="text-[var(--text)] hover:text-[var(--accent)]">Admin - ML Training</Link>
							<Link to="/dashboard/admin/schedules" className="text-[var(--text)] hover:text-[var(--accent)]">Admin - Schedules</Link>
						</>
					)}
				</nav>
			</aside>
			<main className="p-6">
				<div className="flex items-center justify-between mb-6">
					<div className="text-sm text-[var(--muted)]">{user?.email}</div>
					<button onClick={() => { logout(); navigate('/login'); }} className="text-sm text-[var(--accent)]">Logout</button>
				</div>
				<Outlet />
			</main>
		</div>
	);
}
