import { api, setAccessToken, setRefreshToken } from './client';

export type MeResponse = {
	id: number;
	email: string;
	name?: string | null;
	roles: ('admin' | 'user')[];
	email_verified: boolean;
};

type TokenResponse = {
	access_token: string;
	refresh_token?: string | null;
	token_type?: string;
};

type MessageResponse = {
	message: string;
};

export type SignupResponse = {
	message: string;
};

function persistTokens(tokens: TokenResponse) {
	const access = tokens.access_token;
	const refresh = tokens.refresh_token ?? null;
	if (access) {
		setAccessToken(access);
	}
	setRefreshToken(refresh);
}

export async function signup(email: string, password: string, name: string): Promise<SignupResponse> {
	const res = await api.post<SignupResponse>('/auth/signup', { email, password, name });
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

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
	await api.post('/auth/change-password', {
		current_password: currentPassword,
		new_password: newPassword,
	});
}

export async function forgotPassword(email: string): Promise<void> {
	await api.post<MessageResponse>('/auth/forgot-password', { email });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
	await api.post<MessageResponse>('/auth/reset-password', { token, new_password: newPassword });
}

export async function verifyEmail(token: string): Promise<TokenResponse> {
	const res = await api.post<TokenResponse>('/auth/verify-email', { token });
	persistTokens(res.data);
	return res.data;
}

export async function resendVerification(email: string): Promise<void> {
	await api.post<MessageResponse>('/auth/resend-verification', { email });
}

export function logout() {
	setAccessToken(null);
	setRefreshToken(null);
}
