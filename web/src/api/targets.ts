import { api } from './client';

export interface TargetItem {
	id: number;
	symbol: string;
	target_price: number;
	note?: string | null;
	created_at: string;
}

export async function listTargets(): Promise<TargetItem[]> {
	const { data } = await api.get<TargetItem[]>('/user/targets');
	return data;
}
