import { useEffect, useMemo, useRef, useState } from 'react';
import {
	type IndividualServiceStatus,
	type IndividualServicesStatus,
	startIndividualService,
	stopIndividualService,
	runTaskOnce,
} from '@/api/service';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { formatApiTimestampDisplay, formatDuration } from '@/utils/time';

interface IndividualServiceControlsProps {
	service: IndividualServiceStatus;
	unifiedServiceRunning: boolean;
}

const TASK_DISPLAY_NAMES: Record<string, string> = {
	premarket_retry: 'Pre-market Retry',
	sell_monitor: 'Sell Monitor',
	analysis: 'Analysis',
	buy_orders: 'Buy Orders',
	buy_margin_preview: 'Buy Margin Preview',
	eod_cleanup: 'End-of-Day Cleanup',
};

const TASK_DESCRIPTIONS: Record<string, string> = {
	premarket_retry: 'Retries failed buy orders after morning placement (default 9:03 AM IST)',
	sell_monitor: 'Monitors sell orders continuously, converts to market on RSI exit',
	analysis: 'Analyzes stocks and generates recommendations',
	buy_orders: 'Places REGULAR buy orders at market open (default 9:01 AM IST)',
	buy_margin_preview:
		'Evening margin preview for next-morning buys — notify only, no placement (default 4:05 PM IST)',
	eod_cleanup: 'End-of-day cleanup and reset for the next day',
};

