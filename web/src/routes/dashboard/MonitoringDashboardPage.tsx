import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
	getMonitoringDashboard,
	getTaskExecutions,
	getRunningTasks,
	getScheduleCompliance,
	getActiveSessions,
	getReauthHistory,
	getAuthErrors,
	type MonitoringDashboardResponse,
	type TaskExecutionsResponse,
	type RunningTasksResponse,
	type RunningTask,
	type ScheduleComplianceResponse,
	type ActiveSessionsResponse,
	type ReauthHistoryResponse,
	type AuthErrorsResponse,
} from '@/api/monitoring';
import { formatTimeAgo } from '@/utils/time';

function formatDuration(seconds: number): string {
	if (seconds < 60) {
		return `${seconds.toFixed(1)}s`;
	}
	if (seconds < 3600) {
		return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
	}
	return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatTimeAgoShort(dateString: string | null): string {
	if (!dateString) return 'Never';
	const date = new Date(dateString);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffMins = Math.floor(diffMs / 60000);
	const diffHours = Math.floor(diffMs / 3600000);
	const diffDays = Math.floor(diffMs / 86400000);

	if (diffMins < 1) return 'Just now';
	if (diffMins < 60) return `${diffMins}m ago`;
	if (diffHours < 24) return `${diffHours}h ago`;
	if (diffDays < 7) return `${diffDays}d ago`;
	return date.toLocaleDateString();
}

function getStatusColor(status: string): string {
	switch (status) {
		case 'success':
			return 'bg-green-100 text-green-800';
		case 'failed':
			return 'bg-red-100 text-red-800';
		case 'skipped':
			return 'bg-gray-100 text-gray-800';
		case 'running':
			return 'bg-blue-100 text-blue-800';
		default:
			return 'bg-gray-100 text-gray-800';
	}
}

function getComplianceColor(status: string): string {
	switch (status) {
		case 'on_track':
			return 'bg-green-100 text-green-800';
		case 'delayed':
			return 'bg-yellow-100 text-yellow-800';
		case 'missed':
			return 'bg-red-100 text-red-800';
		default:
			return 'bg-gray-100 text-gray-800';
	}
}

function getSessionStatusColor(status: string): string {
	switch (status) {
		case 'valid':
			return 'bg-green-100 text-green-800';
		case 'expiring_soon':
			return 'bg-yellow-100 text-yellow-800';
		case 'expired':
			return 'bg-red-100 text-red-800';
		default:
			return 'bg-gray-100 text-gray-800';
	}
}

function getReauthStatusColor(status: string): string {
	switch (status) {
		case 'success':
			return 'bg-green-100 text-green-800';
		case 'failed':
			return 'bg-red-100 text-red-800';
		case 'rate_limited':
			return 'bg-yellow-100 text-yellow-800';
		default:
			return 'bg-gray-100 text-gray-800';
	}
}

export function MonitoringDashboardPage() {
	const [autoRefresh, setAutoRefresh] = useState(true);
	const [executionsPage, setExecutionsPage] = useState(1);
	const [reauthPage, setReauthPage] = useState(1);
	const [authErrorsPage, setAuthErrorsPage] = useState(1);

	useEffect(() => {
		document.title = 'Monitoring Dashboard';
	}, []);

	// Main dashboard query
	const { data: dashboard, isLoading: dashboardLoading } =
		useQuery<MonitoringDashboardResponse>({
			queryKey: ['monitoring-dashboard'],
			queryFn: getMonitoringDashboard,
			refetchInterval: autoRefresh ? 10000 : false, // Refresh every 10s
		});

	// Task executions query
	const { data: executions } = useQuery<TaskExecutionsResponse>({
		queryKey: ['task-executions', executionsPage],
		queryFn: () => getTaskExecutions({ page: executionsPage, page_size: 20 }),
		refetchInterval: autoRefresh ? 30000 : false,
	});

	// Running tasks query
	const { data: runningTasks } = useQuery<RunningTasksResponse>({
		queryKey: ['running-tasks'],
		queryFn: () => getRunningTasks(),
		refetchInterval: autoRefresh ? 5000 : false, // Refresh every 5s
	});

	// Schedule compliance query
	const { data: compliance } = useQuery<ScheduleComplianceResponse>({
		queryKey: ['schedule-compliance'],
		queryFn: getScheduleCompliance,
		refetchInterval: autoRefresh ? 60000 : false, // Refresh every minute
	});

	// Active sessions query
	const { data: sessions } = useQuery<ActiveSessionsResponse>({
		queryKey: ['active-sessions'],
		queryFn: getActiveSessions,
		refetchInterval: autoRefresh ? 30000 : false,
	});

	// Re-auth history query
	const { data: reauthHistory } = useQuery<ReauthHistoryResponse>({
		queryKey: ['reauth-history', reauthPage],
		queryFn: () => getReauthHistory({ page: reauthPage, page_size: 20 }),
		refetchInterval: autoRefresh ? 30000 : false,
	});

	// Auth errors query
	const { data: authErrors } = useQuery<AuthErrorsResponse>({
		queryKey: ['auth-errors', authErrorsPage],
		queryFn: () => getAuthErrors({ page: authErrorsPage, page_size: 20 }),
		refetchInterval: autoRefresh ? 30000 : false,
	});

	if (dashboardLoading) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-sm sm:text-base text-[var(--text)]">Loading dashboard data...</div>
			</div>
		);
	}

	if (!dashboard) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-sm sm:text-base text-[var(--text)]">No dashboard data available</div>
			</div>
		);
	}

	const { summary, alerts, recent_task_executions, recent_reauth_events, running_tasks } =
		dashboard;

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6">
			<div className="flex justify-between items-center">
				<div className="text-lg sm:text-xl font-semibold text-[var(--text)]">Monitoring Dashboard</div>
				<label className="flex items-center gap-2 text-xs sm:text-sm text-[var(--text)]">
					<input
						type="checkbox"
						checked={autoRefresh}
						onChange={(e) => setAutoRefresh(e.target.checked)}
						className="accent-blue-600 w-4 h-4 sm:w-auto sm:h-auto"
					/>
					<span>Auto-refresh</span>
				</label>
			</div>

			{/* Alerts Section */}
			{alerts.alerts.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">
						Alerts ({alerts.critical_count} critical, {alerts.warning_count} warning)
					</div>
					<div className="space-y-2">
						{alerts.alerts.slice(0, 5).map((alert, idx) => (
							<div
								key={idx}
								className={`p-2 sm:p-3 rounded ${
									alert.severity === 'critical'
										? 'bg-red-500/10 border border-red-500/20'
										: alert.severity === 'warning'
											? 'bg-yellow-500/10 border border-yellow-500/20'
											: 'bg-blue-500/10 border border-blue-500/20'
								}`}
							>
								<div className={`text-sm font-medium ${
									alert.severity === 'critical'
										? 'text-red-400'
										: alert.severity === 'warning'
											? 'text-yellow-400'
											: 'text-blue-400'
								}`}>{alert.message}</div>
								<div className="text-xs text-[var(--text)] opacity-70 mt-1">User: {alert.user_id}</div>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Summary Cards */}
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-xs sm:text-sm text-[var(--text)] opacity-70">Services Running</div>
					<div className="text-xl sm:text-2xl font-bold text-[var(--text)]">
						{summary.services_running}/{summary.total_services}
					</div>
					<div className="text-xs text-[var(--text)] opacity-60 mt-1">
						{summary.services_stopped} stopped
					</div>
				</div>

				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-xs sm:text-sm text-[var(--text)] opacity-70">Tasks Today</div>
					<div className="text-xl sm:text-2xl font-bold text-[var(--text)]">
						{summary.tasks_successful_today}/{summary.tasks_executed_today}
					</div>
					<div className="text-xs text-[var(--text)] opacity-60 mt-1">
						{summary.tasks_failed_today} failed
					</div>
				</div>

				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-xs sm:text-sm text-[var(--text)] opacity-70">Active Sessions</div>
					<div className="text-xl sm:text-2xl font-bold text-[var(--text)]">{summary.active_sessions}</div>
					<div className="text-xs text-[var(--text)] opacity-60 mt-1">
						{summary.sessions_expiring_soon} expiring soon
					</div>
				</div>

				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-xs sm:text-sm text-[var(--text)] opacity-70">Re-auths (24h)</div>
					<div className="text-xl sm:text-2xl font-bold text-[var(--text)]">{summary.reauth_count_24h}</div>
					<div className="text-xs text-[var(--text)] opacity-60 mt-1">
						{summary.reauth_success_rate.toFixed(1)}% success rate
					</div>
				</div>
			</div>

			{/* Currently Running Tasks */}
			{runningTasks?.tasks && runningTasks.tasks.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">
						Currently Running Tasks ({runningTasks.tasks.length})
					</div>
					<div className="overflow-x-auto">
						<table className="w-full text-sm text-[var(--text)]">
							<thead>
								<tr className="border-b border-[#1e293b]">
									<th className="text-left p-2 text-[var(--text)]">Task</th>
									<th className="text-left p-2 text-[var(--text)]">User</th>
									<th className="text-left p-2 text-[var(--text)]">Started</th>
									<th className="text-left p-2 text-[var(--text)]">Duration</th>
								</tr>
							</thead>
							<tbody>
								{runningTasks.tasks.map((task: RunningTask) => (
									<tr key={task.id} className="border-b border-[#1e293b]">
										<td className="p-2 font-medium text-[var(--text)]">{task.task_name}</td>
										<td className="p-2 text-[var(--text)]">{task.user_email || `User ${task.user_id}`}</td>
										<td className="p-2 text-[var(--text)]">{formatTimeAgoShort(task.started_at)}</td>
										<td className="p-2 text-[var(--text)]">{formatDuration(task.duration_seconds)}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</div>
			)}

			{/* Schedule Compliance */}
			{compliance && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">
						Schedule Compliance ({compliance.total_missed} missed,{' '}
						{compliance.total_delayed} delayed)
					</div>
					<div className="overflow-x-auto">
						<table className="w-full text-sm text-[var(--text)]">
							<thead>
								<tr className="border-b border-[#1e293b]">
									<th className="text-left p-2 text-[var(--text)]">Task</th>
									<th className="text-left p-2 text-[var(--text)]">Scheduled</th>
									<th className="text-left p-2 text-[var(--text)]">Last Execution</th>
									<th className="text-left p-2 text-[var(--text)]">Count Today</th>
									<th className="text-left p-2 text-[var(--text)]">Status</th>
								</tr>
							</thead>
							<tbody>
								{compliance.tasks.map((task) => (
									<tr key={task.task_name} className="border-b border-[#1e293b]">
										<td className="p-2 font-medium text-[var(--text)]">{task.task_name}</td>
										<td className="p-2 text-[var(--text)]">{task.scheduled_time}</td>
										<td className="p-2 text-[var(--text)]">
											{formatTimeAgoShort(task.last_execution_at)}
										</td>
										<td className="p-2 text-[var(--text)]">{task.execution_count_today}</td>
										<td className="p-2">
											<span
												className={`px-2 py-1 rounded text-xs ${getComplianceColor(
													task.compliance_status
												)}`}
											>
												{task.compliance_status}
											</span>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</div>
			)}

			{/* Active Sessions */}
			{sessions && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">
						Active Sessions ({sessions.total_active} active, {sessions.expiring_soon}{' '}
						expiring soon, {sessions.expired} expired)
					</div>
					<div className="overflow-x-auto">
						<table className="w-full text-sm text-[var(--text)]">
							<thead>
								<tr className="border-b border-[#1e293b]">
									<th className="text-left p-2 text-[var(--text)]">User</th>
									<th className="text-left p-2 text-[var(--text)]">Session Age</th>
									<th className="text-left p-2 text-[var(--text)]">TTL Remaining</th>
									<th className="text-left p-2 text-[var(--text)]">Status</th>
								</tr>
							</thead>
							<tbody>
								{sessions.sessions.map((session) => (
									<tr key={session.user_id} className="border-b border-[#1e293b]">
										<td className="p-2 text-[var(--text)]">
											{session.user_email || `User ${session.user_id}`}
										</td>
										<td className="p-2 text-[var(--text)]">
											{session.session_age_minutes
												? `${Math.floor(session.session_age_minutes)}m`
												: '-'}
										</td>
										<td className="p-2 text-[var(--text)]">
											{session.ttl_remaining_minutes
												? `${Math.floor(session.ttl_remaining_minutes)}m`
												: '-'}
										</td>
										<td className="p-2">
											<span
												className={`px-2 py-1 rounded text-xs ${getSessionStatusColor(
													session.session_status
												)}`}
											>
												{session.session_status}
											</span>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</div>
			)}

			{/* Recent Task Executions */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
				<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">Recent Task Executions</div>
				<div className="overflow-x-auto">
					<table className="w-full text-sm text-[var(--text)]">
						<thead>
							<tr className="border-b border-[#1e293b]">
								<th className="text-left p-2 text-[var(--text)]">Task</th>
								<th className="text-left p-2 text-[var(--text)]">User</th>
								<th className="text-left p-2 text-[var(--text)]">Executed</th>
								<th className="text-left p-2 text-[var(--text)]">Duration</th>
								<th className="text-left p-2 text-[var(--text)]">Status</th>
							</tr>
						</thead>
						<tbody>
							{/* Use executions.items if available (pagination), otherwise fall back to recent_task_executions */}
							{(executions?.items || recent_task_executions.slice(0, 10)).map((exec) => (
								<tr key={exec.id} className="border-b border-[#1e293b]">
									<td className="p-2 font-medium text-[var(--text)]">{exec.task_name}</td>
									<td className="p-2 text-[var(--text)]">{exec.user_email || `User ${exec.user_id}`}</td>
									<td className="p-2 text-[var(--text)]">{formatTimeAgoShort(exec.executed_at)}</td>
									<td className="p-2 text-[var(--text)]">{formatDuration(exec.duration_seconds)}</td>
									<td className="p-2">
										<span
											className={`px-2 py-1 rounded text-xs ${getStatusColor(
												exec.status
											)}`}
										>
											{exec.status}
										</span>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
				{executions && executions.total_pages > 1 && (
					<div className="mt-3 flex gap-2">
						<button
							onClick={() => setExecutionsPage((p) => Math.max(1, p - 1))}
							disabled={executionsPage === 1}
							className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
						>
							Previous
						</button>
						<span className="px-3 py-1 text-[var(--text)]">
							Page {executionsPage} of {executions.total_pages}
						</span>
						<button
							onClick={() =>
								setExecutionsPage((p) => Math.min(executions.total_pages, p + 1))
							}
							disabled={executionsPage >= executions.total_pages}
							className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
						>
							Next
						</button>
					</div>
				)}
			</div>

			{/* Recent Re-auth Events */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
				<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">Recent Re-authentication Events</div>
				<div className="overflow-x-auto">
					<table className="w-full text-sm text-[var(--text)]">
						<thead>
							<tr className="border-b border-[#1e293b]">
								<th className="text-left p-2 text-[var(--text)]">User</th>
								<th className="text-left p-2 text-[var(--text)]">Timestamp</th>
								<th className="text-left p-2 text-[var(--text)]">Reason</th>
								<th className="text-left p-2 text-[var(--text)]">Status</th>
							</tr>
						</thead>
						<tbody>
							{recent_reauth_events.slice(0, 10).map((event, idx) => (
								<tr key={event.id || idx} className="border-b border-[#1e293b]">
									<td className="p-2 text-[var(--text)]">
										{event.user_email || `User ${event.user_id}`}
									</td>
									<td className="p-2 text-[var(--text)]">{formatTimeAgoShort(event.timestamp)}</td>
									<td className="p-2 text-[var(--text)]">{event.reason || '-'}</td>
									<td className="p-2">
										<span
											className={`px-2 py-1 rounded text-xs ${getReauthStatusColor(
												event.status
											)}`}
										>
											{event.status}
										</span>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
				{reauthHistory && reauthHistory.total_pages > 1 && (
					<div className="mt-3 flex gap-2">
						<button
							onClick={() => setReauthPage((p) => Math.max(1, p - 1))}
							disabled={reauthPage === 1}
							className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
						>
							Previous
						</button>
						<span className="px-3 py-1 text-[var(--text)]">
							Page {reauthPage} of {reauthHistory.total_pages}
						</span>
						<button
							onClick={() =>
								setReauthPage((p) => Math.min(reauthHistory.total_pages, p + 1))
							}
							disabled={reauthPage >= reauthHistory.total_pages}
							className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
						>
							Next
						</button>
					</div>
				)}
			</div>

			{/* Auth Errors */}
			{authErrors && authErrors.errors.length > 0 && (
				<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
					<div className="text-base sm:text-lg font-semibold mb-3 text-[var(--text)]">
						Authentication Errors ({authErrors.total})
					</div>
					<div className="overflow-x-auto">
						<table className="w-full text-sm text-[var(--text)]">
							<thead>
								<tr className="border-b border-[#1e293b]">
									<th className="text-left p-2 text-[var(--text)]">User</th>
									<th className="text-left p-2 text-[var(--text)]">Timestamp</th>
									<th className="text-left p-2 text-[var(--text)]">Type</th>
									<th className="text-left p-2 text-[var(--text)]">Message</th>
									<th className="text-left p-2 text-[var(--text)]">Re-auth</th>
								</tr>
							</thead>
							<tbody>
								{authErrors.errors.map((error) => (
									<tr key={error.id || `${error.user_id}-${error.timestamp}`} className="border-b border-[#1e293b]">
										<td className="p-2 text-[var(--text)]">
											{error.user_email || `User ${error.user_id}`}
										</td>
										<td className="p-2 text-[var(--text)]">{formatTimeAgoShort(error.timestamp)}</td>
										<td className="p-2 text-[var(--text)]">{error.error_type}</td>
										<td className="p-2 truncate max-w-xs text-[var(--text)]" title={error.error_message}>
											{error.error_message}
										</td>
										<td className="p-2">
											{error.reauth_attempted ? (
												<span
													className={`px-2 py-1 rounded text-xs ${
														error.reauth_success
															? 'bg-green-100 text-green-800'
															: 'bg-red-100 text-red-800'
													}`}
												>
													{error.reauth_success ? 'Success' : 'Failed'}
												</span>
											) : (
												<span className="text-[var(--text)]">-</span>
											)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
					{authErrors.total_pages > 1 && (
						<div className="mt-3 flex gap-2">
							<button
								onClick={() => setAuthErrorsPage((p) => Math.max(1, p - 1))}
								disabled={authErrorsPage === 1}
								className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
							>
								Previous
							</button>
							<span className="px-3 py-1 text-[var(--text)]">
								Page {authErrorsPage} of {authErrors.total_pages}
							</span>
							<button
								onClick={() =>
									setAuthErrorsPage((p) => Math.min(authErrors.total_pages, p + 1))
								}
								disabled={authErrorsPage >= authErrors.total_pages}
								className="px-3 py-1 bg-[var(--panel)] border border-[#1e293b] rounded disabled:opacity-50 text-[var(--text)]"
							>
								Next
							</button>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
