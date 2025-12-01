import { api } from './client';

export type NotificationPreferences = {
	// Notification channels
	telegram_enabled: boolean;
	telegram_chat_id: string | null;
	email_enabled: boolean;
	email_address: string | null;
	in_app_enabled: boolean;
	// Legacy notification types
	notify_service_events: boolean;
	notify_trading_events: boolean;
	notify_system_events: boolean;
	notify_errors: boolean;
	// Granular order event preferences
	notify_order_placed: boolean;
	notify_order_rejected: boolean;
	notify_order_executed: boolean;
	notify_order_cancelled: boolean;
	notify_order_modified: boolean;
	notify_retry_queue_added: boolean;
	notify_retry_queue_updated: boolean;
	notify_retry_queue_removed: boolean;
	notify_retry_queue_retried: boolean;
	notify_partial_fill: boolean;
	// System event preferences
	notify_system_errors: boolean;
	notify_system_warnings: boolean;
	notify_system_info: boolean;
	// Granular service event preferences
	notify_service_started: boolean;
	notify_service_stopped: boolean;
	notify_service_execution_completed: boolean;
	// Quiet hours
	quiet_hours_start: string | null; // Time in HH:MM:SS format
	quiet_hours_end: string | null; // Time in HH:MM:SS format
};

export type NotificationPreferencesUpdate = Partial<NotificationPreferences>;

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
	const res = await api.get('/user/notification-preferences');
	return res.data as NotificationPreferences;
}

export async function updateNotificationPreferences(
	input: NotificationPreferencesUpdate
): Promise<NotificationPreferences> {
	const res = await api.put('/user/notification-preferences', input);
	return res.data as NotificationPreferences;
}
