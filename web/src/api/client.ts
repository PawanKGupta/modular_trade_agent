import axios, { AxiosError, type AxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const ACCESS_TOKEN_KEY = 'ta_access_token';
const REFRESH_TOKEN_KEY = 'ta_refresh_token';

type RetriableConfig = AxiosRequestConfig & { _retry?: boolean };

export const api = axios.create({
	baseURL: `${API_BASE_URL}/api/v1`,
	withCredentials: false,
});

const refreshClient = axios.create({
	baseURL: `${API_BASE_URL}/api/v1`,
	withCredentials: false,
});

export function setAccessToken(token: string | null) {
	if (token) {
		localStorage.setItem(ACCESS_TOKEN_KEY, token);
	} else {
		localStorage.removeItem(ACCESS_TOKEN_KEY);
	}
}

export function setRefreshToken(token: string | null) {
	if (token) {
		localStorage.setItem(REFRESH_TOKEN_KEY, token);
	} else {
		localStorage.removeItem(REFRESH_TOKEN_KEY);
	}
}

export function getAccessToken(): string | null {
	return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
	return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearAuthTokens() {
	setAccessToken(null);
	setRefreshToken(null);
}

let refreshPromise: Promise<string | null> | null = null;

export async function requestTokenRefresh(): Promise<string | null> {
	if (!refreshPromise) {
		refreshPromise = (async () => {
			const refreshToken = getRefreshToken();
			if (!refreshToken) {
				return null;
			}
			try {
				const { data } = await refreshClient.post('/auth/refresh', {
					refresh_token: refreshToken,
				});
				const access = data?.access_token as string | undefined;
				if (access) {
					setAccessToken(access);
				}
				setRefreshToken((data?.refresh_token as string | null | undefined) ?? refreshToken);
				return access ?? null;
			} catch (error) {
				clearAuthTokens();
				return null;
			} finally {
				refreshPromise = null;
			}
		})();
	}
	return refreshPromise;
}

// Attach Authorization header if token present
api.interceptors.request.use((config) => {
	const token = getAccessToken();
	if (token) {
		config.headers = config.headers ?? {};
		config.headers.Authorization = `Bearer ${token}`;
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
			!original.url?.includes('/auth/refresh')
		) {
			original._retry = true;
			const newToken = await requestTokenRefresh();
			if (newToken) {
				original.headers = original.headers ?? {};
				original.headers.Authorization = `Bearer ${newToken}`;
				return api(original);
			}
		}
		return Promise.reject(error);
	},
);
