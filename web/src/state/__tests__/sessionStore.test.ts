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
	});

	it('marks hydrated when no tokens are available', async () => {
		vi.mocked(getAccessToken).mockReturnValue(null);
		vi.mocked(getRefreshToken).mockReturnValue(null);
		const refreshSpy = vi.fn().mockResolvedValue(undefined);
		useSessionStore.setState((state) => ({ ...state, refresh: refreshSpy }));

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(refreshSpy).not.toHaveBeenCalled();
		expect(useSessionStore.getState().hasHydrated).toBe(true);
		expect(useSessionStore.getState().isAuthenticated).toBe(false);
	});

	it('uses refresh token when access token missing', async () => {
		vi.mocked(getAccessToken).mockReturnValue(null);
		vi.mocked(getRefreshToken).mockReturnValue('refresh-token');
		vi.mocked(requestTokenRefresh).mockResolvedValue('new-access');
		const refreshSpy = vi.fn().mockResolvedValue(undefined);
		useSessionStore.setState((state) => ({ ...state, refresh: refreshSpy }));

		await act(async () => {
			await useSessionStore.getState().initialize();
		});

		expect(requestTokenRefresh).toHaveBeenCalledTimes(1);
		expect(refreshSpy).toHaveBeenCalled();
	});
});
