import { api } from './client';

export interface PortfolioSnapshot {
	date: string; // YYYY-MM-DD
	total_value: number;
	invested_value: number;
	available_cash: number;
	unrealized_pnl: number;
	realized_pnl: number;
	open_positions_count: number;
	closed_positions_count: number;
	total_return: number;
	daily_return: number;
	snapshot_type: string;
}

function formatDate(date: Date | string): string {
	if (typeof date === 'string') {
		return date;
	}
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

export async function getPortfolioHistory(
	start?: Date | string,
	end?: Date | string,
	limit?: number,
): Promise<PortfolioSnapshot[]> {
	const params: Record<string, any> = {};
	if (start) params.start = formatDate(start);
	if (end) params.end = formatDate(end);
	if (limit) params.limit = limit;

	const { data } = await api.get<PortfolioSnapshot[]>('/user/portfolio/history', { params });
	return data || [];
}

export async function createPortfolioSnapshot(snapshotDate?: string): Promise<any> {
	const params: Record<string, string> = {};
	if (snapshotDate) params.snapshot_date = snapshotDate;

	const { data } = await api.post('/user/portfolio/snapshot', {}, { params });
	return data;
}
