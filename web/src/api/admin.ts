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
	const { data } = await api.patch<AdminUser>(`/admin/users/${id}`, payload);
	return data;
}

export async function deleteUser(id: number): Promise<{ ok: boolean }> {
	await api.delete(`/admin/users/${id}`);
	return { ok: true };
}

// Service Schedule Management

export interface ServiceSchedule {
	id: number;
	task_name: string;
	schedule_time: string; // HH:MM format
	enabled: boolean;
	is_hourly: boolean;
	is_continuous: boolean;
	end_time: string | null; // HH:MM format
	schedule_type: 'daily' | 'once'; // 'daily' runs every day, 'once' runs once and stops
	description: string | null;
	updated_by: number | null;
	updated_at: string;
	next_execution_at: string | null;
}

export interface ServiceSchedules {
	schedules: ServiceSchedule[];
}

export interface UpdateServiceSchedulePayload {
	schedule_time: string; // HH:MM format
	enabled?: boolean;
	is_hourly?: boolean;
	is_continuous?: boolean;
	end_time?: string | null; // HH:MM format
	schedule_type?: 'daily' | 'once';
	description?: string | null;
}

export interface UpdateServiceScheduleResponse {
	success: boolean;
	message: string;
	schedule: ServiceSchedule;
	requires_restart: boolean;
}

export async function listServiceSchedules(): Promise<ServiceSchedules> {
	const { data } = await api.get<ServiceSchedules>('/admin/schedules');
	return data;
}

export async function getServiceSchedule(taskName: string): Promise<ServiceSchedule> {
	const { data } = await api.get<ServiceSchedule>(`/admin/schedules/${taskName}`);
	return data;
}

export async function updateServiceSchedule(
	taskName: string,
	payload: UpdateServiceSchedulePayload
): Promise<UpdateServiceScheduleResponse> {
	const { data } = await api.put<UpdateServiceScheduleResponse>(
		`/admin/schedules/${taskName}`,
		payload
	);
	return data;
}

export async function enableServiceSchedule(
	taskName: string
): Promise<UpdateServiceScheduleResponse> {
	const { data } = await api.post<UpdateServiceScheduleResponse>(
		`/admin/schedules/${taskName}/enable`
	);
	return data;
}

export async function disableServiceSchedule(
	taskName: string
): Promise<UpdateServiceScheduleResponse> {
	const { data } = await api.post<UpdateServiceScheduleResponse>(
		`/admin/schedules/${taskName}/disable`
	);
	return data;
}
