import { api } from './client';

export type BuyingZoneItem = {
	id: number;
	symbol: string;
	rsi10?: number | null;
	ema9?: number | null;
	ema200?: number | null;
	distance_to_ema9?: number | null;
	clean_chart?: boolean | null;
	monthly_support_dist?: number | null;
	confidence?: number | null;
	ts: string;
};

export async function getBuyingZone(limit = 100): Promise<BuyingZoneItem[]> {
	const res = await api.get('/signals/buying-zone', { params: { limit } });
	return res.data as BuyingZoneItem[];
}
