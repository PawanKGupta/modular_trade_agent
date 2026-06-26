import axios, { AxiosError, type AxiosRequestConfig } from 'axios';

const getApiBaseUrl = () => {
	const envUrl = import.meta.env.VITE_API_URL;
	if (envUrl) {
		return envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
	}
	return import.meta.env.PROD ? '' : 'http://localhost:8000';
};

const API_BASE_URL = getApiBaseUrl();
const ACCESS_TOKEN_KEY = 'ta_access_token';
const REFRESH_TOKEN_KEY = 'ta_refresh_token';
const CSRF_TOKEN_KEY = 'ta_csrf_token';

/** Prefer httpOnly cookies in production; memory cache for Bearer header. */
let memoryAccessToken: string | null = null;

type RetriableConfig = AxiosRequestConfig & { _retry?: boolean };

export const api = axios.create({
	baseURL: API_BASE_URL ? `${API_BASE_URL}/api/v1` : '/api/v1',
	withCredentials: true,
});

const refreshClient = axios.create({
	baseURL: API_BASE_URL ? `${API_BASE_URL}/api/v1` : '/api/v1',
	withCredentials: true,
});

export function setAccessToken(token: string | null) {
	memoryAccessToken = token;
	if (!import.meta.env.PROD) {
		if (token) {
			localStorage.setItem(ACCESS_TOKEN_KEY, token);
		} else {
			localStorage.removeItem(ACCESS_TOKEN_KEY);
		}
	}
}

export function setRefreshToken(token: string | null) {
	if (!import.meta.env.PROD && token) {
		localStorage.setItem(REFRESH_TOKEN_KEY, token);
	} else if (!import.meta.env.PROD) {
		localStorage.removeItem(REFRESH_TOKEN_KEY);
	}
}

export function setCsrfToken(token: string | null) {
	if (token) {
		sessionStorage.setItem(CSRF_TOKEN_KEY, token);
	} else {
		sessionStorage.removeItem(CSRF_TOKEN_KEY);
	}
}

export function getAccessToken(): string | null {
	if (memoryAccessToken) {
		return memoryAccessToken;
	}
	if (!import.meta.env.PROD) {
		return localStorage.getItem(ACCESS_TOKEN_KEY);
	}
	return null;
}

export function getRefreshToken(): string | null {
	if (!import.meta.env.PROD) {
		return localStorage.getItem(REFRESH_TOKEN_KEY);
	}
	return null;
}

/** Production uses httpOnly cookies; dev uses localStorage for token restore on reload. */
export function usesCookieOnlyAuthStorage(): boolean {
	return import.meta.env.PROD;
}

export function getCsrfToken(): string | null {
	return sessionStorage.getItem(CSRF_TOKEN_KEY);
}

let onAuthFailureCallback: (() => void) | null = null;

export function setAuthFailureCallback(callback: () => void) {
	onAuthFailureCallback = callback;
}

export function clearAuthTokens() {
	memoryAccessToken = null;
	setAccessToken(null);
	setRefreshToken(null);
	setCsrfToken(null);
	if (onAuthFailureCallback) {
		onAuthFailureCallback();
	}
}

export function applyTokenResponse(data: {
	access_token?: string;
	refresh_token?: string | null;
	csrf_token?: string | null;
}) {
	if (data.access_token) {
		setAccessToken(data.access_token);
	}
	if (data.refresh_token) {
		setRefreshToken(data.refresh_token);
	}
	if (data.csrf_token) {
		setCsrfToken(data.csrf_token);
	}
}

let refreshPromise: Promise<string | null> | null = null;

export async function requestTokenRefresh(): Promise<string | null> {
	if (!refreshPromise) {
		refreshPromise = (async () => {
			const refreshToken = getRefreshToken();
			const body = refreshToken ? { refresh_token: refreshToken } : {};
			try {
				const { data } = await refreshClient.post('/auth/refresh', body);
				applyTokenResponse(data);
				return (data?.access_token as string | undefined) ?? null;
			} catch {
				clearAuthTokens();
				return null;
			} finally {
				refreshPromise = null;
			}
		})();
	}
	return refreshPromise;
}

api.interceptors.request.use((config) => {
	const token = getAccessToken();
	if (token) {
		config.headers = config.headers ?? {};
		config.headers.Authorization = `Bearer ${token}`;
	}
	const csrf = getCsrfToken();
	if (csrf && config.method && !['get', 'head', 'options'].includes(config.method.toLowerCase())) {
		config.headers = config.headers ?? {};
		config.headers['X-CSRF-Token'] = csrf;
	}
	return config;
});

api.interceptors.response.use(
	(response) => response,
	async (error: AxiosError) => {
		const { response, config } = error;
		const original = config as RetriableConfig | undefined;
		if (
			response?.status === 401 &&
			original &&
			!original._retry &&
			!original.url?.includes('/auth/refresh') &&
			!original.url?.includes('/auth/login') &&
			!original.url?.includes('/auth/mfa/login')
		) {
			original._retry = true;
			const newToken = await requestTokenRefresh();
			if (newToken) {
				original.headers = original.headers ?? {};
				original.headers.Authorization = `Bearer ${newToken}`;
				return api(original);
			}
		} else if (response?.status === 401 && !original?.url?.includes('/auth/refresh')) {
			clearAuthTokens();
		}
		return Promise.reject(error);
	},
);
