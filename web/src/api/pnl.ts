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

export async function getDailyPnl(): Promise<DailyPnl[]> {
	const { data } = await api.get<DailyPnl[]>('/user/pnl/daily');
	return data;
}

export async function getPnlSummary(): Promise<PnlSummary> {
	const { data } = await api.get<PnlSummary>('/user/pnl/summary');
	return data;
}
