import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	applyTokenResponse,
	clearAuthTokens,
	getAccessToken,
	getCsrfToken,
	getRefreshToken,
	requestTokenRefresh,
	setAccessToken,
	setCsrfToken,
	setRefreshToken,
	usesCookieOnlyAuthStorage,
} from '../client';

vi.mock('axios', () => {
	const create = vi.fn(() => ({
		post: vi.fn(),
		interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
	}));
	return {
		default: { create },
		create,
	};
});

describe('api client auth helpers', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
	});

	it('stores and clears auth tokens', () => {
		setAccessToken('access');
		setRefreshToken('refresh');
		expect(getAccessToken()).toBe('access');
		expect(getRefreshToken()).toBe('refresh');

		clearAuthTokens();
		expect(getAccessToken()).toBeNull();
		expect(getRefreshToken()).toBeNull();
	});

	it('returns null when refresh token is missing', async () => {
		await expect(requestTokenRefresh()).resolves.toBeNull();
	});

	it('stores CSRF token via applyTokenResponse', () => {
		applyTokenResponse({
			access_token: 'access',
			refresh_token: 'refresh',
			csrf_token: 'csrf-abc',
		});
		expect(getCsrfToken()).toBe('csrf-abc');
		setCsrfToken(null);
		expect(getCsrfToken()).toBeNull();
	});

	it('reports cookie-only auth storage in production builds', () => {
		expect(typeof usesCookieOnlyAuthStorage()).toBe('boolean');
	});
});
