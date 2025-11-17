import { api } from './client';

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface ServiceLogEntry {
	id: number;
	user_id: number;
	level: LogLevel;
	module: string;
	message: string;
	context: Record<string, unknown> | null;
	timestamp: string;
}

export interface ErrorLogEntry {
	id: number;
	user_id: number;
	error_type: string;
	error_message: string;
	traceback: string | null;
	context: Record<string, unknown> | null;
	resolved: boolean;
	resolved_at: string | null;
	resolved_by: number | null;
	resolution_notes: string | null;
	occurred_at: string;
}

type OptionalParams = {
	level?: string;
	module?: string;
	start_time?: string;
	end_time?: string;
	search?: string;
	limit?: number;
};

export async function getUserLogs(params?: OptionalParams): Promise<ServiceLogEntry[]> {
	const { data } = await api.get<{ logs: ServiceLogEntry[] }>('/user/logs', { params });
	return data.logs;
}

export async function getUserErrorLogs(params?: {
	resolved?: boolean;
	error_type?: string;
	start_time?: string;
	end_time?: string;
	search?: string;
	limit?: number;
}): Promise<ErrorLogEntry[]> {
	const { data } = await api.get<{ errors: ErrorLogEntry[] }>('/user/logs/errors', { params });
	return data.errors;
}

export async function getAdminLogs(
	params?: OptionalParams & { user_id?: number }
): Promise<ServiceLogEntry[]> {
	const { data } = await api.get<{ logs: ServiceLogEntry[] }>('/admin/logs', { params });
	return data.logs;
}

export async function getAdminErrorLogs(
	params?: {
		user_id?: number;
		resolved?: boolean;
		error_type?: string;
		start_time?: string;
		end_time?: string;
		search?: string;
		limit?: number;
	}
): Promise<ErrorLogEntry[]> {
	const { data } = await api.get<{ errors: ErrorLogEntry[] }>('/admin/logs/errors', { params });
	return data.errors;
}

export async function resolveErrorLog(
	errorId: number,
	payload: { notes?: string | null }
): Promise<{ message: string; error: ErrorLogEntry }> {
	const { data } = await api.post<{ message: string; error: ErrorLogEntry }>(
		`/admin/logs/errors/${errorId}/resolve`,
		payload
	);
	return data;
}
