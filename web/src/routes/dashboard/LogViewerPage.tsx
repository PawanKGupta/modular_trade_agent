import { useMemo, useState } from 'react';
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

	const [errorFilters, setErrorFilters] = useState({
		resolved: 'all',
		search: '',
		limit: 100,
	});
	const [errorDates, setErrorDates] = useState<DateFilters>({ start: '', end: '' });

	const logQueryKey = useMemo(
		() => ['logs', logFilters, logDates, scope, adminUserFilter, isAdmin],
		[logFilters, logDates, scope, adminUserFilter, isAdmin]
	);

	const logsQuery = useQuery<ServiceLogEntry[]>({
		queryKey: logQueryKey,
		queryFn: () => {
			const params = {
				level: logFilters.level || undefined,
				module: logFilters.module || undefined,
				search: logFilters.search || undefined,
				start_time: toIso(logDates.start),
				end_time: toIso(logDates.end),
				limit: logFilters.limit,
			};
			if (isAdmin && scope === 'all') {
				return getAdminLogs({
					...params,
					user_id: adminUserFilter ? Number(adminUserFilter) : undefined,
				});
			}
			return getUserLogs(params);
		},
	});

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
		<div className="p-4 space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-xl font-semibold">Log Management</h1>
					<p className="text-sm text-[var(--muted)]">
						Search structured service logs and error reports. Admins can switch to a global view to
						triage issues across users.
					</p>
				</div>
			</div>

			<div className="grid gap-6">
				<section className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4 space-y-4">
					<div className="flex items-center justify-between flex-wrap gap-2">
						<h2 className="text-lg font-semibold">Service Logs</h2>
						{isAdmin && (
							<div className="flex items-center gap-2 text-sm">
								<label className="flex items-center gap-2">
									<span>Scope</span>
									<select
										value={scope}
										onChange={(event) => setScope(event.target.value as 'self' | 'all')}
										className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
									>
										<option value="self">My Logs</option>
										<option value="all">All Users</option>
									</select>
								</label>
								{scope === 'all' && (
									<label className="flex items-center gap-2">
										<span>User ID</span>
										<input
											type="number"
											value={adminUserFilter}
											onChange={(event) => setAdminUserFilter(event.target.value)}
											className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1 w-28"
											placeholder="Any"
										/>
									</label>
								)}
							</div>
						)}
					</div>

					<div className="grid md:grid-cols-4 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span>Level</span>
							<select
								value={logFilters.level}
								onChange={(event) =>
									setLogFilters((prev) => ({ ...prev, level: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							>
								{LEVELS.map((level) => (
									<option key={level || 'any'} value={level}>
										{level || 'Any'}
									</option>
								))}
							</select>
						</label>
						<label className="flex flex-col gap-1">
							<span>Module</span>
							<input
								value={logFilters.module}
								onChange={(event) =>
									setLogFilters((prev) => ({ ...prev, module: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
								placeholder="scheduler"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span>Search</span>
							<input
								value={logFilters.search}
								onChange={(event) =>
									setLogFilters((prev) => ({ ...prev, search: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
								placeholder="keyword"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span>Limit</span>
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
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							/>
						</label>
					</div>

					<div className="grid md:grid-cols-2 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span>Start Date</span>
							<input
								type="date"
								value={logDates.start}
								onChange={(event) =>
									setLogDates((prev) => ({ ...prev, start: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span>End Date</span>
							<input
								type="date"
								value={logDates.end}
								onChange={(event) =>
									setLogDates((prev) => ({ ...prev, end: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							/>
						</label>
					</div>

					<LogTable logs={logsQuery.data ?? []} isLoading={logsQuery.isLoading} />
				</section>

				<section className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4 space-y-4">
					<div className="flex items-center justify-between flex-wrap gap-2">
						<h2 className="text-lg font-semibold">Error Logs</h2>
						<div className="text-xs text-[var(--muted)]">
							Click "Show Details" to inspect tracebacks and resolution notes.
						</div>
					</div>

					<div className="grid md:grid-cols-4 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span>Status</span>
							<select
								value={errorFilters.resolved}
								onChange={(event) =>
									setErrorFilters((prev) => ({ ...prev, resolved: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							>
								<option value="all">All</option>
								<option value="false">Unresolved</option>
								<option value="true">Resolved</option>
							</select>
						</label>
						<label className="flex flex-col gap-1">
							<span>Search</span>
							<input
								value={errorFilters.search}
								onChange={(event) =>
									setErrorFilters((prev) => ({ ...prev, search: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
								placeholder="message contains..."
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span>Limit</span>
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
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							/>
						</label>
					</div>

					<div className="grid md:grid-cols-2 gap-3 text-sm">
						<label className="flex flex-col gap-1">
							<span>Start Date</span>
							<input
								type="date"
								value={errorDates.start}
								onChange={(event) =>
									setErrorDates((prev) => ({ ...prev, start: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
							/>
						</label>
						<label className="flex flex-col gap-1">
							<span>End Date</span>
							<input
								type="date"
								value={errorDates.end}
								onChange={(event) =>
									setErrorDates((prev) => ({ ...prev, end: event.target.value }))
								}
								className="bg-[#0f172a] border border-[#1f2937] rounded px-2 py-1"
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
