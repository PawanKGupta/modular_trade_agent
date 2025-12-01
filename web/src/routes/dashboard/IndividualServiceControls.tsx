import { useState } from 'react';
import {
	type IndividualServiceStatus,
	type IndividualServicesStatus,
	startIndividualService,
	stopIndividualService,
	runTaskOnce,
} from '@/api/service';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { formatTimeAgo, formatDuration } from '@/utils/time';

interface IndividualServiceControlsProps {
	service: IndividualServiceStatus;
	unifiedServiceRunning: boolean;
}

const TASK_DISPLAY_NAMES: Record<string, string> = {
	premarket_retry: 'Pre-market Retry',
	sell_monitor: 'Sell Monitor',
	position_monitor: 'Position Monitor',
	analysis: 'Analysis',
	buy_orders: 'Buy Orders',
	eod_cleanup: 'End-of-Day Cleanup',
};

const TASK_DESCRIPTIONS: Record<string, string> = {
	premarket_retry: 'Retries failed orders from previous day',
	sell_monitor: 'Places sell orders and monitors them continuously',
	position_monitor: 'Monitors positions hourly for reentry/exit signals',
	analysis: 'Analyzes stocks and generates recommendations',
	buy_orders: 'Places AMO buy orders for the next day',
	eod_cleanup: 'End-of-day cleanup and reset for the next day',
};

