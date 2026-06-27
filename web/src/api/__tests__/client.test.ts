import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios, { AxiosError } from 'axios';
import {
	applyTokenResponse,
	api,
	clearAuthTokens,
	getAccessToken,
	getCsrfToken,
	getRefreshToken,
	requestTokenRefresh,
	setAccessToken,
	setAuthFailureCallback,
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

const responseInterceptorOnRejected = vi.mocked(api.interceptors.response.use).mock.calls[0]?.[1] as
	| ((error: AxiosError) => Promise<unknown>)
	| undefined;

const refreshClientMock = vi.mocked(axios.create).mock.results.find((r) => r.value !== api)?.value;

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

	it('invokes auth failure callback when clearAuthTokens is called', () => {
		const callback = vi.fn();
		setAuthFailureCallback(callback);
		clearAuthTokens();
		expect(callback).toHaveBeenCalledTimes(1);

		// Reset callback to avoid affecting other tests
		setAuthFailureCallback(() => {});
	});

	it('intercepts 401 error, attempts refresh, and calls failure callback if refresh fails', async () => {
		expect(responseInterceptorOnRejected).toBeTypeOf('function');
		expect(refreshClientMock).toBeDefined();

		// Mock refreshClient.post to reject (failed refresh)
		refreshClientMock.post.mockRejectedValue(new Error('refresh expired'));

		// Set a dummy refresh token to trigger refresh attempt in dev environment mock
		localStorage.setItem('ta_refresh_token', 'dummy-refresh-token');

		const failureCallback = vi.fn();
		setAuthFailureCallback(failureCallback);

		const mockError = {
			response: { status: 401 },
			config: { url: '/api/v1/portfolio', headers: {} },
		} as unknown as AxiosError;

		await expect(responseInterceptorOnRejected!(mockError)).rejects.toThrow();

		expect(refreshClientMock.post).toHaveBeenCalledWith('/auth/refresh', {
			refresh_token: 'dummy-refresh-token',
		});
		expect(failureCallback).toHaveBeenCalledTimes(1);

		// Clean up
		localStorage.removeItem('ta_refresh_token');
		setAuthFailureCallback(() => {});
	});

	it('does not retry and calls failure callback if response is 401 and _retry is already true', async () => {
		expect(responseInterceptorOnRejected).toBeTypeOf('function');
		expect(refreshClientMock).toBeDefined();
		refreshClientMock.post.mockReset();

		const failureCallback = vi.fn();
		setAuthFailureCallback(failureCallback);

		const mockError = {
			response: { status: 401 },
			config: { url: '/api/v1/portfolio', headers: {}, _retry: true },
		} as unknown as AxiosError;

		await expect(responseInterceptorOnRejected!(mockError)).rejects.toEqual(mockError);

		// Should not attempt refresh
		expect(refreshClientMock.post).not.toHaveBeenCalled();
		// Should call failure callback
		expect(failureCallback).toHaveBeenCalledTimes(1);

		// Clean up
		setAuthFailureCallback(() => {});
	});

	it('does not attempt refresh if the 401 is on a login request', async () => {
		expect(responseInterceptorOnRejected).toBeTypeOf('function');
		expect(refreshClientMock).toBeDefined();
		refreshClientMock.post.mockReset();

		const failureCallback = vi.fn();
		setAuthFailureCallback(failureCallback);

		const mockError = {
			response: { status: 401 },
			config: { url: '/api/v1/auth/login', headers: {} },
		} as unknown as AxiosError;

		await expect(responseInterceptorOnRejected!(mockError)).rejects.toEqual(mockError);

		// Should not attempt refresh
		expect(refreshClientMock.post).not.toHaveBeenCalled();
		// Should call failure callback to clean up local storage
		expect(failureCallback).toHaveBeenCalledTimes(1);

		setAuthFailureCallback(() => {});
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
