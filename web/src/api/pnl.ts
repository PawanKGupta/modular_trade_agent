import { api } from './client';

export interface DailyPnl {
	date: string; // YYYY-MM-DD
	pnl: number;
}

export interface PnlSummary {
	totalPnl: number;
	daysGreen: number;
	daysRed: number;
}

export async function getDailyPnl(start?: string, end?: string): Promise<DailyPnl[]> {
	const params: Record<string, string> = {};
	if (start) params.start = start;
	if (end) params.end = end;
	const { data } = await api.get<DailyPnl[]>('/user/pnl/daily', { params });
	return data;
}

export async function getPnlSummary(start?: string, end?: string): Promise<PnlSummary> {
	const params: Record<string, string> = {};
	if (start) params.start = start;
	if (end) params.end = end;
	const { data } = await api.get<PnlSummary>('/user/pnl/summary', { params });
	return data;
}
