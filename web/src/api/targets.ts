import { api } from './client';

export interface TargetItem {
	id: number;
	symbol: string;
	target_price: number;
	entry_price: number;
	current_price: number | null;
	quantity: number;
	distance_to_target: number | null;
	distance_to_target_absolute: number | null;
	target_type: string;
	is_active: boolean;
	achieved_at: string | null;
	note: string | null;
	created_at: string;
	updated_at: string;
}

export async function listTargets(): Promise<TargetItem[]> {
	const { data } = await api.get<TargetItem[]>('/user/targets');
	return data;
}
