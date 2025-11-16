import { create } from 'zustand';
import { me, logout as apiLogout, type MeResponse } from '@/api/auth';

type SessionState = {
	isAuthenticated: boolean;
	user: MeResponse | null;
	isAdmin: boolean;
	setSession: (user: MeResponse | null) => void;
	refresh: () => Promise<void>;
	logout: () => void;
};

export const useSessionStore = create<SessionState>((set) => ({
	isAuthenticated: false,
	user: null,
	isAdmin: false,
	setSession: (user) =>
		set({
			user,
			isAuthenticated: !!user,
			isAdmin: !!user?.roles?.includes('admin'),
		}),
	refresh: async () => {
		try {
			const profile = await me();
			set({
				user: profile,
				isAuthenticated: true,
				isAdmin: !!profile.roles?.includes('admin'),
			});
		} catch {
			set({ user: null, isAuthenticated: false, isAdmin: false });
		}
	},
	logout: () => {
		apiLogout();
		set({ user: null, isAuthenticated: false, isAdmin: false });
	},
}));
