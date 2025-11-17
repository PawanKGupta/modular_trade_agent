import { api } from './client';

export interface ServiceStatus {
	service_running: boolean;
	last_heartbeat: string | null;
	last_task_execution: string | null;
	error_count: number;
	last_error: string | null;
	updated_at: string | null;
}

export interface ServiceStartResponse {
	success: boolean;
	message: string;
	service_running: boolean;
}

export interface ServiceStopResponse {
	success: boolean;
	message: string;
	service_running: boolean;
}

export interface TaskExecution {
	id: number;
	task_name: string;
	executed_at: string;
	status: 'success' | 'failed' | 'skipped';
	duration_seconds: number;
	details: Record<string, any> | null;
}

export interface TaskHistory {
	tasks: TaskExecution[];
	total: number;
}

export interface ServiceLog {
	id: number;
	level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
	module: string;
	message: string;
	context: Record<string, any> | null;
	timestamp: string;
}

export interface ServiceLogs {
	logs: ServiceLog[];
	total: number;
	limit: number;
}

export async function startService(): Promise<ServiceStartResponse> {
	const { data } = await api.post<ServiceStartResponse>('/user/service/start');
	return data;
}

export async function stopService(): Promise<ServiceStopResponse> {
	const { data } = await api.post<ServiceStopResponse>('/user/service/stop');
	return data;
}

export async function getServiceStatus(): Promise<ServiceStatus> {
	const { data } = await api.get<ServiceStatus>('/user/service/status');
	return data;
}

export async function getTaskHistory(params?: {
	task_name?: string;
	status?: 'success' | 'failed' | 'skipped';
	limit?: number;
}): Promise<TaskHistory> {
	const { data } = await api.get<TaskHistory>('/user/service/tasks', { params });
	return data;
}

export async function getServiceLogs(params?: {
	level?: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
	module?: string;
	hours?: number;
	limit?: number;
}): Promise<ServiceLogs> {
	const { data } = await api.get<ServiceLogs>('/user/service/logs', { params });
	return data;
}
