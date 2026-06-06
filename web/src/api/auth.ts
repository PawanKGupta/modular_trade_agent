import { api, setAccessToken, setRefreshToken } from './client';

export type MeResponse = {
	id: number;
	email: string;
	name?: string | null;
	mobile_number?: string | null;
	roles: ('admin' | 'user')[];
	email_verified: boolean;
};

export type ProfileUpdateResponse = {
	message: string;
	email: string;
	mobile_number?: string | null;
	email_verified: boolean;
	verification_required: boolean;
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

export async function signup(
	email: string,
	password: string,
	name: string,
	mobileNumber?: string,
): Promise<SignupResponse> {
	const body: Record<string, string> = { email, password, name };
	const mobileDigits = mobileNumber?.trim() ? mobileNumber.replace(/\D/g, '') : '';
	if (mobileDigits) {
		body.mobile_number = mobileDigits;
	}
	const res = await api.post<SignupResponse>('/auth/signup', body);
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

export async function updateProfile(input: {
	email: string;
	mobile_number?: string | null;
	current_password?: string;
}): Promise<ProfileUpdateResponse> {
	const body: {
		email: string;
		mobile_number?: string | null;
		current_password?: string;
	} = {
		email: input.email.trim(),
	};
	if (input.mobile_number !== undefined) {
		const trimmed = (input.mobile_number ?? '').trim();
		body.mobile_number = trimmed ? trimmed.replace(/\D/g, '') : null;
	}
	if (input.current_password) {
		body.current_password = input.current_password;
	}
	const res = await api.patch<ProfileUpdateResponse>('/auth/profile', body);
	return res.data;
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
