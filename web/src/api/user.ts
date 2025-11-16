import { api } from './client';

export type Settings = {
	trade_mode: 'paper' | 'broker';
	broker?: string | null;
	broker_status?: string | null;
};

export async function getSettings(): Promise<Settings> {
	const res = await api.get('/user/settings');
	return res.data as Settings;
}

export async function updateSettings(input: Partial<Settings>): Promise<Settings> {
	const res = await api.put('/user/settings', input);
	return res.data as Settings;
}
