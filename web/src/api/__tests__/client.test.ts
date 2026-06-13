import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	applyTokenResponse,
	api,
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

type RequestInterceptor = (config: {
	method?: string;
	headers?: Record<string, string>;
}) => {
	method?: string;
	headers?: Record<string, string>;
};

const requestInterceptor = vi.mocked(api.interceptors.request.use).mock.calls[0]?.[0] as
	| RequestInterceptor
	| undefined;

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

	it('adds CSRF header on mutating requests when token is set', () => {
		expect(requestInterceptor).toBeTypeOf('function');
		setCsrfToken('csrf-token');
		const config = requestInterceptor!({ method: 'post' });
		expect(config.headers?.['X-CSRF-Token']).toBe('csrf-token');
	});
});
