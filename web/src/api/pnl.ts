import { api } from './client';

export interface DailyPnl {
	date: string; // YYYY-MM-DD
	pnl: number;
	realized_pnl?: number;
	unrealized_pnl?: number;
	fees?: number;
}

export interface PnlSummary {
	totalPnl: number;
	totalRealizedPnl: number;
	totalUnrealizedPnl: number;
	tradesGreen: number;
	tradesRed: number;
	minTradePnl: number;
	maxTradePnl: number;
	avgTradePnl: number;
	// Backward-compat
	daysGreen: number;
	daysRed: number;
}

export interface ClosedPositionDetail {
	id: number;
	symbol: string;
	stock_name: string | null;
	quantity: number;
	avg_price: number;
	exit_price: number | null;
	opened_at: string;
	closed_at: string;
	realized_pnl: number | null;
	realized_pnl_pct: number | null;
	exit_reason: string | null;
}

export interface PaginatedClosedPositions {
	items: ClosedPositionDetail[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
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

export async function getDailyPnl(
	start?: Date | string,
	end?: Date | string,
	tradeMode?: 'paper' | 'broker',
	includeUnrealized?: boolean,
): Promise<DailyPnl[]> {
	const params: Record<string, string> = {};
	if (start) params.start = formatDate(start);
	if (end) params.end = formatDate(end);
	if (tradeMode) params.trade_mode = tradeMode;
	if (includeUnrealized) params.include_unrealized = 'true';
	const { data } = await api.get<DailyPnl[]>('/user/pnl/daily', { params });
	return data;
}

export async function getPnlSummary(
	start?: Date | string,
	end?: Date | string,
	tradeMode?: 'paper' | 'broker',
	includeUnrealized?: boolean,
): Promise<PnlSummary> {
	const params: Record<string, string> = {};
	if (start) params.start = formatDate(start);
	if (end) params.end = formatDate(end);
	if (tradeMode) params.trade_mode = tradeMode;
	if (includeUnrealized) params.include_unrealized = 'true';
	const { data } = await api.get<PnlSummary>('/user/pnl/summary', { params });
	return data;
}

export async function triggerPnlCalculation(targetDate?: string, tradeMode?: string): Promise<unknown> {
	const params: Record<string, string> = {};
	if (targetDate) params.target_date = targetDate;
	if (tradeMode) params.trade_mode = tradeMode;
	const { data } = await api.post('/user/pnl/calculate', {}, { params });
	return data;
}

export async function backfillPnlData(startDate: string, endDate: string, tradeMode?: string): Promise<unknown> {
	const params: Record<string, string> = {
		start_date: startDate,
		end_date: endDate,
	};
	if (tradeMode) params.trade_mode = tradeMode;
	const { data } = await api.post('/user/pnl/backfill', {}, { params });
	return data;
}

export async function getClosedPositions(
	page: number = 1,
	pageSize: number = 10,
	tradeMode?: 'paper' | 'broker',
	sortBy: string = 'closed_at',
	sortOrder: 'asc' | 'desc' = 'desc',
): Promise<PaginatedClosedPositions> {
	const params: Record<string, string> = {
		page: page.toString(),
		page_size: pageSize.toString(),
		sort_by: sortBy,
		sort_order: sortOrder,
	};
	if (tradeMode) params.trade_mode = tradeMode;
	const { data } = await api.get<PaginatedClosedPositions>('/user/pnl/closed-positions', { params });
	return data;
}
