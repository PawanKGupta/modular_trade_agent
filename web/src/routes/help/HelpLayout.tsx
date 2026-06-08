import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';
import { BrandMark } from '@/components/BrandMark';
import { useSessionStore } from '@/state/sessionStore';
import { HELP_NAV_ITEMS, helpPath } from './helpNav';

const NAV_LINK_CLASS =
	'relative block px-3 py-2 rounded-md text-sm transition-colors min-h-[44px] flex flex-col justify-center focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--panel)]';

/**
 * Public help center shell at `/help/*` (no login required).
 * Logged-in users see a shortcut back to the dashboard.
 */
export function HelpLayout() {
	const location = useLocation();
	const user = useSessionStore((s) => s.user);
	const [sidebarOpen, setSidebarOpen] = useState(false);

	useEffect(() => {
		setSidebarOpen(false);
	}, [location.pathname]);

	const isActive = (slug: string) => {
		const path = helpPath(slug);
		return slug === '' ? location.pathname === '/help' : location.pathname === path;
	};

	return (
		<div className="min-h-screen flex flex-col lg:grid lg:grid-cols-[260px_1fr] bg-[var(--bg)]">
			<button
				type="button"
				onClick={() => setSidebarOpen(!sidebarOpen)}
				className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-[var(--panel)] border border-[#1e293b]/50 text-[var(--text)] min-h-[44px] min-w-[44px] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
				aria-label="Toggle help menu"
			>
				☰
			</button>

			<aside
				className={clsx(
					'fixed lg:static inset-y-0 left-0 z-40 w-[260px] bg-[var(--panel)] border-r border-[#1e293b]/50 flex flex-col transform transition-transform lg:translate-x-0',
					sidebarOpen ? 'translate-x-0' : '-translate-x-full',
				)}
			>
				<div className="p-4 sm:p-6 border-b border-[#1e293b]/50">
					<BrandMark />
					<p className="text-xs text-[var(--muted)] mt-2">User guide</p>
				</div>
				<nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
					{HELP_NAV_ITEMS.map((item) => {
						const active = isActive(item.slug);
						return (
							<Link
								key={item.slug || 'home'}
								to={helpPath(item.slug)}
								onClick={() => setSidebarOpen(false)}
								className={clsx(
									NAV_LINK_CLASS,
									active
										? 'bg-[var(--accent)]/20 text-[var(--accent)] shadow-sm'
										: 'text-[var(--text)]/80 hover:bg-[#1e293b]/50 hover:text-[var(--text)]',
								)}
							>
								{active ? (
									<div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-[var(--accent)] rounded-r-full" />
								) : null}
								<span className="font-medium">{item.title}</span>
								<span className="text-xs text-[var(--muted)] mt-0.5 line-clamp-2">{item.description}</span>
							</Link>
						);
					})}
				</nav>
				<div className="p-3 border-t border-[#1e293b]/50 space-y-2 text-sm">
					{user ? (
						<Link
							to="/dashboard"
							className="block text-center py-2 rounded bg-[var(--accent)] text-black font-medium min-h-[44px] flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--panel)]"
						>
							Back to dashboard
						</Link>
					) : (
						<>
							<Link
								to="/login"
								className="block text-center py-2 rounded bg-[var(--accent)] text-black font-medium min-h-[44px] flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:ring-offset-2 focus:ring-offset-[var(--panel)]"
							>
								Log in
							</Link>
							<Link
								to="/signup"
								className="block text-center text-[var(--accent)] text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 rounded-sm"
							>
								Create account
							</Link>
						</>
					)}
				</div>
			</aside>

			{sidebarOpen ? (
				<button
					type="button"
					className="fixed inset-0 z-30 bg-black/50 lg:hidden"
					aria-label="Close help menu"
					onClick={() => setSidebarOpen(false)}
				/>
			) : null}

			<main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 pt-16 lg:pt-8">
				<Outlet />
			</main>
		</div>
	);
}
