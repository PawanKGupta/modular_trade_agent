import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const api = axios.create({
	baseURL: `${API_BASE_URL}/api/v1`,
	withCredentials: false,
});

// Attach Authorization header if token present
api.interceptors.request.use((config) => {
	const token = localStorage.getItem('ta_access_token');
	if (token) {
		config.headers = config.headers ?? {};
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});

export function setAccessToken(token: string | null) {
	if (token) {
		localStorage.setItem('ta_access_token', token);
	} else {
		localStorage.removeItem('ta_access_token');
	}
}
