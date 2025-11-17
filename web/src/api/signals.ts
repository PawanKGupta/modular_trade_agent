import { api } from './client';

export type BuyingZoneItem = {
	id: number;
	symbol: string;
	// Technical indicators
	rsi10?: number | null;
	ema9?: number | null;
	ema200?: number | null;
	distance_to_ema9?: number | null;
	clean_chart?: boolean | null;
	monthly_support_dist?: number | null;
	confidence?: number | null;
	// Scoring fields
	backtest_score?: number | null;
	combined_score?: number | null;
	strength_score?: number | null;
	priority_score?: number | null;
	// ML fields
	ml_verdict?: string | null;
	ml_confidence?: number | null;
	ml_probabilities?: Record<string, number> | null;
	// Trading parameters
	buy_range?: { low: number; high: number } | null;
	target?: number | null;
	stop?: number | null;
	last_close?: number | null;
	// Fundamental data
	pe?: number | null;
	pb?: number | null;
	fundamental_assessment?: string | null;
	fundamental_ok?: boolean | null;
	// Volume data
	avg_vol?: number | null;
	today_vol?: number | null;
	volume_analysis?: Record<string, any> | null;
	volume_pattern?: Record<string, any> | null;
	volume_description?: string | null;
	vol_ok?: boolean | null;
	volume_ratio?: number | null;
	// Analysis metadata
	verdict?: string | null;
	signals?: string[] | null;
	justification?: string[] | null;
	timeframe_analysis?: Record<string, any> | null;
	news_sentiment?: Record<string, any> | null;
	candle_analysis?: Record<string, any> | null;
	chart_quality?: Record<string, any> | null;
	// Timestamp
	ts: string;
};

export async function getBuyingZone(limit = 100): Promise<BuyingZoneItem[]> {
	const res = await api.get('/signals/buying-zone', { params: { limit } });
	return res.data as BuyingZoneItem[];
}

export async function getBuyingZoneColumns(): Promise<string[]> {
	const res = await api.get('/user/buying-zone-columns');
	return (res.data as { columns: string[] }).columns;
}

export async function saveBuyingZoneColumns(columns: string[]): Promise<string[]> {
	const res = await api.put('/user/buying-zone-columns', { columns });
	return (res.data as { columns: string[] }).columns;
}
