import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
	getAdminErrorLogs,
	getAdminLogs,
	getUserErrorLogs,
	getUserLogs,
	resolveErrorLog,
	type ErrorLogEntry,
	type ServiceLogEntry,
} from '@/api/logs';
import { LogTable } from './LogTable';
import { ErrorLogTable } from './ErrorLogTable';
import { LogExportButton } from './LogExportButton';
import { QuickFilters } from './QuickFilters';
import { ModuleAutocomplete } from './ModuleAutocomplete';
import { UserAutocomplete } from './UserAutocomplete';
import { useSessionStore } from '@/state/sessionStore';

type DateFilters = {
	start: string;
	end: string;
};

const LEVELS = ['', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

function toIso(value: string) {
	if (!value) return undefined;
	const date = new Date(value);
	return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

export function LogViewerPage() {
	const { isAdmin } = useSessionStore();
	const queryClient = useQueryClient();

	const [logFilters, setLogFilters] = useState({
		level: '',
		module: '',
		search: '',
		limit: 200,
	});
	const [logDates, setLogDates] = useState<DateFilters>({ start: '', end: '' });
	const [scope, setScope] = useState<'self' | 'all'>('self');
	const [adminUserFilter, setAdminUserFilter] = useState('');
	const [tailMode, setTailMode] = useState(false);
	const [daysBack, setDaysBack] = useState<number | undefined>(undefined);
	const [isRefreshing, setIsRefreshing] = useState(false);
	const [isScrolledUp, setIsScrolledUp] = useState(false);
	const [showId, setShowId] = useState(false);
	const [searchInContext, setSearchInContext] = useState(false);
	const tableContainerRef = useRef<HTMLDivElement>(null);

	const [errorFilters, setErrorFilters] = useState({
		resolved: 'all',
		search: '',
		limit: 100,
	});
	const [errorDates, setErrorDates] = useState<DateFilters>({ start: '', end: '' });

	const logQueryKey = useMemo(
		() => ['logs', logFilters, logDates, scope, adminUserFilter, isAdmin, tailMode, daysBack],
		[logFilters, logDates, scope, adminUserFilter, isAdmin, tailMode, daysBack]
	);

	const logsQuery = useQuery<ServiceLogEntry[]>({
		queryKey: logQueryKey,
		queryFn: () => {
			const params = {
				level: logFilters.level || undefined,
				module: logFilters.module || undefined,
				search: logFilters.search || undefined,
				start_time: tailMode ? undefined : toIso(logDates.start),
				end_time: tailMode ? undefined : toIso(logDates.end),
				limit: logFilters.limit,
				tail: tailMode ? true : undefined,
				days_back: daysBack,
			};
			if (isAdmin && scope === 'all') {
				return getAdminLogs({
					...params,
					user_id: adminUserFilter ? Number(adminUserFilter) : undefined,
				});
			}
			return getUserLogs(params);
		},
		refetchInterval: tailMode && !isScrolledUp ? 3000 : false,
		refetchOnWindowFocus: tailMode && !isScrolledUp,
	});

	// Handle auto-refresh indicator
	useEffect(() => {
		if (tailMode && logsQuery.isFetching) {
			setIsRefreshing(true);
			const timer = setTimeout(() => setIsRefreshing(false), 500);
			return () => clearTimeout(timer);
		}
		setIsRefreshing(false);
	}, [tailMode, logsQuery.isFetching]);

	// Disable date filters when tail mode is active
	useEffect(() => {
		if (tailMode) {
			setDaysBack(undefined);
		}
	}, [tailMode]);

	// Scroll detection to pause auto-refresh
	useEffect(() => {
		if (!tailMode || !tableContainerRef.current) return;

		const container = tableContainerRef.current;
		let lastScrollTop = container.scrollTop;

		const handleScroll = () => {
			const currentScrollTop = container.scrollTop;
			const scrollHeight = container.scrollHeight;
			const clientHeight = container.clientHeight;
			const isAtBottom = scrollHeight - currentScrollTop - clientHeight < 50; // 50px threshold

			// If user scrolls up, pause refresh
			if (currentScrollTop < lastScrollTop && !isAtBottom) {
				setIsScrolledUp(true);
			} else if (isAtBottom) {
				// If user scrolls back to bottom, resume refresh
				setIsScrolledUp(false);
			}

			lastScrollTop = currentScrollTop;
		};

		container.addEventListener('scroll', handleScroll);
		return () => container.removeEventListener('scroll', handleScroll);
	}, [tailMode]);

	// Handle quick filter application
	const handleQuickFilter = (filter: {
		level?: string;
		startTime?: string;
		endTime?: string;
		daysBack?: number;
	}) => {
		if (filter.level) {
			setLogFilters((prev) => ({ ...prev, level: filter.level! }));
		}
		if (filter.startTime && filter.endTime) {
			const startDate = new Date(filter.startTime);
			const endDate = new Date(filter.endTime);
			setLogDates({
				start: startDate.toISOString().split('T')[0],
				end: endDate.toISOString().split('T')[0],
			});
			setDaysBack(undefined);
		}
		if (filter.daysBack !== undefined) {
			setDaysBack(filter.daysBack);
			setLogDates({ start: '', end: '' });
		}
		setTailMode(false); // Disable tail mode when applying filters
		setIsScrolledUp(false); // Reset scroll state
	};

	const handleClearFilters = () => {
		setLogFilters({ level: '', module: '', search: '', limit: 200 });
		setLogDates({ start: '', end: '' });
		setDaysBack(undefined);
		setTailMode(false);
	};

	const errorQueryKey = useMemo(
		() => ['errors', errorFilters, errorDates, scope, adminUserFilter, isAdmin],
		[errorFilters, errorDates, scope, adminUserFilter, isAdmin]
	);

	const errorsQuery = useQuery<ErrorLogEntry[]>({
		queryKey: errorQueryKey,
		queryFn: () => {
			const params = {
				resolved:
					errorFilters.resolved === 'all' ? undefined : errorFilters.resolved === 'true',
				search: errorFilters.search || undefined,
				start_time: toIso(errorDates.start),
				end_time: toIso(errorDates.end),
				limit: errorFilters.limit,
			};
			if (isAdmin && scope === 'all') {
				return getAdminErrorLogs({
					...params,
					user_id: adminUserFilter ? Number(adminUserFilter) : undefined,
				});
			}
			return getUserErrorLogs(params);
		},
	});

	const resolveMutation = useMutation({
		mutationFn: ({ id, notes }: { id: number; notes?: string }) =>
			resolveErrorLog(id, { notes }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: errorQueryKey });
		},
	});

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<div>
					<h1 className="text-lg sm:text-xl font-semibold">Log Management</h1>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Search structured service logs and error reports. Admins can switch to a global view to
						triage issues across users.
					</p>
				</div>
			</div>

			<div className="grid gap-4 sm:gap-6">
				<section className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4 space-y-3 sm:space-y-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-2">
						<h2 className="text-base sm:text-lg font-semibold">Service Logs</h2>
						<div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 text-sm w-full sm:w-auto">
							<LogExportButton logs={logsQuery.data ?? []} />
							<label className="flex flex-col sm:flex-row items-start sm:items-center gap-1 sm:gap-2">
								<span className="text-xs sm:text-sm whitespace-nowrap">Live Tail</span>
								<button
									type="button"
									onClick={() => setTailMode(!tailMode)}
									className={`px-3 py-2 sm:px-2 sm:py-1 rounded min-h-[44px] sm:min-h-0 transition-colors ${
										tailMode
											? 'bg-green-600 hover:bg-green-700 text-white'
											: 'bg-[#0f172a] border border-[#1f2937] text-[var(--muted)] hover:bg-[#1a2332]'
									}`}
								>
									{tailMode ? '● Live' : '○ Off'}
								</button>
							</label>
							{isAdmin && (
								<>
									<label className="flex flex-col sm:flex-row items-start sm:items-center gap-1 sm:gap-2">
										<span className="text-xs sm:text-sm whitespace-nowrap">Scope</span>
										<select
											value={scope}
											onChange={(event) => setScope(event.target.value as 'self' | 'all')}
											className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 w-full sm:w-auto"
										>
											<option value="self">My Logs</option>
											<option value="all">All Users</option>
										</select>
									</label>
									{scope === 'all' && (
										<label className="flex flex-col sm:flex-row items-start sm:items-center gap-1 sm:gap-2">
											<span className="text-xs sm:text-sm whitespace-nowrap">User</span>
											<UserAutocomplete
												value={adminUserFilter}
												onChange={setAdminUserFilter}
												placeholder="Any"
											/>
										</label>
									)}
								</>
							)}
						</div>
					</div>

					<QuickFilters onFilter={handleQuickFilter} onClear={handleClearFilters} />

					<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Level</span>
							<select
								value={logFilters.level}
								onChange={(event) =>
									setLogFilters((prev) => ({ ...prev, level: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							>
								{LEVELS.map((level) => (
									<option key={level || 'any'} value={level}>
										{level || 'Any'}
									</option>
								))}
							</select>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Module</span>
							<ModuleAutocomplete
								logs={logsQuery.data ?? []}
								value={logFilters.module}
								onChange={(value) => setLogFilters((prev) => ({ ...prev, module: value }))}
								placeholder="scheduler"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Search</span>
							<div className="flex flex-col gap-1">
								<input
									value={logFilters.search}
									onChange={(event) =>
										setLogFilters((prev) => ({ ...prev, search: event.target.value }))
									}
									className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
									placeholder="keyword"
								/>
								<label className="flex items-center gap-1 text-xs text-[var(--muted)]">
									<input
										type="checkbox"
										checked={searchInContext}
										onChange={(e) => setSearchInContext(e.target.checked)}
										className="w-3 h-3"
									/>
									Search in context
								</label>
							</div>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Limit</span>
							<input
								type="number"
								min={1}
								max={1000}
								value={logFilters.limit}
								onChange={(event) =>
									setLogFilters((prev) => ({
										...prev,
										limit: Number(event.target.value),
									}))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							/>
						</label>
					</div>

					{!tailMode && (
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
							<label className="flex flex-col gap-1">
								<span className="text-xs sm:text-sm">Days Back</span>
								<select
									value={daysBack || ''}
									onChange={(event) =>
										setDaysBack(event.target.value ? Number(event.target.value) : undefined)
									}
									className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
								>
									<option value="">Custom Date Range</option>
									<option value="1">Last 1 day</option>
									<option value="3">Last 3 days</option>
									<option value="7">Last 7 days</option>
									<option value="14">Last 14 days</option>
								</select>
							</label>
							<label className="flex flex-col gap-1">
								<span className="text-xs sm:text-sm">Start Date</span>
								<input
									type="date"
									value={logDates.start}
									onChange={(event) =>
										setLogDates((prev) => ({ ...prev, start: event.target.value }))
									}
									disabled={!!daysBack}
									className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 disabled:opacity-50 disabled:cursor-not-allowed"
								/>
							</label>
							<label className="flex flex-col gap-1">
								<span className="text-xs sm:text-sm">End Date</span>
								<input
									type="date"
									value={logDates.end}
									onChange={(event) =>
										setLogDates((prev) => ({ ...prev, end: event.target.value }))
									}
									disabled={!!daysBack}
									className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 disabled:opacity-50 disabled:cursor-not-allowed"
								/>
							</label>
						</div>
					)}

					{tailMode && (
						<div className="text-xs text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded p-2">
							{isScrolledUp ? (
								<span>⏸ Live tail paused - scroll to bottom to resume</span>
							) : (
								<span>● Live tail mode active - showing last 200 lines, auto-refreshing every 3 seconds</span>
							)}
						</div>
					)}

					<div className="flex items-center justify-between mb-2">
						<label className="flex items-center gap-2 text-xs sm:text-sm">
							<input
								type="checkbox"
								checked={showId}
								onChange={(e) => setShowId(e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-[var(--muted)]">Show Log IDs</span>
						</label>
					</div>

					<div ref={tableContainerRef} className="max-h-[600px] overflow-y-auto">
						<LogTable
							logs={logsQuery.data ?? []}
							isLoading={logsQuery.isLoading}
							isRefreshing={isRefreshing}
							showId={showId}
							searchTerm={searchInContext && logFilters.search ? logFilters.search : undefined}
						/>
					</div>
				</section>

				<section className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4 space-y-3 sm:space-y-4">
					<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-2">
						<h2 className="text-base sm:text-lg font-semibold">Error Logs</h2>
						<div className="text-xs text-[var(--muted)]">
							Click "Show Details" to inspect tracebacks and resolution notes.
						</div>
					</div>

					<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Status</span>
							<select
								value={errorFilters.resolved}
								onChange={(event) =>
									setErrorFilters((prev) => ({ ...prev, resolved: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							>
								<option value="all">All</option>
								<option value="false">Unresolved</option>
								<option value="true">Resolved</option>
							</select>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Search</span>
							<input
								value={errorFilters.search}
								onChange={(event) =>
									setErrorFilters((prev) => ({ ...prev, search: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
								placeholder="message contains..."
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Limit</span>
							<input
								type="number"
								min={1}
								max={500}
								value={errorFilters.limit}
								onChange={(event) =>
									setErrorFilters((prev) => ({
										...prev,
										limit: Number(event.target.value),
									}))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							/>
						</label>
					</div>

					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">Start Date</span>
							<input
								type="date"
								value={errorDates.start}
								onChange={(event) =>
									setErrorDates((prev) => ({ ...prev, start: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span className="text-xs sm:text-sm">End Date</span>
							<input
								type="date"
								value={errorDates.end}
								onChange={(event) =>
									setErrorDates((prev) => ({ ...prev, end: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0"
							/>
						</label>
					</div>

					<ErrorLogTable
						errors={errorsQuery.data ?? []}
						isLoading={errorsQuery.isLoading}
						isAdmin={isAdmin && scope === 'all'}
						onResolve={
							isAdmin && scope === 'all'
								? (error) => {
										const notes = window.prompt(
											'Add optional resolution notes:',
											error.resolution_notes ?? ''
										);
										resolveMutation.mutate({ id: error.id, notes: notes ?? undefined });
								  }
								: undefined
						}
					/>
				</section>
			</div>
		</div>
	);
}
