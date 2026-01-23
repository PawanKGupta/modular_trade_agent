import { api } from './client';

// Service Execution Monitoring Types

export interface ServiceHealthStatus {
	user_id: number;
	user_email: string | null;
	service_running: boolean;
	last_heartbeat: string | null;
	heartbeat_age_seconds: number | null;
	last_task_execution: string | null;
	last_task_name: string | null;
	error_count: number;
	last_error: string | null;
	updated_at: string | null;
}

export interface ServicesHealthResponse {
	services: ServiceHealthStatus[];
	total_running: number;
	total_stopped: number;
	services_with_recent_errors: number;
}

export interface TaskExecutionWithSchedule {
	id: number;
	user_id: number;
	user_email: string | null;
	task_name: string;
	scheduled_time: string | null;
	executed_at: string;
	time_difference_seconds: number | null;
	status: 'success' | 'failed' | 'skipped' | 'running';
	duration_seconds: number;
	execution_type: 'scheduled' | 'run_once' | 'manual';
	details: Record<string, unknown> | null;
}

export interface TaskExecutionsResponse {
	items: TaskExecutionWithSchedule[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

export interface TaskMetrics {
	task_name: string;
	total_executions: number;
	successful_executions: number;
	failed_executions: number;
	skipped_executions: number;
	success_rate: number;
	avg_duration_seconds: number;
	p95_duration_seconds: number | null;
	p99_duration_seconds: number | null;
	on_time_percentage: number | null;
	last_execution_at: string | null;
	last_execution_status: string | null;
}

export interface TaskMetricsResponse {
	metrics: TaskMetrics[];
	period_days: number;
}

export interface ScheduleCompliance {
	task_name: string;
	scheduled_time: string;
	enabled: boolean;
	is_continuous: boolean;
	end_time: string | null;
	last_execution_at: string | null;
	next_expected_execution: string | null;
	execution_count_today: number;
	expected_count_today: number | null;
	compliance_status: 'on_track' | 'delayed' | 'missed' | 'not_applicable';
	last_execution_status: string | null;
}

export interface ScheduleComplianceResponse {
	tasks: ScheduleCompliance[];
	total_missed: number;
	total_delayed: number;
}

export interface RunningTask {
	id: number;
	user_id: number;
	user_email: string | null;
	task_name: string;
	started_at: string;
	duration_seconds: number;
	estimated_completion: string | null;
}

export interface RunningTasksResponse {
	tasks: RunningTask[];
	total: number;
}

// Authentication Monitoring Types

export interface ActiveSession {
	user_id: number;
	user_email: string | null;
	session_created_at: string | null;
	session_age_minutes: number | null;
	session_status: 'valid' | 'expiring_soon' | 'expired';
	ttl_remaining_minutes: number | null;
	is_authenticated: boolean;
	client_available: boolean;
}

export interface ActiveSessionsResponse {
	sessions: ActiveSession[];
	total_active: number;
	expiring_soon: number;
	expired: number;
}

export interface ReauthEvent {
	id: number | null;
	user_id: number;
	user_email: string | null;
	timestamp: string;
	triggered_by: string | null;
	status: 'success' | 'failed' | 'rate_limited';
	duration_seconds: number | null;
	reason: string | null;
	error_message: string | null;
}

export interface ReauthHistoryResponse {
	events: ReauthEvent[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

export interface ReauthStatistics {
	user_id: number;
	user_email: string | null;
	reauth_count_24h: number;
	reauth_count_7d: number;
	reauth_count_30d: number;
	reauth_rate_per_hour: number;
	success_rate: number;
	avg_time_between_reauth_minutes: number | null;
	rate_limited: boolean;
	cooldown_remaining_seconds: number | null;
	blocked: boolean;
}

export interface ReauthStatisticsResponse {
	statistics: ReauthStatistics[];
	period_days: number;
}

export interface AuthError {
	id: number | null;
	user_id: number;
	user_email: string | null;
	timestamp: string;
	error_type: string;
	error_code: string | null;
	error_message: string;
	api_endpoint: string | null;
	method_name: string | null;
	reauth_attempted: boolean;
	reauth_success: boolean | null;
}

export interface AuthErrorsResponse {
	errors: AuthError[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

// Combined Dashboard Types

export interface DashboardSummary {
	total_services: number;
	services_running: number;
	services_stopped: number;
	tasks_executed_today: number;
	tasks_successful_today: number;
	tasks_failed_today: number;
	services_with_errors: number;
	active_sessions: number;
	sessions_expiring_soon: number;
	reauth_count_24h: number;
	reauth_success_rate: number;
	auth_errors_24h: number;
	tasks_failed_due_to_auth: number;
}

export interface DashboardAlerts {
	alerts: Array<{
		severity: 'critical' | 'warning' | 'info';
		type: string;
		message: string;
		user_id: number;
	}>;
	critical_count: number;
	warning_count: number;
	info_count: number;
}

export interface MonitoringDashboardResponse {
	summary: DashboardSummary;
	alerts: DashboardAlerts;
	recent_task_executions: TaskExecutionWithSchedule[];
	recent_reauth_events: ReauthEvent[];
	running_tasks: RunningTask[];
	updated_at: string;
}

// API Functions

export async function getServicesHealth(): Promise<ServicesHealthResponse> {
	const { data } = await api.get<ServicesHealthResponse>('/admin/monitoring/services/health');
	return data;
}

export async function getTaskExecutions(params?: {
	page?: number;
	page_size?: number;
	user_id?: number;
	task_name?: string;
	status?: string;
	start_date?: string;
	end_date?: string;
}): Promise<TaskExecutionsResponse> {
	const { data } = await api.get<TaskExecutionsResponse>('/admin/monitoring/tasks/executions', {
		params,
	});
	return data;
}

export async function getRunningTasks(user_id?: number): Promise<RunningTasksResponse> {
	const { data } = await api.get<RunningTasksResponse>('/admin/monitoring/tasks/running', {
		params: user_id ? { user_id } : {},
	});
	return data;
}

export async function getTaskMetrics(params?: {
	period_days?: number;
	user_id?: number;
	task_name?: string;
}): Promise<TaskMetricsResponse> {
	const { data } = await api.get<TaskMetricsResponse>('/admin/monitoring/tasks/metrics', {
		params,
	});
	return data;
}

export async function getScheduleCompliance(): Promise<ScheduleComplianceResponse> {
	const { data } = await api.get<ScheduleComplianceResponse>(
		'/admin/monitoring/tasks/compliance'
	);
	return data;
}

export async function getActiveSessions(): Promise<ActiveSessionsResponse> {
	const { data } = await api.get<ActiveSessionsResponse>('/admin/monitoring/auth/sessions');
	return data;
}

export async function getReauthHistory(params?: {
	page?: number;
	page_size?: number;
	user_id?: number;
	start_date?: string;
	end_date?: string;
}): Promise<ReauthHistoryResponse> {
	const { data } = await api.get<ReauthHistoryResponse>('/admin/monitoring/auth/reauth-history', {
		params,
	});
	return data;
}

export async function getAuthErrors(params?: {
	page?: number;
	page_size?: number;
	user_id?: number;
	start_date?: string;
	end_date?: string;
}): Promise<AuthErrorsResponse> {
	const { data } = await api.get<AuthErrorsResponse>('/admin/monitoring/auth/errors', {
		params,
	});
	return data;
}

export async function getReauthStatistics(params?: {
	period_days?: number;
	user_id?: number;
}): Promise<ReauthStatisticsResponse> {
	const { data } = await api.get<ReauthStatisticsResponse>('/admin/monitoring/auth/stats', {
		params,
	});
	return data;
}

export async function getMonitoringDashboard(): Promise<MonitoringDashboardResponse> {
	const { data } = await api.get<MonitoringDashboardResponse>('/admin/monitoring/dashboard');
	return data;
}
