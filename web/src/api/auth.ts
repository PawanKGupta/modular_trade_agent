import { api, setAccessToken, setRefreshToken } from './client';

export type MeResponse = {
	id: number;
	email: string;
	name?: string | null;
	roles: ('admin' | 'user')[];
};

type TokenResponse = {
	access_token: string;
	refresh_token?: string | null;
	token_type?: string;
};

function persistTokens(tokens: TokenResponse) {
	const access = tokens.access_token;
	const refresh = tokens.refresh_token ?? null;
	if (access) {
		setAccessToken(access);
	}
	setRefreshToken(refresh);
}

export async function signup(email: string, password: string, name?: string) {
	const res = await api.post<TokenResponse>('/auth/signup', { email, password, name });
	persistTokens(res.data);
	return res.data;
}

export async function login(email: string, password: string) {
	const res = await api.post<TokenResponse>('/auth/login', { email, password });
	persistTokens(res.data);
	return res.data;
}

export async function me(): Promise<MeResponse> {
	const res = await api.get('/auth/me');
	return res.data as MeResponse;
}

export function logout() {
	setAccessToken(null);
	setRefreshToken(null);
}
