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
	const { user } = useSessionStore();
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

	if (!user || user.role !== 'admin') {
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
				<div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
					<div className="flex items-center justify-between">
						<div className="text-yellow-400">
							⚠️ Schedule changes require unified service restart to take effect.
						</div>
						<button
							onClick={() => setShowRestartBanner(false)}
							className="text-yellow-400 hover:text-yellow-300"
						>
							×
						</button>
					</div>
				</div>
			)}

			{/* Schedules Table */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full">
						<thead className="bg-[#1e293b]">
							<tr>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
									Task
								</th>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
									Schedule Time
								</th>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
									Type
								</th>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
									Status
								</th>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
									Next Execution
								</th>
								<th className="px-4 py-3 text-left text-sm font-semibold text-[var(--text)]">
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
										<td className="px-4 py-3">
											<div className="text-sm font-medium text-[var(--text)]">
												{taskDisplayName}
											</div>
											{schedule.description && (
												<div className="text-xs text-[var(--muted)] mt-1">
													{schedule.description}
												</div>
											)}
										</td>
										<td className="px-4 py-3">
											{isEditing ? (
												<input
													type="time"
													value={editForm.schedule_time || ''}
													onChange={(e) =>
														setEditForm({ ...editForm, schedule_time: e.target.value })
													}
													className="px-2 py-1 bg-[#1e293b] border border-[#334155] rounded text-sm text-[var(--text)]"
												/>
											) : (
												<div className="text-sm text-[var(--text)]">
													{schedule.schedule_time}
												</div>
											)}
										</td>
										<td className="px-4 py-3">
											<div className="flex flex-col gap-1">
												{isEditing ? (
													<>
														<label className="flex items-center gap-2 text-sm text-[var(--text)]">
															<input
																type="checkbox"
																checked={editForm.is_hourly || false}
																onChange={(e) =>
																	setEditForm({ ...editForm, is_hourly: e.target.checked })
																}
																className="accent-blue-600"
															/>
															<span>Hourly</span>
														</label>
														<label className="flex items-center gap-2 text-sm text-[var(--text)]">
															<input
																type="checkbox"
																checked={editForm.is_continuous || false}
																onChange={(e) =>
																	setEditForm({
																		...editForm,
																		is_continuous: e.target.checked,
																	})
																}
																className="accent-blue-600"
															/>
															<span>Continuous</span>
														</label>
														{editForm.is_continuous && (
															<input
																type="time"
																value={editForm.end_time || ''}
																onChange={(e) =>
																	setEditForm({ ...editForm, end_time: e.target.value })
																}
																placeholder="End time"
																className="px-2 py-1 bg-[#1e293b] border border-[#334155] rounded text-sm text-[var(--text)] mt-1"
															/>
														)}
													</>
												) : (
													<div className="text-sm text-[var(--text)]">
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
															<span className="text-[var(--muted)]">One-time</span>
														)}
														{schedule.end_time && (
															<div className="text-xs text-[var(--muted)] mt-1">
																Ends: {schedule.end_time}
															</div>
														)}
													</div>
												)}
											</div>
										</td>
										<td className="px-4 py-3">
											{isEditing ? (
												<label className="flex items-center gap-2 text-sm text-[var(--text)]">
													<input
														type="checkbox"
														checked={editForm.enabled || false}
														onChange={(e) =>
															setEditForm({ ...editForm, enabled: e.target.checked })
														}
														className="accent-blue-600"
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
										<td className="px-4 py-3">
											{schedule.next_execution_at ? (
												<div className="text-sm text-[var(--text)]">
													{formatTimeAgo(
														Math.floor(
															(Date.now() - new Date(schedule.next_execution_at).getTime()) /
																1000
														)
													)}
												</div>
											) : (
												<span className="text-sm text-[var(--muted)]">N/A</span>
											)}
										</td>
										<td className="px-4 py-3">
											{isEditing ? (
												<div className="flex gap-2">
													<button
														onClick={() => handleSave(schedule.task_name)}
														disabled={updateMutation.isPending}
														className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm font-medium disabled:opacity-50"
													>
														{updateMutation.isPending ? 'Saving...' : 'Save'}
													</button>
													<button
														onClick={handleCancel}
														className="px-3 py-1 bg-gray-600 hover:bg-gray-700 text-white rounded text-sm font-medium"
													>
														Cancel
													</button>
												</div>
											) : (
												<div className="flex gap-2">
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
