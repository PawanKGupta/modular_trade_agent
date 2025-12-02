import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
	getNotificationPreferences,
	updateNotificationPreferences,
	type NotificationPreferences,
	type NotificationPreferencesUpdate,
} from '@/api/notification-preferences';

export function NotificationPreferencesPage() {
	const qc = useQueryClient();
	const [hasChanges, setHasChanges] = useState(false);
	const [localPrefs, setLocalPrefs] = useState<NotificationPreferences | null>(null);
	const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
	const [testingTelegram, setTestingTelegram] = useState(false);
	const [telegramTestResult, setTelegramTestResult] = useState<{ success: boolean; message: string } | null>(null);

	const { data: preferences, isLoading } = useQuery<NotificationPreferences>({
		queryKey: ['notificationPreferences'],
		queryFn: getNotificationPreferences,
	});

	const updateMutation = useMutation({
		mutationFn: updateNotificationPreferences,
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['notificationPreferences'] });
			setHasChanges(false);
			setSaveMessage({ type: 'success', text: 'Notification preferences saved successfully!' });
			setTimeout(() => setSaveMessage(null), 3000);
		},
		onError: (error: any) => {
			setSaveMessage({
				type: 'error',
				text: error?.response?.data?.detail || 'Failed to save notification preferences',
			});
			setTimeout(() => setSaveMessage(null), 5000);
		},
	});

	useEffect(() => {
		document.title = 'Notification Preferences';
	}, []);

	useEffect(() => {
		if (preferences) {
			setLocalPrefs(preferences);
		}
	}, [preferences]);

	const handleChange = (field: keyof NotificationPreferences, value: any) => {
		if (!localPrefs) return;
		setLocalPrefs({ ...localPrefs, [field]: value });
		setHasChanges(true);
		setSaveMessage(null);
	};

	const handleSave = () => {
		if (!localPrefs || !preferences) return;

		const updates: NotificationPreferencesUpdate = {};
		// Only include changed fields
		Object.keys(localPrefs).forEach((key) => {
			const typedKey = key as keyof NotificationPreferences;
			const localValue = localPrefs[typedKey];
			const prefValue = preferences[typedKey];
			if (localValue !== prefValue) {
				// Convert null to undefined for optional fields, keep other values as-is
				(updates as any)[typedKey] = localValue === null ? undefined : localValue;
			}
		});

		if (Object.keys(updates).length > 0) {
			updateMutation.mutate(updates);
		}
	};

	const handleEnableAll = (category: 'order' | 'system' | 'retry' | 'service') => {
		if (!localPrefs) return;
		const updates: Partial<NotificationPreferences> = {};

		if (category === 'order') {
			updates.notify_order_placed = true;
			updates.notify_order_rejected = true;
			updates.notify_order_executed = true;
			updates.notify_order_cancelled = true;
			updates.notify_order_modified = true;
			updates.notify_partial_fill = true;
		} else if (category === 'system') {
			updates.notify_system_errors = true;
			updates.notify_system_warnings = true;
			updates.notify_system_info = true;
		} else if (category === 'retry') {
			updates.notify_retry_queue_added = true;
			updates.notify_retry_queue_updated = true;
			updates.notify_retry_queue_removed = true;
			updates.notify_retry_queue_retried = true;
		} else if (category === 'service') {
			updates.notify_service_started = true;
			updates.notify_service_stopped = true;
			updates.notify_service_execution_completed = true;
		}

		setLocalPrefs({ ...localPrefs, ...updates });
		setHasChanges(true);
	};

	const handleDisableAll = (category: 'order' | 'system' | 'retry' | 'service') => {
		if (!localPrefs) return;
		const updates: Partial<NotificationPreferences> = {};

		if (category === 'order') {
			updates.notify_order_placed = false;
			updates.notify_order_rejected = false;
			updates.notify_order_executed = false;
			updates.notify_order_cancelled = false;
			updates.notify_order_modified = false;
			updates.notify_partial_fill = false;
		} else if (category === 'system') {
			updates.notify_system_errors = false;
			updates.notify_system_warnings = false;
			updates.notify_system_info = false;
		} else if (category === 'retry') {
			updates.notify_retry_queue_added = false;
			updates.notify_retry_queue_updated = false;
			updates.notify_retry_queue_removed = false;
			updates.notify_retry_queue_retried = false;
		} else if (category === 'service') {
			updates.notify_service_started = false;
			updates.notify_service_stopped = false;
			updates.notify_service_execution_completed = false;
		}

		setLocalPrefs({ ...localPrefs, ...updates });
		setHasChanges(true);
	};

	const handleTestTelegram = async () => {
		if (!localPrefs?.telegram_bot_token || !localPrefs?.telegram_chat_id) return;

		setTestingTelegram(true);
		setTelegramTestResult(null);

		try {
			const response = await fetch(
				`/api/v1/user/notification-preferences/telegram/test?bot_token=${encodeURIComponent(localPrefs.telegram_bot_token)}&chat_id=${encodeURIComponent(localPrefs.telegram_chat_id)}`,
				{
					method: 'POST',
					headers: {
						'Authorization': `Bearer ${localStorage.getItem('ta_access_token')}`,
					},
				}
			);

			const data = await response.json();
			setTelegramTestResult(data);
		} catch (error) {
			setTelegramTestResult({
				success: false,
				message: 'Failed to test connection. Please try again.',
			});
		} finally {
			setTestingTelegram(false);
		}
	};

	if (isLoading || !localPrefs) {
		return <div className="p-4">Loading notification preferences...</div>;
	}

	return (
		<div className="p-4 space-y-6 max-w-4xl">
			<div className="flex items-center justify-between">
				<h1 className="text-xl font-semibold">Notification Preferences</h1>
				<div className="flex items-center gap-3">
					{hasChanges && (
						<span className="text-sm text-yellow-400">Unsaved changes</span>
					)}
					<button
						onClick={handleSave}
						disabled={updateMutation.isPending || !hasChanges}
						className="px-4 py-2 rounded bg-[var(--accent)] text-black disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--accent-hover)]"
					>
						{updateMutation.isPending ? 'Saving...' : 'Save Preferences'}
					</button>
				</div>
			</div>

			{saveMessage && (
				<div
					className={`p-3 rounded ${
						saveMessage.type === 'success'
							? 'bg-green-900/50 text-green-400 border border-green-700'
							: 'bg-red-900/50 text-red-400 border border-red-700'
					}`}
				>
					{saveMessage.text}
				</div>
			)}

			{/* Notification Channels */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<h2 className="text-lg font-semibold">Notification Channels</h2>
				<p className="text-sm text-[var(--muted)]">
					Choose how you want to receive notifications
				</p>

				<div className="space-y-3">
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.in_app_enabled}
							onChange={(e) => handleChange('in_app_enabled', e.target.checked)}
							className="w-4 h-4"
						/>
						<div>
							<span className="font-medium">In-App Notifications</span>
							<p className="text-xs text-[var(--muted)]">
								Show notifications in the web interface
							</p>
						</div>
					</label>

					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.telegram_enabled}
							onChange={(e) => handleChange('telegram_enabled', e.target.checked)}
							className="w-4 h-4"
						/>
						<div className="flex-1">
							<span className="font-medium">Telegram</span>
							<p className="text-xs text-[var(--muted)]">
								Receive notifications via Telegram bot
							</p>
							{localPrefs.telegram_enabled && (
								<div className="mt-2 space-y-2">
									<input
										type="text"
										value={localPrefs.telegram_bot_token || ''}
										onChange={(e) => handleChange('telegram_bot_token', e.target.value || null)}
										placeholder="Telegram Bot Token (e.g., 123456:ABC-DEF)"
										className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
									/>
									<input
										type="text"
										value={localPrefs.telegram_chat_id || ''}
										onChange={(e) => handleChange('telegram_chat_id', e.target.value || null)}
										placeholder="Telegram Chat ID (e.g., 123456789)"
										className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
									/>
									<button
										onClick={handleTestTelegram}
										disabled={!localPrefs.telegram_bot_token || !localPrefs.telegram_chat_id || testingTelegram}
										className="w-full px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
									>
										{testingTelegram ? 'Testing...' : 'Test Connection'}
									</button>
									{telegramTestResult && (
										<div className={`text-xs p-2 rounded ${telegramTestResult.success ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
											{telegramTestResult.message}
										</div>
									)}
								</div>
							)}
						</div>
					</label>

					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.email_enabled}
							onChange={(e) => handleChange('email_enabled', e.target.checked)}
							className="w-4 h-4"
						/>
						<div className="flex-1">
							<span className="font-medium">Email</span>
							<p className="text-xs text-[var(--muted)]">
								Receive notifications via email
							</p>
							{localPrefs.email_enabled && (
								<input
									type="email"
									value={localPrefs.email_address || ''}
									onChange={(e) => handleChange('email_address', e.target.value || null)}
									placeholder="Email address"
									className="mt-2 w-full p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
								/>
							)}
						</div>
					</label>
				</div>
			</section>

			{/* Order Events */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-lg font-semibold">Order Events</h2>
						<p className="text-sm text-[var(--muted)]">
							Control which order-related events trigger notifications
						</p>
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => handleEnableAll('order')}
							className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
						>
							Enable All
						</button>
						<button
							type="button"
							onClick={() => handleDisableAll('order')}
							className="text-xs px-2 py-1 rounded bg-gray-600 hover:bg-gray-700 text-white"
						>
							Disable All
						</button>
					</div>
				</div>

				<div className="space-y-2">
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_order_placed}
							onChange={(e) => handleChange('notify_order_placed', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Placed</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_order_executed}
							onChange={(e) => handleChange('notify_order_executed', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Executed</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_order_rejected}
							onChange={(e) => handleChange('notify_order_rejected', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Rejected</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_order_cancelled}
							onChange={(e) => handleChange('notify_order_cancelled', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Cancelled</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_order_modified}
							onChange={(e) => handleChange('notify_order_modified', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Modified (Manual)</span>
						<span className="text-xs text-[var(--muted)]">(Opt-in)</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_partial_fill}
							onChange={(e) => handleChange('notify_partial_fill', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Partial Fill</span>
					</label>
				</div>
			</section>

			{/* Retry Queue Events */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-lg font-semibold">Retry Queue Events</h2>
						<p className="text-sm text-[var(--muted)]">
							Control notifications for retry queue operations
						</p>
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => handleEnableAll('retry')}
							className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
						>
							Enable All
						</button>
						<button
							type="button"
							onClick={() => handleDisableAll('retry')}
							className="text-xs px-2 py-1 rounded bg-gray-600 hover:bg-gray-700 text-white"
						>
							Disable All
						</button>
					</div>
				</div>

				<div className="space-y-2">
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_retry_queue_added}
							onChange={(e) => handleChange('notify_retry_queue_added', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Added to Retry Queue</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_retry_queue_updated}
							onChange={(e) => handleChange('notify_retry_queue_updated', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Retry Queue Updated</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_retry_queue_removed}
							onChange={(e) => handleChange('notify_retry_queue_removed', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Removed from Retry Queue</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_retry_queue_retried}
							onChange={(e) => handleChange('notify_retry_queue_retried', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Order Retried Successfully</span>
					</label>
				</div>
			</section>

			{/* System Events */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-lg font-semibold">System Events</h2>
						<p className="text-sm text-[var(--muted)]">
							Control notifications for system-level events
						</p>
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => handleEnableAll('system')}
							className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
						>
							Enable All
						</button>
						<button
							type="button"
							onClick={() => handleDisableAll('system')}
							className="text-xs px-2 py-1 rounded bg-gray-600 hover:bg-gray-700 text-white"
						>
							Disable All
						</button>
					</div>
				</div>

				<div className="space-y-2">
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_system_errors}
							onChange={(e) => handleChange('notify_system_errors', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>System Errors</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_system_warnings}
							onChange={(e) => handleChange('notify_system_warnings', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>System Warnings</span>
						<span className="text-xs text-[var(--muted)]">(Opt-in)</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_system_info}
							onChange={(e) => handleChange('notify_system_info', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>System Info</span>
						<span className="text-xs text-[var(--muted)]">(Opt-in)</span>
					</label>
				</div>
			</section>

			{/* Service Events */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-lg font-semibold">Service Events</h2>
						<p className="text-sm text-[var(--muted)]">
							Control notifications for service lifecycle events
						</p>
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => handleEnableAll('service')}
							className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
						>
							Enable All
						</button>
						<button
							type="button"
							onClick={() => handleDisableAll('service')}
							className="text-xs px-2 py-1 rounded bg-gray-600 hover:bg-gray-700 text-white"
						>
							Disable All
						</button>
					</div>
				</div>

				<div className="space-y-2">
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_service_started}
							onChange={(e) => handleChange('notify_service_started', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Service Started</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_service_stopped}
							onChange={(e) => handleChange('notify_service_stopped', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Service Stopped</span>
					</label>
					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.notify_service_execution_completed}
							onChange={(e) => handleChange('notify_service_execution_completed', e.target.checked)}
							className="w-4 h-4"
						/>
						<span>Service Execution Completed</span>
					</label>
				</div>
			</section>

			{/* Quiet Hours */}
			<section className="space-y-4 p-4 border border-[#1e293b] rounded">
				<h2 className="text-lg font-semibold">Quiet Hours</h2>
				<p className="text-sm text-[var(--muted)]">
					Set a time range when notifications will be suppressed (e.g., 22:00 - 08:00 for
					nighttime)
				</p>

				<div className="flex items-center gap-4">
					<div className="flex-1">
						<label className="block text-sm mb-1">Start Time</label>
						<input
							type="time"
							value={localPrefs.quiet_hours_start?.substring(0, 5) || ''}
							onChange={(e) =>
								handleChange('quiet_hours_start', e.target.value ? `${e.target.value}:00` : null)
							}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
					</div>
					<div className="flex-1">
						<label className="block text-sm mb-1">End Time</label>
						<input
							type="time"
							value={localPrefs.quiet_hours_end?.substring(0, 5) || ''}
							onChange={(e) =>
								handleChange('quiet_hours_end', e.target.value ? `${e.target.value}:00` : null)
							}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
					</div>
					<div className="flex items-end">
						<button
							type="button"
							onClick={() => {
								handleChange('quiet_hours_start', null);
								handleChange('quiet_hours_end', null);
							}}
							className="px-3 py-2 rounded bg-gray-600 hover:bg-gray-700 text-white text-sm"
						>
							Clear
						</button>
					</div>
				</div>
				{localPrefs.quiet_hours_start && localPrefs.quiet_hours_end && (
					<p className="text-xs text-[var(--muted)]">
						Notifications will be suppressed between {localPrefs.quiet_hours_start.substring(0, 5)} and{' '}
						{localPrefs.quiet_hours_end.substring(0, 5)}
					</p>
				)}
			</section>
		</div>
	);
}