export function IndividualServiceControls({
	service,
	unifiedServiceRunning,
}: IndividualServiceControlsProps) {
	const renderTimestamp = (timestamp: string) => {
		const date = new Date(timestamp);
		const secondsDiff = Math.floor((Date.now() - date.getTime()) / 1000);
		const relative = formatTimeAgo(secondsDiff);
		return (
			<>
				{date.toLocaleString()}
				<span className="text-[var(--muted)] ml-2 text-xs">({relative})</span>
			</>
		);
	};
	const qc = useQueryClient();
	const [showConflictWarning, setShowConflictWarning] = useState(false);
	const [conflictMessage, setConflictMessage] = useState<string | null>(null);

	const startMutation = useMutation({
		mutationFn: (taskName: string) => startIndividualService({ task_name: taskName }),
		onSuccess: (response, taskName) => {
			if (response.success) {
				qc.setQueryData<IndividualServicesStatus>(
					['individualServicesStatus'],
					(old) => {
						if (!old || !old.services || !old.services[taskName]) {
							return old;
						}
						return {
							...old,
							services: {
								...old.services,
								[taskName]: {
									...old.services[taskName],
									is_running: true,
									started_at: new Date().toISOString(),
								},
							},
						};
					}
				);
				setTimeout(() => {
					qc.refetchQueries({ queryKey: ['individualServicesStatus'] });
				}, 500);
			}
			qc.invalidateQueries({ queryKey: ['serviceTasks'] });
		},
	});

	const stopMutation = useMutation({
		mutationFn: (taskName: string) => stopIndividualService({ task_name: taskName }),
		onSuccess: (response, taskName) => {
			if (response.success) {
				// Optimistically update the cache immediately
				qc.setQueryData<IndividualServicesStatus>(
					['individualServicesStatus'],
					(old) => {
						if (!old || !old.services || !old.services[taskName]) return old;
						return {
							...old,
							services: {
								...old.services,
								[taskName]: {
									...old.services[taskName],
									is_running: false,
									started_at: null,
								},
							},
						};
					}
				);
				// Refetch after a delay to get the latest data from server
				setTimeout(() => {
					qc.refetchQueries({ queryKey: ['individualServicesStatus'] });
				}, 500);
			}
			qc.invalidateQueries({ queryKey: ['serviceTasks'] });
		},
	});

	const runOnceMutation = useMutation({
		mutationFn: (taskName: string) => runTaskOnce({ task_name: taskName }),
		onSuccess: (response) => {
			// Handle backend rejection (e.g., unified service conflict)
			if (!response.success) {
				setConflictMessage(response.message || 'Task execution failed');
				setShowConflictWarning(true);
				setTimeout(() => setShowConflictWarning(false), 8000);
				return;
			}

			// Handle warning conflicts (still successful)
			if (response.has_conflict) {
				setConflictMessage(response.conflict_message || 'Conflict detected');
				setShowConflictWarning(true);
				setTimeout(() => setShowConflictWarning(false), 5000);
			}
			qc.invalidateQueries({ queryKey: ['individualServicesStatus'] });
			qc.invalidateQueries({ queryKey: ['serviceTasks'] });
			qc.invalidateQueries({ queryKey: ['buying-zone'] });
		},
	});

	const taskDisplayName = TASK_DISPLAY_NAMES[service.task_name] || service.task_name;
	const taskDescription = TASK_DESCRIPTIONS[service.task_name] || '';
	const lastSummary =
		(service.last_execution_details?.analysis_summary as
			| {
					inserted?: number;
					updated?: number;
					skipped?: number;
					processed?: number;
					error?: string;
				}
			| undefined) ?? undefined;

	// "Run Once" is disabled if service is running OR if there's a "running" execution
	const isRunOnceRunning = service.last_execution_status === 'running';
	// Service is considered "running" if either the scheduled service is running OR a run-once execution is in progress
	const isServiceActive = service.is_running || isRunOnceRunning;
	// Disable individual service start button if unified service is running, service is already running, or run-once is running
	const canStartIndividual = !unifiedServiceRunning && !service.is_running && !isRunOnceRunning;

	// Run-once is blocked if unified service is running (except for analysis which doesn't need broker session)
	const isBlockedByUnifiedService = unifiedServiceRunning && service.task_name !== 'analysis';
	const canRunOnce = !service.is_running && !isRunOnceRunning && !isBlockedByUnifiedService;

	const handleRunOnce = () => {
		// No warning dialog needed - backend enforces the block
		runOnceMutation.mutate(service.task_name);
	};

	const handleStart = () => {
		startMutation.mutate(service.task_name);
	};

	const handleStop = () => {
		stopMutation.mutate(service.task_name);
	};

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4">
			<div className="flex items-start justify-between mb-3">
				<div className="flex-1">
					<div className="flex items-center gap-2 mb-1">
						<h3 className="text-base font-semibold text-[var(--text)]">{taskDisplayName}</h3>
						<div
							className={`px-2 py-0.5 rounded text-xs font-medium ${
								isServiceActive
									? 'bg-green-500/20 text-green-400'
									: 'bg-gray-500/20 text-gray-400'
							}`}
						>
							{isServiceActive ? 'Running' : 'Stopped'}
						</div>
						{!service.schedule_enabled && (
							<div className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">
								Disabled
							</div>
						)}
					</div>
					{taskDescription && (
						<p className="text-sm text-[var(--muted)] mb-2">{taskDescription}</p>
					)}
				</div>
			</div>

			{/* Status Info */}
			<div className="grid grid-cols-2 gap-3 mb-3 text-sm">
				{service.last_execution_at && (
					<div>
						<div className="text-[var(--muted)] mb-1">Last Execution</div>
						<div className="text-[var(--text)]">{renderTimestamp(service.last_execution_at)}</div>
					</div>
				)}
				{service.next_execution_at && (
					<div>
						<div className="text-[var(--muted)] mb-1">Next Execution</div>
						<div className="text-[var(--text)]">{renderTimestamp(service.next_execution_at)}</div>
					</div>
				)}
			</div>
			{service.last_execution_status && (
				<div className="mb-3">
					<div className="text-[var(--muted)] mb-1">Last Result</div>
					<div
						className={`text-sm font-medium ${
							service.last_execution_status === 'success'
								? 'text-green-400'
								: service.last_execution_status === 'failed'
									? 'text-red-400'
									: service.last_execution_status === 'running'
										? 'text-blue-400'
										: 'text-yellow-400'
						}`}
					>
						{service.last_execution_status === 'success'
							? 'Success'
							: service.last_execution_status === 'failed'
								? 'Failed'
								: service.last_execution_status === 'running'
									? 'Running'
									: 'Skipped'}
						{typeof service.last_execution_duration === 'number' &&
							` - ${formatDuration(service.last_execution_duration)}`}
					</div>
					{lastSummary && (
						<div className="text-xs text-[var(--muted)] mt-1">
							Processed {lastSummary.processed ?? 0} - Inserted {lastSummary.inserted ?? 0} - Updated{' '}
							{lastSummary.updated ?? 0}
							{lastSummary.error && <span className="text-red-400 ml-1">({lastSummary.error})</span>}
						</div>
					)}
				</div>
			)}

			{/* Conflict Warning */}
			{showConflictWarning && conflictMessage && (
				<div className="mb-3 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-sm text-yellow-400">
					⚠ {conflictMessage}
				</div>
			)}

			{/* Action Buttons */}
			<div className="flex gap-2">
				<button
					onClick={handleStart}
					disabled={!canStartIndividual || startMutation.isPending || stopMutation.isPending}
					className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
						!canStartIndividual || startMutation.isPending || stopMutation.isPending
							? 'bg-gray-600 text-gray-400 cursor-not-allowed'
							: 'bg-green-600 hover:bg-green-700 text-white'
					}`}
					title={
						unifiedServiceRunning
							? 'Cannot start individual service when unified service is running'
							: service.is_running
								? 'Service is already running'
								: isRunOnceRunning
									? 'Cannot start service while run-once task is executing'
									: 'Start this service'
					}
				>
					{startMutation.isPending ? 'Starting...' : 'Start Service'}
				</button>
				<button
					onClick={handleStop}
					disabled={!service.is_running || startMutation.isPending || stopMutation.isPending}
					className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
						!service.is_running || startMutation.isPending || stopMutation.isPending
							? 'bg-gray-600 text-gray-400 cursor-not-allowed'
							: 'bg-red-600 hover:bg-red-700 text-white'
					}`}
				>
					{stopMutation.isPending ? 'Stopping...' : 'Stop Service'}
				</button>
				<button
					onClick={handleRunOnce}
					disabled={!canRunOnce || runOnceMutation.isPending || isRunOnceRunning}
					className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
						!canRunOnce || runOnceMutation.isPending || isRunOnceRunning
							? 'bg-gray-600 text-gray-400 cursor-not-allowed'
							: 'bg-blue-600 hover:bg-blue-700 text-white'
					}`}
					title={
						service.is_running
							? 'Service is already running'
							: isRunOnceRunning
								? 'Task is currently running'
								: isBlockedByUnifiedService
									? 'Cannot run while unified service is active (would cause session conflicts). Stop unified service first.'
									: 'Run this task once immediately'
					}
				>
					{runOnceMutation.isPending || isRunOnceRunning ? 'Running...' : 'Run Once'}
				</button>
			</div>
		</div>
	);
}
