import { api } from './client';

export type Notification = {
	id: number;
	user_id: number;
	type: 'service' | 'trading' | 'system' | 'error';
	level: 'info' | 'warning' | 'error' | 'critical';
	title: string;
	message: string;
	read: boolean;
	read_at: string | null;
	created_at: string;
	telegram_sent: boolean;
	email_sent: boolean;
	in_app_delivered: boolean;
};

export type NotificationFilters = {
	type?: 'service' | 'trading' | 'system' | 'error';
	level?: 'info' | 'warning' | 'error' | 'critical';
	read?: boolean;
	limit?: number;
};

export async function getNotifications(filters?: NotificationFilters): Promise<Notification[]> {
	const params = new URLSearchParams();
	if (filters?.type) params.append('type', filters.type);
	if (filters?.level) params.append('level', filters.level);
	if (filters?.read !== undefined) params.append('read', String(filters.read));
	if (filters?.limit) params.append('limit', String(filters.limit));

	const res = await api.get(`/user/notifications?${params.toString()}`);
	return res.data as Notification[];
}

export async function getUnreadNotifications(limit?: number): Promise<Notification[]> {
	const params = new URLSearchParams();
	if (limit) params.append('limit', String(limit));

	const res = await api.get(`/user/notifications/unread?${params.toString()}`);
	return res.data as Notification[];
}

export async function getNotificationCount(): Promise<{ unread_count: number }> {
	const res = await api.get('/user/notifications/count');
	return res.data as { unread_count: number };
}

export async function markNotificationRead(notificationId: number): Promise<Notification> {
	const res = await api.post(`/user/notifications/${notificationId}/read`);
	return res.data as Notification;
}

export async function markAllNotificationsRead(): Promise<{ marked_read: number }> {
	const res = await api.post('/user/notifications/read-all');
	return res.data as { marked_read: number };
}
