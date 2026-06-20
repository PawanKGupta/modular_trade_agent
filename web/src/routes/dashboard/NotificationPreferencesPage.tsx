import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import {
	getNotificationPreferences,
	updateNotificationPreferences,
	type NotificationPreferences,
	type NotificationPreferencesUpdate,
} from '@/api/notification-preferences';

// ── Accordion card (mirrors SettingsPage > SectionCard) ───────────────────────

type SectionCardProps = {
	id: string;
	icon: string;
	title: string;
	badge?: ReactNode;
	isOpen: boolean;
	onToggle: () => void;
	children: ReactNode;
};

function SectionCard({ id, icon, title, badge, isOpen, onToggle, children }: SectionCardProps) {
	return (
		<div className="rounded-lg border border-[#1e293b] bg-[#0c1521] overflow-hidden transition-shadow hover:shadow-[0_0_0_1px_#334155]">
			<button
				type="button"
				id={`${id}-header`}
				aria-expanded={isOpen}
				aria-controls={`${id}-body`}
				onClick={onToggle}
				className="w-full flex items-center justify-between px-4 py-3.5 text-left gap-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
			>
				<div className="flex items-center gap-3 min-w-0">
					<span className="text-base shrink-0">{icon}</span>
					<span className="font-medium text-sm sm:text-base truncate">{title}</span>
					{badge}
				</div>
				<svg
					className={`w-4 h-4 shrink-0 text-[var(--muted)] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
					viewBox="0 0 20 20"
					fill="currentColor"
					aria-hidden="true"
				>
					<path
						fillRule="evenodd"
						d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
						clipRule="evenodd"
					/>
				</svg>
			</button>
			<div
				id={`${id}-body`}
				role="region"
				aria-labelledby={`${id}-header`}
				className={`transition-all duration-200 ease-in-out ${isOpen ? 'max-h-[9999px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden pointer-events-none'}`}
			>
				<div className="px-4 pb-5 pt-1 border-t border-[#1e293b] space-y-4">{children}</div>
			</div>
		</div>
	);
}

// ── Enable / Disable All row ───────────────────────────────────────────────────

function BulkActions({ onEnable, onDisable }: { onEnable: () => void; onDisable: () => void }) {
	return (
		<div className="flex gap-2 pt-1">
			<button
				type="button"
				onClick={onEnable}
				className="text-xs px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
			>
				Enable All
			</button>
			<button
				type="button"
				onClick={onDisable}
				className="text-xs px-2 py-1 rounded bg-gray-600 hover:bg-gray-700 text-white"
			>
				Disable All
			</button>
		</div>
	);
}

// ── Main page ─────────────────────────────────────────────────────────────────

type SectionKey = 'channels' | 'orders' | 'retry' | 'system' | 'service' | 'billing' | 'quiet';

export function NotificationPreferencesPage() {
	const qc = useQueryClient();
	const [hasChanges, setHasChanges] = useState(false);
	const [localPrefs, setLocalPrefs] = useState<NotificationPreferences | null>(null);
	const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
	const [testingTelegram, setTestingTelegram] = useState(false);
	const [telegramTestResult, setTelegramTestResult] = useState<{ success: boolean; message: string } | null>(null);
	const [openSection, setOpenSection] = useState<SectionKey | ''>('');

	const toggle = useCallback(
		(key: SectionKey) => setOpenSection((prev) => (prev === key ? '' : key)),
		[],
	);

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
		onError: (error: unknown) => {
			const errorDetail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setSaveMessage({
				type: 'error',
				text: errorDetail || 'Failed to save notification preferences',
			});
			setTimeout(() => setSaveMessage(null), 5000);
		},
	});

	useEffect(() => {
		document.title = 'Notification Preferences';
	}, []);

	useEffect(() => {
		if (preferences) setLocalPrefs(preferences);
	}, [preferences]);

	const handleChange = (field: keyof NotificationPreferences, value: unknown) => {
		if (!localPrefs) return;
		setLocalPrefs({ ...localPrefs, [field]: value });
		setHasChanges(true);
		setSaveMessage(null);
	};

	const handleSave = () => {
		if (!localPrefs || !preferences) return;
		const updates: NotificationPreferencesUpdate = {};
		Object.keys(localPrefs).forEach((key) => {
			const typedKey = key as keyof NotificationPreferences;
			const localValue = localPrefs[typedKey];
			const prefValue = preferences[typedKey];
			if (localValue !== prefValue) {
				(updates as Record<string, unknown>)[typedKey] = localValue === null ? undefined : localValue;
			}
		});
		if (Object.keys(updates).length > 0) updateMutation.mutate(updates);
	};

	const handleEnableAll = (category: 'order' | 'system' | 'retry' | 'service' | 'billing') => {
		if (!localPrefs) return;
		const updates: Partial<NotificationPreferences> = {};
		if (category === 'order') {
			updates.notify_order_placed = true;
			updates.notify_order_rejected = true;
			updates.notify_order_executed = true;
			updates.notify_order_cancelled = true;
			updates.notify_order_modified = true;
			updates.notify_partial_fill = true;
			updates.notify_balance_shortfall = true;
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
		} else if (category === 'billing') {
			updates.notify_payment_failed = true;
		}
		setLocalPrefs({ ...localPrefs, ...updates });
		setHasChanges(true);
	};

	const handleDisableAll = (category: 'order' | 'system' | 'retry' | 'service' | 'billing') => {
		if (!localPrefs) return;
		const updates: Partial<NotificationPreferences> = {};
		if (category === 'order') {
			updates.notify_order_placed = false;
			updates.notify_order_rejected = false;
			updates.notify_order_executed = false;
			updates.notify_order_cancelled = false;
			updates.notify_order_modified = false;
			updates.notify_partial_fill = false;
			updates.notify_balance_shortfall = false;
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
		} else if (category === 'billing') {
			updates.notify_payment_failed = false;
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
					headers: { Authorization: `Bearer ${localStorage.getItem('ta_access_token')}` },
				},
			);
			const data = await response.json();
			setTelegramTestResult(data);
		} catch {
			setTelegramTestResult({ success: false, message: 'Failed to test connection. Please try again.' });
		} finally {
			setTestingTelegram(false);
		}
	};

	if (isLoading || !localPrefs) {
		return <div className="p-2 sm:p-4 text-xs sm:text-sm">Loading notification preferences...</div>;
	}

	const inputCls =
		'w-full px-3 py-2.5 sm:py-2 rounded bg-[#070e17] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0 focus:outline-none focus:border-[var(--accent)] transition-colors';

	return (
		<div className="p-2 sm:p-4 max-w-xl">
			<h1 className="text-lg sm:text-xl font-semibold mb-1">Notification Preferences</h1>
			<p className="text-xs sm:text-sm text-[var(--muted)] mb-5">
				Choose which events notify you and how.
			</p>

			{saveMessage && (
				<div
					className={`mb-4 p-2 sm:p-3 rounded text-xs sm:text-sm ${
						saveMessage.type === 'success'
							? 'bg-green-900/50 text-green-400 border border-green-700'
							: 'bg-red-900/50 text-red-400 border border-red-700'
					}`}
				>
					{saveMessage.text}
				</div>
			)}

			<div className="space-y-3">
				{/* ── Channels ─────────────────────────────────────────────── */}
				<SectionCard
					id="np-channels"
					icon="📡"
					title="Notification Channels"
					isOpen={openSection === 'channels'}
					onToggle={() => toggle('channels')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Choose how you want to receive notifications.
					</p>

					<label className="flex items-center gap-3">
						<input
							type="checkbox"
							checked={localPrefs.in_app_enabled}
							onChange={(e) => handleChange('in_app_enabled', e.target.checked)}
							className="w-4 h-4"
						/>
						<div>
							<span className="font-medium text-sm">In-App Notifications</span>
							<p className="text-xs text-[var(--muted)]">Show notifications in the web interface</p>
						</div>
					</label>

					<label className="flex items-start gap-3">
						<input
							type="checkbox"
							checked={localPrefs.telegram_enabled}
							onChange={(e) => handleChange('telegram_enabled', e.target.checked)}
							className="w-4 h-4 mt-0.5"
						/>
						<div className="flex-1">
							<span className="font-medium text-sm">Telegram</span>
							<p className="text-xs text-[var(--muted)]">Receive notifications via Telegram bot</p>
							{localPrefs.telegram_enabled && (
								<div className="mt-2 space-y-2">
									<input
										type="text"
										value={localPrefs.telegram_bot_token || ''}
										onChange={(e) => handleChange('telegram_bot_token', e.target.value || null)}
										placeholder="Telegram Bot Token (e.g., 123456:ABC-DEF)"
										className={inputCls}
									/>
									<input
										type="text"
										value={localPrefs.telegram_chat_id || ''}
										onChange={(e) => handleChange('telegram_chat_id', e.target.value || null)}
										placeholder="Telegram Chat ID (e.g., 123456789)"
										className={inputCls}
									/>
									<button
										onClick={handleTestTelegram}
										disabled={
											!localPrefs.telegram_bot_token ||
											!localPrefs.telegram_chat_id ||
											testingTelegram
										}
										className="w-full px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed min-h-[40px]"
									>
										{testingTelegram ? 'Testing…' : 'Test Connection'}
									</button>
									{telegramTestResult && (
										<div
											className={`text-xs p-2 rounded ${telegramTestResult.success ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}
										>
											{telegramTestResult.message}
										</div>
									)}
								</div>
							)}
						</div>
					</label>

					<label className="flex items-start gap-3">
						<input
							type="checkbox"
							checked={localPrefs.email_enabled}
							onChange={(e) => handleChange('email_enabled', e.target.checked)}
							className="w-4 h-4 mt-0.5"
						/>
						<div className="flex-1">
							<span className="font-medium text-sm">Email</span>
							<p className="text-xs text-[var(--muted)]">Receive notifications via email</p>
							{localPrefs.email_enabled && (
								<input
									type="email"
									value={localPrefs.email_address || ''}
									onChange={(e) => handleChange('email_address', e.target.value || null)}
									placeholder="Email address"
									className={`mt-2 ${inputCls}`}
								/>
							)}
						</div>
					</label>
				</SectionCard>

				{/* ── Order Events ─────────────────────────────────────────── */}
				<SectionCard
					id="np-orders"
					icon="📦"
					title="Order Events"
					isOpen={openSection === 'orders'}
					onToggle={() => toggle('orders')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Control which order-related events trigger notifications.
					</p>
					<BulkActions
						onEnable={() => handleEnableAll('order')}
						onDisable={() => handleDisableAll('order')}
					/>
					<div className="space-y-2">
						{[
							{ field: 'notify_order_placed', label: 'Order Placed' },
							{ field: 'notify_order_executed', label: 'Order Executed' },
							{ field: 'notify_order_rejected', label: 'Order Rejected' },
							{ field: 'notify_order_cancelled', label: 'Order Cancelled' },
							{ field: 'notify_partial_fill', label: 'Partial Fill' },
						].map(({ field, label }) => (
							<label key={field} className="flex items-center gap-3">
								<input
									type="checkbox"
									checked={localPrefs[field as keyof NotificationPreferences] as boolean}
									onChange={(e) => handleChange(field as keyof NotificationPreferences, e.target.checked)}
									className="w-4 h-4"
								/>
								<span className="text-sm">{label}</span>
							</label>
						))}
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_order_modified}
								onChange={(e) => handleChange('notify_order_modified', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">
								Order Modified{' '}
								<span className="text-xs text-[var(--muted)]">(incl. 9:05 pre-market)</span>
							</span>
						</label>
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_balance_shortfall}
								onChange={(e) => handleChange('notify_balance_shortfall', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">
								Balance Shortfall{' '}
								<span className="text-xs text-[var(--muted)]">(evening preview and morning buy)</span>
							</span>
						</label>
					</div>
				</SectionCard>

				{/* ── Retry Queue ──────────────────────────────────────────── */}
				<SectionCard
					id="np-retry"
					icon="🔄"
					title="Retry Queue Events"
					isOpen={openSection === 'retry'}
					onToggle={() => toggle('retry')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Control notifications for retry queue operations.
					</p>
					<BulkActions
						onEnable={() => handleEnableAll('retry')}
						onDisable={() => handleDisableAll('retry')}
					/>
					<div className="space-y-2">
						{[
							{ field: 'notify_retry_queue_added', label: 'Order Added to Retry Queue' },
							{ field: 'notify_retry_queue_updated', label: 'Retry Queue Updated' },
							{ field: 'notify_retry_queue_removed', label: 'Order Removed from Retry Queue' },
							{ field: 'notify_retry_queue_retried', label: 'Order Retried Successfully' },
						].map(({ field, label }) => (
							<label key={field} className="flex items-center gap-3">
								<input
									type="checkbox"
									checked={localPrefs[field as keyof NotificationPreferences] as boolean}
									onChange={(e) => handleChange(field as keyof NotificationPreferences, e.target.checked)}
									className="w-4 h-4"
								/>
								<span className="text-sm">{label}</span>
							</label>
						))}
					</div>
				</SectionCard>

				{/* ── System Events ────────────────────────────────────────── */}
				<SectionCard
					id="np-system"
					icon="⚙️"
					title="System Events"
					isOpen={openSection === 'system'}
					onToggle={() => toggle('system')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Control notifications for system-level events.
					</p>
					<BulkActions
						onEnable={() => handleEnableAll('system')}
						onDisable={() => handleDisableAll('system')}
					/>
					<div className="space-y-2">
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_system_errors}
								onChange={(e) => handleChange('notify_system_errors', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">System Errors</span>
						</label>
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_system_warnings}
								onChange={(e) => handleChange('notify_system_warnings', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">
								System Warnings <span className="text-xs text-[var(--muted)]">(Opt-in)</span>
							</span>
						</label>
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_system_info}
								onChange={(e) => handleChange('notify_system_info', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">
								System Info <span className="text-xs text-[var(--muted)]">(Opt-in)</span>
							</span>
						</label>
					</div>
				</SectionCard>

				{/* ── Service Events ───────────────────────────────────────── */}
				<SectionCard
					id="np-service"
					icon="🔧"
					title="Service Events"
					isOpen={openSection === 'service'}
					onToggle={() => toggle('service')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Control notifications for service lifecycle events.
					</p>
					<BulkActions
						onEnable={() => handleEnableAll('service')}
						onDisable={() => handleDisableAll('service')}
					/>
					<div className="space-y-2">
						{[
							{ field: 'notify_service_started', label: 'Service Started' },
							{ field: 'notify_service_stopped', label: 'Service Stopped' },
							{ field: 'notify_service_execution_completed', label: 'Service Execution Completed' },
						].map(({ field, label }) => (
							<label key={field} className="flex items-center gap-3">
								<input
									type="checkbox"
									checked={localPrefs[field as keyof NotificationPreferences] as boolean}
									onChange={(e) => handleChange(field as keyof NotificationPreferences, e.target.checked)}
									className="w-4 h-4"
								/>
								<span className="text-sm">{label}</span>
							</label>
						))}
					</div>
				</SectionCard>

				{/* ── Billing ──────────────────────────────────────────────── */}
				<SectionCard
					id="np-billing"
					icon="💳"
					title="Billing Emails"
					isOpen={openSection === 'billing'}
					onToggle={() => toggle('billing')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						When Razorpay reports a failed billing payment (e.g. performance fee order).
					</p>
					<BulkActions
						onEnable={() => handleEnableAll('billing')}
						onDisable={() => handleDisableAll('billing')}
					/>
					<div className="space-y-2">
						<label className="flex items-center gap-3">
							<input
								type="checkbox"
								checked={localPrefs.notify_payment_failed}
								onChange={(e) => handleChange('notify_payment_failed', e.target.checked)}
								className="w-4 h-4"
							/>
							<span className="text-sm">Payment Failed</span>
						</label>
					</div>
				</SectionCard>

				{/* ── Quiet Hours ──────────────────────────────────────────── */}
				<SectionCard
					id="np-quiet"
					icon="🌙"
					title="Quiet Hours"
					isOpen={openSection === 'quiet'}
					onToggle={() => toggle('quiet')}
				>
					<p className="text-xs sm:text-sm text-[var(--muted)]">
						Set a time range when notifications will be suppressed (e.g. 22:00–08:00 for nighttime).
					</p>
					<div className="flex items-end gap-3">
						<div className="flex-1">
							<label className="block text-xs sm:text-sm mb-1">Start Time</label>
							<input
								type="time"
								value={localPrefs.quiet_hours_start?.substring(0, 5) || ''}
								onChange={(e) =>
									handleChange('quiet_hours_start', e.target.value ? `${e.target.value}:00` : null)
								}
								className="w-full px-3 py-2 rounded bg-[#070e17] border border-[#1e293b] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
							/>
						</div>
						<div className="flex-1">
							<label className="block text-xs sm:text-sm mb-1">End Time</label>
							<input
								type="time"
								value={localPrefs.quiet_hours_end?.substring(0, 5) || ''}
								onChange={(e) =>
									handleChange('quiet_hours_end', e.target.value ? `${e.target.value}:00` : null)
								}
								className="w-full px-3 py-2 rounded bg-[#070e17] border border-[#1e293b] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
							/>
						</div>
						<button
							type="button"
							onClick={() => {
								handleChange('quiet_hours_start', null);
								handleChange('quiet_hours_end', null);
							}}
							className="px-4 py-2 rounded bg-gray-600 hover:bg-gray-700 text-white text-sm min-h-[40px]"
						>
							Clear
						</button>
					</div>
					{localPrefs.quiet_hours_start && localPrefs.quiet_hours_end && (
						<p className="text-xs text-[var(--muted)]">
							Notifications suppressed between {localPrefs.quiet_hours_start.substring(0, 5)} and{' '}
							{localPrefs.quiet_hours_end.substring(0, 5)}.
						</p>
					)}
				</SectionCard>
			</div>

			{/* Save bar */}
			{hasChanges && (
				<div className="sticky bottom-2 sm:bottom-4 mt-4 bg-[#0c1521] border border-[#1e293b] rounded-lg p-3 sm:p-4 shadow-lg">
					<div className="flex items-center justify-between">
						<span className="text-sm text-yellow-400">Unsaved changes</span>
						<div className="flex gap-3">
							<button
								type="button"
								onClick={() => {
									if (preferences) setLocalPrefs(preferences);
									setHasChanges(false);
								}}
								className="px-4 py-2 rounded bg-gray-600 hover:bg-gray-700 text-white text-sm min-h-[40px]"
							>
								Cancel
							</button>
							<button
								onClick={handleSave}
								disabled={updateMutation.isPending}
								className="px-4 py-2 rounded bg-[var(--accent)] text-black text-sm font-medium min-h-[40px] disabled:opacity-60"
							>
								{updateMutation.isPending ? 'Saving…' : 'Save Preferences'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
