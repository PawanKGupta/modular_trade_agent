import { api } from './client';

export interface ActivityItem {
	id: number;
	ts: string;
	event: string;
	detail?: string | null;
	level?: 'info' | 'warn' | 'error';
}

export async function listActivity(level?: ActivityItem['level']): Promise<ActivityItem[]> {
	const params = level ? { level } : undefined;
	const { data } = await api.get<ActivityItem[]>('/user/activity', { params });
	return data;
}
