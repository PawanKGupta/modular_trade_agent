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
				<div className="font-semibold mb-3">Trade Agent</div>
				<nav className="flex flex-col gap-2 text-sm">
					<Link to="/dashboard">Overview</Link>
					<Link to="/dashboard/buying-zone">Buying Zone</Link>
					<Link to="/dashboard/orders">Orders</Link>
					<Link to="/dashboard/pnl">PnL</Link>
					<Link to="/dashboard/targets">Targets</Link>
					<Link to="/dashboard/activity">Activity</Link>
					<Link to="/dashboard/settings">Settings</Link>
					{isAdmin && <Link to="/dashboard/admin/users">Admin • Users</Link>}
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
