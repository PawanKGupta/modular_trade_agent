import { api } from './client';

export type Role = 'admin' | 'user';

export interface AdminUser {
	id: number;
	email: string;
	name?: string | null;
	role: Role;
	is_active: boolean;
	created_at: string;
	updated_at: string;
}

export interface CreateUserPayload {
	email: string;
	password: string;
	name?: string;
	role?: Role;
}

export interface UpdateUserPayload {
	name?: string | null;
	role?: Role;
	is_active?: boolean;
	password?: string;
}

export async function listUsers(): Promise<AdminUser[]> {
	const { data } = await api.get<AdminUser[]>('/admin/users');
	return data;
}

export async function createUser(payload: CreateUserPayload): Promise<AdminUser> {
	const { data } = await api.post<AdminUser>('/admin/users', payload);
	return data;
}

export async function updateUser(id: number, payload: UpdateUserPayload): Promise<AdminUser> {
	const { data } = await api.put<AdminUser>(`/admin/users/${id}`, payload);
	return data;
}

export async function deleteUser(id: number): Promise<{ ok: boolean }> {
	await api.delete(`/admin/users/${id}`);
	return { ok: true };
}