export function IndividualServiceControls({
	service,
	unifiedServiceRunning,
}: IndividualServiceControlsProps) {
	const renderTimestamp = (timestamp: string) => formatApiTimestampDisplay(timestamp);
	const qc = useQueryClient();
	const [conflictMessage, setConflictMessage] = useState<string | null>(null);
	const [conflictStickyWhileRunning, setConflictStickyWhileRunning] = useState(false);
	const [runOnceLocalStartedAt, setRunOnceLocalStartedAt] = useState<string | null>(null);
	const [nowMs, setNowMs] = useState(() => Date.now());
	const conflictDismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const clearConflictDismissTimer = () => {
		if (conflictDismissTimerRef.current) {
			clearTimeout(conflictDismissTimerRef.current);
			conflictDismissTimerRef.current = null;
		}
	};

	const scheduleConflictDismiss = (delayMs: number) => {
		clearConflictDismissTimer();
		conflictDismissTimerRef.current = setTimeout(() => {
			setConflictMessage(null);
			setConflictStickyWhileRunning(false);
			conflictDismissTimerRef.current = null;
		}, delayMs);
	};

	useEffect(() => () => clearConflictDismissTimer(), []);

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
		onSuccess: (response, taskName) => {
			// Handle backend rejection (e.g., unified service conflict)
			if (!response.success) {
				setConflictStickyWhileRunning(false);
				setConflictMessage(response.message || 'Task execution failed');
				scheduleConflictDismiss(8000);
				return;
			}

			// Optimistic running state until polling confirms completion
			qc.setQueryData<IndividualServicesStatus>(['individualServicesStatus'], (old) => {
				if (!old?.services?.[taskName]) {
					return old;
				}
				return {
					...old,
					services: {
						...old.services,
						[taskName]: {
							...old.services[taskName],
							last_execution_status: 'running',
							current_run_started_at: new Date().toISOString(),
						},
					},
				};
			});

			// Keep advisory conflict visible for the whole run (not a short auto-dismiss)
			if (response.has_conflict) {
				clearConflictDismissTimer();
				setConflictMessage(response.conflict_message || 'Conflict detected');
				setConflictStickyWhileRunning(true);
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

	// Run-once in progress (API status or optimistic state right after click)
	const isRunOnceRunning =
		service.last_execution_status === 'running' || runOnceMutation.isPending;

	const prevIsRunOnceRunningRef = useRef(false);

	useEffect(() => {
		if (!isRunOnceRunning) {
			setRunOnceLocalStartedAt(null);
			return;
		}
		const id = setInterval(() => setNowMs(Date.now()), 1000);
		return () => clearInterval(id);
	}, [isRunOnceRunning]);

	useEffect(() => {
		const wasRunning = prevIsRunOnceRunningRef.current;
		prevIsRunOnceRunningRef.current = isRunOnceRunning;
		if (wasRunning && !isRunOnceRunning && conflictStickyWhileRunning) {
			setConflictStickyWhileRunning(false);
			scheduleConflictDismiss(30_000);
		}
	}, [isRunOnceRunning, conflictStickyWhileRunning]);

	const runStartedAtMs = useMemo(() => {
		if (!isRunOnceRunning) {
			return null;
		}
		const candidateMs: number[] = [];
		if (service.current_run_started_at) {
			candidateMs.push(new Date(service.current_run_started_at).getTime());
		}
		if (runOnceLocalStartedAt) {
			candidateMs.push(new Date(runOnceLocalStartedAt).getTime());
		}
		if (candidateMs.length === 0) {
			return null;
		}
		return Math.max(...candidateMs);
	}, [isRunOnceRunning, service.current_run_started_at, runOnceLocalStartedAt]);

	const currentRunDurationLabel = useMemo(() => {
		if (!isRunOnceRunning) {
			return null;
		}
		if (runStartedAtMs == null) {
			return formatDuration(0);
		}
		const elapsedSeconds = Math.max(0, (nowMs - runStartedAtMs) / 1000);
		return formatDuration(elapsedSeconds);
	}, [isRunOnceRunning, runStartedAtMs, nowMs]);

	const lastResultDurationLabel = useMemo(() => {
		if (isRunOnceRunning || typeof service.last_execution_duration !== 'number') {
			return null;
		}
		return formatDuration(service.last_execution_duration);
	}, [isRunOnceRunning, service.last_execution_duration]);

	const durationLabel = currentRunDurationLabel ?? lastResultDurationLabel;

	const showConflictBanner = Boolean(conflictMessage);
	// Service is considered "running" if either the scheduled service is running OR a run-once execution is in progress
	const isServiceActive = service.is_running || isRunOnceRunning;
	// Disable individual service start button if unified service is running, service is already running, or run-once is running
	const canStartIndividual = !unifiedServiceRunning && !service.is_running && !isRunOnceRunning;

	// Run-once is blocked if unified service is running (except for analysis which doesn't need broker session)
	const isBlockedByUnifiedService = unifiedServiceRunning && service.task_name !== 'analysis';
	const canRunOnce = !service.is_running && !isRunOnceRunning && !isBlockedByUnifiedService;

	const handleRunOnce = () => {
		// No warning dialog needed - backend enforces the block
		setRunOnceLocalStartedAt(new Date().toISOString());
		runOnceMutation.mutate(service.task_name);
	};

	const handleStart = () => {
		startMutation.mutate(service.task_name);
	};

	const handleStop = () => {
		stopMutation.mutate(service.task_name);
	};

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4">
			<div className="flex items-start justify-between mb-2 sm:mb-3">
				<div className="flex-1">
					<div className="flex flex-wrap items-center gap-2 mb-1">
						<h3 className="text-sm sm:text-base font-semibold text-[var(--text)]">{taskDisplayName}</h3>
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
						<p className="text-xs sm:text-sm text-[var(--muted)] mb-2">{taskDescription}</p>
					)}
				</div>
			</div>

			{/* Status Info */}
			<div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 mb-2 sm:mb-3 text-xs sm:text-sm">
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
			{(service.last_execution_status || isRunOnceRunning) && (
				<div className="mb-3">
					<div className="text-[var(--muted)] mb-1">
						{isRunOnceRunning ? 'Current Run' : 'Last Result'}
					</div>
					<div
						className={`text-sm font-medium ${
							isRunOnceRunning || service.last_execution_status === 'running'
								? 'text-blue-400'
								: service.last_execution_status === 'success'
									? 'text-green-400'
									: service.last_execution_status === 'failed'
										? 'text-red-400'
										: 'text-yellow-400'
						}`}
					>
						{isRunOnceRunning || service.last_execution_status === 'running'
							? 'Running'
							: service.last_execution_status === 'success'
								? 'Success'
								: service.last_execution_status === 'failed'
									? 'Failed'
									: 'Skipped'}
						{durationLabel && ` - ${durationLabel}`}
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
			{showConflictBanner && conflictMessage && (
				<div className="mb-2 sm:mb-3 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs sm:text-sm text-yellow-400">
					⚠ {conflictMessage}
				</div>
			)}

			{/* Action Buttons */}
			<div className="flex flex-col sm:flex-row gap-2">
				<button
					onClick={handleStart}
					disabled={!canStartIndividual || startMutation.isPending || stopMutation.isPending}
					className={`px-3 py-2.5 sm:py-1.5 rounded text-xs sm:text-sm font-medium transition-colors min-h-[44px] sm:min-h-0 ${
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
					className={`px-3 py-2.5 sm:py-1.5 rounded text-xs sm:text-sm font-medium transition-colors min-h-[44px] sm:min-h-0 ${
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
					className={`px-3 py-2.5 sm:py-1.5 rounded text-xs sm:text-sm font-medium transition-colors min-h-[44px] sm:min-h-0 ${
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
