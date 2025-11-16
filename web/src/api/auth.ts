import { api, setAccessToken } from './client';

export type MeResponse = {
	id: number;
	email: string;
	name?: string | null;
	roles: ('admin' | 'user')[];
};

export async function signup(email: string, password: string, name?: string) {
	const res = await api.post('/auth/signup', { email, password, name });
	const token = res.data?.access_token as string;
	setAccessToken(token);
	return token;
}

export async function login(email: string, password: string) {
	const res = await api.post('/auth/login', { email, password });
	const token = res.data?.access_token as string;
	setAccessToken(token);
	return token;
}

export async function me(): Promise<MeResponse> {
	const res = await api.get('/auth/me');
	return res.data as MeResponse;
}

export function logout() {
	setAccessToken(null);
}
