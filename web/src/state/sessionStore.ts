import { create } from 'zustand';
import { me, logout as apiLogout, type MeResponse } from '@/api/auth';
import {
	clearAuthTokens,
	getAccessToken,
	getRefreshToken,
	requestTokenRefresh,
} from '@/api/client';

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

export const useSessionStore = create<SessionState>((set, get) => ({
	isAuthenticated: false,
	user: null,
	isAdmin: false,
	hasHydrated: false,
	setSession: (user) =>
		set({
			user,
			isAuthenticated: !!user,
			isAdmin: !!user?.roles?.includes('admin'),
			hasHydrated: true,
		}),
	refresh: async () => {
		try {
			const profile = await me();
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
		const { hasHydrated, refresh } = get();
		if (hasHydrated) return;
		const accessToken = getAccessToken();
		const refreshToken = getRefreshToken();
		if (!accessToken && !refreshToken) {
			set({ hasHydrated: true, user: null, isAuthenticated: false, isAdmin: false });
			return;
		}
		try {
			if (!accessToken && refreshToken) {
				const refreshed = await requestTokenRefresh();
				if (!refreshed) {
					set({ hasHydrated: true, user: null, isAuthenticated: false, isAdmin: false });
					return;
				}
			}
			await refresh();
		} catch {
			clearAuthTokens();
			set({ hasHydrated: true, user: null, isAuthenticated: false, isAdmin: false });
		}
	},
	logout: () => {
		apiLogout();
		clearAuthTokens();
		set({ user: null, isAuthenticated: false, isAdmin: false, hasHydrated: true });
	},
}));
