import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	listServiceSchedules,
	updateServiceSchedule,
	enableServiceSchedule,
	disableServiceSchedule,
	type ServiceSchedule,
} from '@/api/admin';
import { formatTimeAgo } from '@/utils/time';
import { useSessionStore } from '@/state/sessionStore';

export function ServiceSchedulePage() {
	const qc = useQueryClient();
	const { user, isAdmin } = useSessionStore();
	const [editingSchedule, setEditingSchedule] = useState<string | null>(null);
	const [editForm, setEditForm] = useState<Partial<ServiceSchedule>>({});
	const [showRestartBanner, setShowRestartBanner] = useState(false);

	const { data: schedules, isLoading } = useQuery({
		queryKey: ['serviceSchedules'],
		queryFn: listServiceSchedules,
		refetchInterval: 30000, // Refresh every 30 seconds
	});

	const updateMutation = useMutation({
		mutationFn: ({ taskName, payload }: { taskName: string; payload: any }) =>
			updateServiceSchedule(taskName, payload),
		onSuccess: (response) => {
			if (response.requires_restart) {
				setShowRestartBanner(true);
			}
			qc.invalidateQueries({ queryKey: ['serviceSchedules'] });
			setEditingSchedule(null);
		},
	});

	const enableMutation = useMutation({
		mutationFn: (taskName: string) => enableServiceSchedule(taskName),
		onSuccess: (response) => {
			if (response.requires_restart) {
				setShowRestartBanner(true);
			}
			qc.invalidateQueries({ queryKey: ['serviceSchedules'] });
		},
	});

	const disableMutation = useMutation({
		mutationFn: (taskName: string) => disableServiceSchedule(taskName),
		onSuccess: (response) => {
			if (response.requires_restart) {
				setShowRestartBanner(true);
			}
			qc.invalidateQueries({ queryKey: ['serviceSchedules'] });
		},
	});

	const handleEdit = (schedule: ServiceSchedule) => {
		setEditingSchedule(schedule.task_name);
		setEditForm({
			schedule_time: schedule.schedule_time,
			enabled: schedule.enabled,
			is_hourly: schedule.is_hourly,
			is_continuous: schedule.is_continuous,
			end_time: schedule.end_time,
			schedule_type: schedule.schedule_type,
			description: schedule.description,
		});
	};

	const handleSave = (taskName: string) => {
		updateMutation.mutate({
			taskName,
			payload: {
				schedule_time: editForm.schedule_time,
				enabled: editForm.enabled,
				is_hourly: editForm.is_hourly,
				is_continuous: editForm.is_continuous,
				end_time: editForm.end_time || null,
				schedule_type: editForm.schedule_type || 'daily',
				description: editForm.description || null,
			},
		});
	};

	const handleCancel = () => {
		setEditingSchedule(null);
		setEditForm({});
	};

	const handleToggleEnabled = (schedule: ServiceSchedule) => {
		if (schedule.enabled) {
			disableMutation.mutate(schedule.task_name);
		} else {
			enableMutation.mutate(schedule.task_name);
		}
	};

	const TASK_DISPLAY_NAMES: Record<string, string> = {
		premarket_retry: 'Pre-market Retry',
		sell_monitor: 'Sell Monitor',
		position_monitor: 'Position Monitor',
		analysis: 'Analysis',
		buy_orders: 'Buy Orders',
		eod_cleanup: 'End-of-Day Cleanup',
	};

	if (!user || !isAdmin) {
		return (
			<div className="p-4">
				<div className="text-red-400">Access denied. Admin privileges required.</div>
			</div>
		);
	}

	if (isLoading) {
		return <div className="p-4 text-[var(--text)]">Loading schedules...</div>;
	}

	return (
		<div className="p-4 space-y-6">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold text-[var(--text)]">Service Schedules</h1>
			</div>


			{/* Restart Banner */}
			{showRestartBanner && (
				<div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 sm:p-4">
					<div className="flex items-start sm:items-center justify-between gap-2">
						<div className="text-xs sm:text-sm text-yellow-400">
							[WARN]? Schedule changes require unified service restart to take effect.
						</div>
						<button
							onClick={() => setShowRestartBanner(false)}
							className="text-yellow-400 hover:text-yellow-300 min-h-[32px] sm:min-h-0 px-2"
						>
							x
						</button>
					</div>
				</div>
			)}

			{/* Schedules Table */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
				<div className="overflow-x-auto -mx-2 sm:mx-0">
					<table className="w-full text-xs sm:text-sm">
						<thead className="bg-[#1e293b]">
							<tr>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap">
									Task
								</th>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap hidden sm:table-cell">
									Schedule Time
								</th>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap hidden md:table-cell">
									Type
								</th>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap">
									Status
								</th>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap hidden lg:table-cell">
									Next Execution
								</th>
								<th className="px-2 sm:px-4 py-2 sm:py-3 text-left font-semibold text-[var(--text)] whitespace-nowrap">
									Actions
								</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-[#1e293b]">
							{schedules?.schedules.map((schedule) => {
								const isEditing = editingSchedule === schedule.task_name;
								const taskDisplayName =
									TASK_DISPLAY_NAMES[schedule.task_name] || schedule.task_name;

								return (
									<tr key={schedule.id} className="hover:bg-[#1e293b]/50">
										<td className="px-2 sm:px-4 py-2 sm:py-3">
											<div className="text-xs sm:text-sm font-medium text-[var(--text)]">
												{taskDisplayName}
											</div>
											{schedule.description && (
												<div className="text-xs text-[var(--muted)] mt-1">
													{schedule.description}
												</div>
											)}
										</td>
										<td className="px-2 sm:px-4 py-2 sm:py-3 hidden sm:table-cell">
											{isEditing ? (
												<input
													type="time"
													value={editForm.schedule_time || ''}
													onChange={(e) =>
														setEditForm({ ...editForm, schedule_time: e.target.value })
													}
													className="px-2 py-2 sm:py-1 bg-[#1e293b] border border-[#334155] rounded text-xs sm:text-sm text-[var(--text)] min-h-[44px] sm:min-h-0"
												/>
											) : (
												<div className="text-xs sm:text-sm text-[var(--text)]">
													{schedule.schedule_time}
												</div>
											)}
										</td>
										<td className="px-2 sm:px-4 py-2 sm:py-3 hidden md:table-cell">
											<div className="flex flex-col gap-2">
												{isEditing ? (
													<>
														<label className="flex items-center gap-2 text-sm text-[var(--text)]">
															<span className="w-24">Schedule:</span>
															<select
																value={editForm.schedule_type || 'daily'}
																onChange={(e) => {
																	const newScheduleType = e.target.value as 'daily' | 'once';
																	// If changing to "once", set execution to "one-time" and clear hourly/continuous
																	if (newScheduleType === 'once') {
																		setEditForm({
																			...editForm,
																			schedule_type: newScheduleType,
																			is_hourly: false,
																			is_continuous: false,
																			end_time: null,
																		});
																	} else {
																		setEditForm({
																			...editForm,
																			schedule_type: newScheduleType,
																		});
																	}
																}}
																className="px-2 py-1 bg-[#1e293b] border border-[#334155] rounded text-sm text-[var(--text)]"
															>
																<option value="daily">Daily</option>
																<option value="once">Once</option>
															</select>
														</label>
														<label className="flex items-center gap-2 text-sm text-[var(--text)]">
															<span className="w-24">Execution:</span>
															<select
																value={
																	editForm.is_hourly
																		? 'hourly'
																		: editForm.is_continuous
																			? 'continuous'
																			: 'one-time'
																}
																onChange={(e) => {
																	const value = e.target.value;
																	setEditForm({
																		...editForm,
																		is_hourly: value === 'hourly',
																		is_continuous: value === 'continuous',
																		end_time: value === 'continuous' ? editForm.end_time : null,
																	});
																}}
																disabled={editForm.schedule_type === 'once'}
																className="px-2 py-1 bg-[#1e293b] border border-[#334155] rounded text-sm text-[var(--text)] disabled:opacity-50 disabled:cursor-not-allowed"
															>
																<option value="one-time">One-time</option>
																<option value="hourly">Hourly</option>
																<option value="continuous">Continuous</option>
															</select>
															{editForm.schedule_type === 'once' && (
																<span className="text-xs text-[var(--muted)] ml-1">
																	(locked to one-time)
																</span>
															)}
														</label>
														{editForm.is_continuous && (
															<label className="flex items-center gap-2 text-sm text-[var(--text)]">
																<span className="w-24">End Time:</span>
																<input
																	type="time"
																	value={editForm.end_time || ''}
																	onChange={(e) =>
																		setEditForm({ ...editForm, end_time: e.target.value })
																	}
																	placeholder="End time"
																	className="px-2 py-1 bg-[#1e293b] border border-[#334155] rounded text-sm text-[var(--text)]"
																/>
															</label>
														)}
													</>
												) : (
													<div className="text-sm text-[var(--text)]">
														<div className="mb-1">
															<span className={`px-2 py-0.5 rounded text-xs ${
																schedule.schedule_type === 'daily'
																	? 'bg-green-500/20 text-green-400'
																	: 'bg-orange-500/20 text-orange-400'
															}`}>
																{schedule.schedule_type === 'daily' ? 'Daily' : 'Once'}
															</span>
														</div>
														<div className="mt-1">
															{schedule.is_hourly && (
																<span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs mr-1">
																	Hourly
																</span>
															)}
															{schedule.is_continuous && (
																<span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs mr-1">
																	Continuous
																</span>
															)}
															{!schedule.is_hourly && !schedule.is_continuous && (
																<span className="px-2 py-0.5 bg-gray-500/20 text-gray-400 rounded text-xs">
																	One-time
																</span>
															)}
														</div>
														{schedule.end_time && (
															<div className="text-xs text-[var(--muted)] mt-1">
																Ends: {schedule.end_time}
															</div>
														)}
													</div>
												)}
											</div>
										</td>
										<td className="px-2 sm:px-4 py-2 sm:py-3">
											{isEditing ? (
												<label className="flex items-center gap-2 text-xs sm:text-sm text-[var(--text)] min-h-[44px] sm:min-h-0">
													<input
														type="checkbox"
														checked={editForm.enabled || false}
														onChange={(e) =>
															setEditForm({ ...editForm, enabled: e.target.checked })
														}
														className="accent-blue-600 w-4 h-4"
													/>
													<span>Enabled</span>
												</label>
											) : (
												<div
													className={`px-2 py-1 rounded text-xs font-medium inline-block ${
														schedule.enabled
															? 'bg-green-500/20 text-green-400'
															: 'bg-gray-500/20 text-gray-400'
													}`}
												>
													{schedule.enabled ? 'Enabled' : 'Disabled'}
												</div>
											)}
										</td>
										<td className="px-2 sm:px-4 py-2 sm:py-3 hidden lg:table-cell">
											{schedule.next_execution_at ? (
												<div className="text-xs sm:text-sm text-[var(--text)]">
													{formatTimeAgo(
														Math.floor(
															(Date.now() - new Date(schedule.next_execution_at).getTime()) /
																1000
														)
													)}
												</div>
											) : (
												<span className="text-xs sm:text-sm text-[var(--muted)]">N/A</span>
											)}
										</td>
										<td className="px-2 sm:px-4 py-2 sm:py-3">
											{isEditing ? (
												<div className="flex flex-col sm:flex-row gap-2">
													<button
														onClick={() => handleSave(schedule.task_name)}
														disabled={updateMutation.isPending}
														className="px-3 py-2 sm:py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs sm:text-sm font-medium disabled:opacity-50 min-h-[36px] sm:min-h-0"
													>
														{updateMutation.isPending ? 'Saving...' : 'Save'}
													</button>
													<button
														onClick={handleCancel}
														className="px-3 py-2 sm:py-1 bg-gray-600 hover:bg-gray-700 text-white rounded text-xs sm:text-sm font-medium min-h-[36px] sm:min-h-0"
													>
														Cancel
													</button>
												</div>
											) : (
												<div className="flex flex-col sm:flex-row gap-2">
													<button
														onClick={() => handleEdit(schedule)}
														className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium"
													>
														Edit
													</button>
													<button
														onClick={() => handleToggleEnabled(schedule)}
														disabled={
															enableMutation.isPending || disableMutation.isPending
														}
														className={`px-3 py-1 rounded text-sm font-medium disabled:opacity-50 ${
															schedule.enabled
																? 'bg-yellow-600 hover:bg-yellow-700 text-white'
																: 'bg-green-600 hover:bg-green-700 text-white'
														}`}
													>
														{enableMutation.isPending || disableMutation.isPending
															? '...'
															: schedule.enabled
																? 'Disable'
																: 'Enable'}
													</button>
												</div>
											)}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	);
}
