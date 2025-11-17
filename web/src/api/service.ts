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

// Individual Service Management

export interface IndividualServiceStatus {
	task_name: string;
	is_running: boolean;
	started_at: string | null;
	last_execution_at: string | null;
	next_execution_at: string | null;
	process_id: number | null;
	schedule_enabled: boolean;
}

export interface IndividualServicesStatus {
	services: Record<string, IndividualServiceStatus>;
}

export interface StartIndividualServiceRequest {
	task_name: string;
}

export interface StartIndividualServiceResponse {
	success: boolean;
	message: string;
}

export interface StopIndividualServiceRequest {
	task_name: string;
}

export interface StopIndividualServiceResponse {
	success: boolean;
	message: string;
}

export interface RunOnceRequest {
	task_name: string;
	execution_type?: 'run_once' | 'manual';
}

export interface RunOnceResponse {
	success: boolean;
	message: string;
	execution_id: number | null;
	has_conflict: boolean;
	conflict_message: string | null;
}

export async function getIndividualServicesStatus(): Promise<IndividualServicesStatus> {
	const { data } = await api.get<IndividualServicesStatus>('/user/service/individual/status');
	return data;
}

export async function startIndividualService(
	request: StartIndividualServiceRequest
): Promise<StartIndividualServiceResponse> {
	const { data } = await api.post<StartIndividualServiceResponse>(
		'/user/service/individual/start',
		request
	);
	return data;
}

export async function stopIndividualService(
	request: StopIndividualServiceRequest
): Promise<StopIndividualServiceResponse> {
	const { data } = await api.post<StopIndividualServiceResponse>(
		'/user/service/individual/stop',
		request
	);
	return data;
}

export async function runTaskOnce(request: RunOnceRequest): Promise<RunOnceResponse> {
	const { data } = await api.post<RunOnceResponse>('/user/service/individual/run-once', request);
	return data;
}
