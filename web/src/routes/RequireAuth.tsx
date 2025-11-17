import { ReactNode, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useSessionStore } from '@/state/sessionStore';

export function RequireAuth({ children }: { children: ReactNode }) {
	const { isAuthenticated, hasHydrated, initialize } = useSessionStore((s) => ({
		isAuthenticated: s.isAuthenticated,
		hasHydrated: s.hasHydrated,
		initialize: s.initialize,
	}));

	useEffect(() => {
		if (!hasHydrated) {
			void initialize();
		}
	}, [hasHydrated, initialize]);

	if (!hasHydrated) {
		return (
			<div className="p-4 text-sm text-gray-500" role="status" aria-live="polite">
				Restoring session...
			</div>
		);
	}

	if (!isAuthenticated) {
		return <Navigate to="/login" replace />;
	}

	return children;
}
