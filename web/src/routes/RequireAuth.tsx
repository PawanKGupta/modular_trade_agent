import { ReactNode, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useSessionStore } from '@/state/sessionStore';

export function RequireAuth({ children }: { children: ReactNode }) {
	const isAuthenticated = useSessionStore((s) => s.isAuthenticated);
	const hasHydrated = useSessionStore((s) => s.hasHydrated);
	const initialize = useSessionStore((s) => s.initialize);

	useEffect(() => {
		if (!hasHydrated) {
			void initialize();
		}
	}, [hasHydrated, initialize]);

	if (!hasHydrated) {
		return (
			<div className="p-2 sm:p-4 text-xs sm:text-sm text-gray-500" role="status" aria-live="polite">
				Restoring session...
			</div>
		);
	}

	if (!isAuthenticated) {
		return <Navigate to="/login" replace />;
	}

	return children;
}
