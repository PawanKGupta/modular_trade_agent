import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import { useSessionStore } from '../sessionStore';
import {
	getAccessToken,
	getRefreshToken,
	requestTokenRefresh,
} from '@/api/client';

vi.mock('@/api/client', async (importOriginal) => {
	const actual = await importOriginal<typeof import('@/api/client')>();
	return {
		...actual,
		getAccessToken: vi.fn(),
		getRefreshToken: vi.fn(),
		requestTokenRefresh: vi.fn(),
		clearAuthTokens: actual.clearAuthTokens,
	};
});

vi.mock('@/api/auth', () => ({
	me: vi.fn(),
	logout: vi.fn(),
}));

describe('sessionStore.initialize', () => {
	beforeEach(() => {
		useSessionStore.setState((state) => ({
			...state,
			isAuthenticated: false,
			user: null,
			isAdmin: false,
			hasHydrated: false,
		}));
		localStorage.clear();
		vi.mocked(getAccessToken).mockReset();
		vi.mocked(getRefreshToken).mockReset();
		vi.mocked(requestTokenRefresh).mockReset();
		vi.clearAllMocks();
	});

	it('marks hydrated when no tokens are available', async () => {
		const authApi = await import('@/api/auth');
		vi.mocked(getAccessToken).mockReturnValue(null);
		vi.mocked(getRefreshToken).mockReturnValue(null);

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(authApi.me).not.toHaveBeenCalled();
		expect(useSessionStore.getState().hasHydrated).toBe(true);
		expect(useSessionStore.getState().isAuthenticated).toBe(false);
	});

	it('uses refresh token when access token missing', async () => {
		const authApi = await import('@/api/auth');
		vi.mocked(getAccessToken).mockReturnValue(null);
		vi.mocked(getRefreshToken).mockReturnValue('refresh-token');
		vi.mocked(requestTokenRefresh).mockResolvedValue('new-access');
		vi.mocked(authApi.me).mockResolvedValue({ id: 1, email: 'a@x.com', roles: ['user'] } as never);

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(requestTokenRefresh).toHaveBeenCalledTimes(1);
		expect(authApi.me).toHaveBeenCalled();
	});

	it('clears session when refresh fails', async () => {
		const authApi = await import('@/api/auth');
		vi.mocked(authApi.me).mockRejectedValue(new Error('unauthorized'));
		useSessionStore.setState({
			isAuthenticated: true,
			user: { id: 1, email: 'a@x.com', roles: ['user'] } as never,
			hasHydrated: true,
		});

		await expect(
			act(async () => {
				await useSessionStore.getState().refresh();
			})
		).rejects.toThrow('unauthorized');
		expect(useSessionStore.getState().isAuthenticated).toBe(false);
		expect(useSessionStore.getState().user).toBeNull();
	});

	it('skips initialize when already hydrated', async () => {
		const authApi = await import('@/api/auth');
		useSessionStore.setState({ hasHydrated: true });

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(authApi.me).not.toHaveBeenCalled();
	});

	it('marks hydrated when token refresh returns null', async () => {
		const authApi = await import('@/api/auth');
		vi.mocked(getAccessToken).mockReturnValue(null);
		vi.mocked(getRefreshToken).mockReturnValue('refresh-token');
		vi.mocked(requestTokenRefresh).mockResolvedValue(null);

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(authApi.me).not.toHaveBeenCalled();
		expect(useSessionStore.getState().hasHydrated).toBe(true);
		expect(useSessionStore.getState().isAuthenticated).toBe(false);
	});

	it('clears session when initialize refresh throws', async () => {
		const authApi = await import('@/api/auth');
		vi.mocked(getAccessToken).mockReturnValue('access-token');
		vi.mocked(authApi.me).mockRejectedValue(new Error('network down'));

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(useSessionStore.getState().hasHydrated).toBe(true);
		expect(useSessionStore.getState().isAuthenticated).toBe(false);
		expect(useSessionStore.getState().user).toBeNull();
	});
});
