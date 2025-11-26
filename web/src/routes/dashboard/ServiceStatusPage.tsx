import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { getServiceStatus, getTaskHistory, getServiceLogs, startService, stopService, getIndividualServicesStatus, type ServiceStatus, type TaskExecution, type ServiceLog, type IndividualServicesStatus } from '@/api/service';
import { formatTimeAgo } from '@/utils/time';
import { ServiceControls } from './ServiceControls';
import { ServiceTasksTable } from './ServiceTasksTable';
import { ServiceLogsViewer } from './ServiceLogsViewer';
import { IndividualServicesSection } from './IndividualServicesSection';

export function ServiceStatusPage() {
	const qc = useQueryClient();
	const [autoRefresh, setAutoRefresh] = useState(true);

	// Service status query with auto-refresh
	const { data: status, isLoading: statusLoading } = useQuery<ServiceStatus>({
		queryKey: ['serviceStatus'],
		queryFn: getServiceStatus,
		refetchInterval: (query) => {
			if (!autoRefresh) return false;
			const data = query.state.data;
			return data?.service_running ? 5000 : false; // Refresh every 5s if running
		},
	});

	// Task history query
	const { data: taskHistory, isLoading: tasksLoading } = useQuery({
		queryKey: ['serviceTasks'],
		queryFn: () => getTaskHistory({ limit: 50 }),
		refetchInterval: autoRefresh ? 10000 : false, // Refresh every 10s
	});

	// Service logs query
	const { data: logs, isLoading: logsLoading } = useQuery({
		queryKey: ['serviceLogs'],
		queryFn: () => getServiceLogs({ limit: 100, hours: 24 }),
		refetchInterval: autoRefresh ? 15000 : false, // Refresh every 15s
	});

	// Individual services status query
	const { data: individualStatus } = useQuery<IndividualServicesStatus>({
		queryKey: ['individualServicesStatus'],
		queryFn: getIndividualServicesStatus,
		refetchInterval: autoRefresh ? 5000 : false, // Refresh every 5s
	});

	// Start/stop mutations
	const startMutation = useMutation({
		mutationFn: startService,
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['serviceStatus'] });
			qc.invalidateQueries({ queryKey: ['serviceTasks'] });
			qc.invalidateQueries({ queryKey: ['serviceLogs'] });
		},
	});

	const stopMutation = useMutation({
		mutationFn: stopService,
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['serviceStatus'] });
			qc.invalidateQueries({ queryKey: ['serviceTasks'] });
			qc.invalidateQueries({ queryKey: ['serviceLogs'] });
		},
	});

	useEffect(() => {
		document.title = 'Service Status';
	}, []);

	if (statusLoading) {
		return <div className="p-4">Loading service status...</div>;
	}

	const isRunning = status?.service_running ?? false;
	const lastHeartbeat = status?.last_heartbeat ? new Date(status.last_heartbeat) : null;
	const lastTaskExecution = status?.last_task_execution ? new Date(status.last_task_execution) : null;

	// Check if any individual service is running or any run-once is running
	const services = individualStatus?.services || {};
	const anyIndividualServiceRunning = Object.values(services).some(service => service.is_running);
	const anyRunOnceRunning = Object.values(services).some(service => service.last_execution_status === 'running');

	return (
		<div className="p-4 space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold text-[var(--text)]">Service Status</h1>
				<label className="flex items-center gap-2 text-sm text-[var(--text)]">
					<input
						type="checkbox"
						checked={autoRefresh}
						onChange={(e) => setAutoRefresh(e.target.checked)}
						className="accent-blue-600"
					/>
					<span>Auto-refresh</span>
				</label>
			</div>

			{/* Service Status Card */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-lg font-semibold text-[var(--text)]">Service Health</h2>
					<div className={`px-3 py-1 rounded-full text-sm font-medium ${isRunning ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
						{isRunning ? '✓ Running' : '✗ Stopped'}
					</div>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
					<div>
						<div className="text-sm text-[var(--muted)] mb-1">Last Heartbeat</div>
						<div className="text-sm text-[var(--text)]">
							{lastHeartbeat ? (
								<>
									{lastHeartbeat.toLocaleString()}
									<span className="text-[var(--muted)] ml-2">
										({formatTimeAgo(Math.floor((Date.now() - lastHeartbeat.getTime()) / 1000))})
									</span>
								</>
							) : (
								<span className="text-[var(--muted)]">Never</span>
							)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)] mb-1">Last Task Execution</div>
						<div className="text-sm text-[var(--text)]">
							{lastTaskExecution ? (
								<>
									{lastTaskExecution.toLocaleString()}
									<span className="text-[var(--muted)] ml-2">
										({formatTimeAgo(Math.floor((Date.now() - lastTaskExecution.getTime()) / 1000))})
									</span>
								</>
							) : (
								<span className="text-[var(--muted)]">Never</span>
							)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)] mb-1">Error Count</div>
						<div className={`text-sm font-medium ${status?.error_count && status.error_count > 0 ? 'text-red-400' : 'text-green-400'}`}>
							{status?.error_count ?? 0}
						</div>
					</div>
				</div>

				{status?.last_error && (
					<div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded">
						<div className="text-sm font-medium text-red-400 mb-1">Last Error</div>
						<div className="text-sm text-red-300">{status.last_error}</div>
					</div>
				)}

				{/* Service Controls */}
				<div className="mt-6">
					<ServiceControls
						isRunning={isRunning}
						onStart={() => startMutation.mutate()}
						onStop={() => stopMutation.mutate()}
						isStarting={startMutation.isPending}
						isStopping={stopMutation.isPending}
						anyIndividualServiceRunning={anyIndividualServiceRunning}
						anyRunOnceRunning={anyRunOnceRunning}
					/>
				</div>
			</div>

			{/* Individual Services Section */}
			<IndividualServicesSection unifiedServiceRunning={isRunning} />

			{/* Task Execution History */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
				<h2 className="text-lg font-semibold mb-4 text-[var(--text)]">Task Execution History</h2>
				<ServiceTasksTable tasks={taskHistory?.tasks ?? []} isLoading={tasksLoading} />
			</div>

			{/* Service Logs */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
				<h2 className="text-lg font-semibold mb-4 text-[var(--text)]">Recent Service Logs</h2>
				<ServiceLogsViewer logs={logs?.logs ?? []} isLoading={logsLoading} />
			</div>
		</div>
	);
}
