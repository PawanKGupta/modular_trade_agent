import { create } from 'zustand';
import { me, logout as apiLogout, type MeResponse } from '@/api/auth';
import {
	clearAuthTokens,
	getAccessToken,
	getRefreshToken,
	requestTokenRefresh,
} from '@/api/client';

/** Treat missing email_verified as verified (legacy API / cached sessions). */
function normalizeMe(profile: MeResponse): MeResponse {
	return {
		...profile,
		email_verified: profile.email_verified ?? true,
	};
}

type SessionState = {
	isAuthenticated: boolean;
	user: MeResponse | null;
	isAdmin: boolean;
	hasHydrated: boolean;
	setSession: (user: MeResponse | null) => void;
	refresh: () => Promise<void>;
	initialize: () => Promise<void>;
	logout: () => void;
};

let initializePromise: Promise<void> | null = null;

export const useSessionStore = create<SessionState>((set, get) => ({
	isAuthenticated: false,
	user: null,
	isAdmin: false,
	hasHydrated: false,
	setSession: (user) =>
		set({
			user: user ? normalizeMe(user) : null,
			isAuthenticated: !!user,
			isAdmin: !!user?.roles?.includes('admin'),
			hasHydrated: true,
		}),
	refresh: async () => {
		try {
			const profile = normalizeMe(await me());
			set({
				user: profile,
				isAuthenticated: true,
				isAdmin: !!profile.roles?.includes('admin'),
				hasHydrated: true,
			});
		} catch (error) {
			clearAuthTokens();
			set({ user: null, isAuthenticated: false, isAdmin: false, hasHydrated: true });
			throw error;
		}
	},
	initialize: async () => {
		if (get().hasHydrated) return;
		if (initializePromise) {
			return initializePromise;
		}

		initializePromise = (async () => {
			const { refresh } = get();
			try {
				if (!getAccessToken() && getRefreshToken()) {
					await requestTokenRefresh();
				}
				// Always call /auth/me so httpOnly cookie sessions restore after reload (incl. E2E).
				await refresh();
			} catch {
				clearAuthTokens();
				set({ hasHydrated: true, user: null, isAuthenticated: false, isAdmin: false });
			} finally {
				initializePromise = null;
			}
		})();

		return initializePromise;
	},
	logout: () => {
		apiLogout();
		clearAuthTokens();
		set({ user: null, isAuthenticated: false, isAdmin: false, hasHydrated: true });
	},
}));
