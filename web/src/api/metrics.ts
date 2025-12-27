import { api } from './client';

export interface TradeMetrics {
	total_trades: number;
	profitable_trades: number;
	losing_trades: number;
	win_rate: number;
	average_profit_per_trade: number;
	best_trade_profit: number | null;
	worst_trade_loss: number | null;
	total_realized_pnl: number;
	best_trade_symbol: string | null;
	worst_trade_symbol: string | null;
	days_traded: number;
	avg_holding_period_days: number;
}

export interface DailyMetrics {
	date: string;
	trades: number;
	profitable_trades: number;
	losing_trades: number;
	daily_pnl: number;
	win_rate: number;
}

export async function getDashboardMetrics(
	periodDays?: number,
	tradeMode?: string,
): Promise<TradeMetrics> {
	const params: Record<string, unknown> = {};
	if (periodDays) params.period_days = periodDays;
	if (tradeMode) params.trade_mode = tradeMode;

	const { data } = await api.get<TradeMetrics>('/dashboard/metrics', { params });
	return data;
}

export async function getDailyMetrics(dateStr?: string, tradeMode?: string): Promise<DailyMetrics> {
	const params: Record<string, string> = {};
	if (dateStr) params.date_str = dateStr;
	if (tradeMode) params.trade_mode = tradeMode;

	const { data } = await api.get<DailyMetrics>('/dashboard/metrics/daily', { params });
	return data;
}
