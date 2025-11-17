import { api } from './client';

export interface TradingConfig {
	// RSI Configuration
	rsi_period: number;
	rsi_oversold: number;
	rsi_extreme_oversold: number;
	rsi_near_oversold: number;

	// Capital & Position Management
	user_capital: number;
	max_portfolio_size: number;
	max_position_volume_ratio: number;
	min_absolute_avg_volume: number;

	// Chart Quality Filters
	chart_quality_enabled: boolean;
	chart_quality_min_score: number;
	chart_quality_max_gap_frequency: number;
	chart_quality_min_daily_range_pct: number;
	chart_quality_max_extreme_candle_frequency: number;

	// Risk Management
	default_stop_loss_pct: number | null;
	tight_stop_loss_pct: number | null;
	min_stop_loss_pct: number | null;
	default_target_pct: number;
	strong_buy_target_pct: number;
	excellent_target_pct: number;

	// Risk-Reward Ratios
	strong_buy_risk_reward: number;
	buy_risk_reward: number;
	excellent_risk_reward: number;

	// Order Defaults
	default_exchange: string;
	default_product: string;
	default_order_type: string;
	default_variety: string;
	default_validity: string;

	// Behavior Toggles
	allow_duplicate_recommendations_same_day: boolean;
	exit_on_ema9_or_rsi50: boolean;
	min_combined_score: number;

	// News Sentiment
	news_sentiment_enabled: boolean;
	news_sentiment_lookback_days: number;
	news_sentiment_min_articles: number;
	news_sentiment_pos_threshold: number;
	news_sentiment_neg_threshold: number;

	// ML Configuration
	ml_enabled: boolean;
	ml_model_version: string | null;
	ml_confidence_threshold: number;
	ml_combine_with_rules: boolean;
}

export interface TradingConfigUpdate {
	// All fields are optional for partial updates
	rsi_period?: number;
	rsi_oversold?: number;
	rsi_extreme_oversold?: number;
	rsi_near_oversold?: number;
	user_capital?: number;
	max_portfolio_size?: number;
	max_position_volume_ratio?: number;
	min_absolute_avg_volume?: number;
	chart_quality_enabled?: boolean;
	chart_quality_min_score?: number;
	chart_quality_max_gap_frequency?: number;
	chart_quality_min_daily_range_pct?: number;
	chart_quality_max_extreme_candle_frequency?: number;
	default_stop_loss_pct?: number | null;
	tight_stop_loss_pct?: number | null;
	min_stop_loss_pct?: number | null;
	default_target_pct?: number;
	strong_buy_target_pct?: number;
	excellent_target_pct?: number;
	strong_buy_risk_reward?: number;
	buy_risk_reward?: number;
	excellent_risk_reward?: number;
	default_exchange?: 'NSE' | 'BSE';
	default_product?: 'CNC' | 'MIS' | 'NRML';
	default_order_type?: 'MARKET' | 'LIMIT';
	default_variety?: 'AMO' | 'REGULAR';
	default_validity?: 'DAY' | 'IOC' | 'GTC';
	allow_duplicate_recommendations_same_day?: boolean;
	exit_on_ema9_or_rsi50?: boolean;
	min_combined_score?: number;
	news_sentiment_enabled?: boolean;
	news_sentiment_lookback_days?: number;
	news_sentiment_min_articles?: number;
	news_sentiment_pos_threshold?: number;
	news_sentiment_neg_threshold?: number;
	ml_enabled?: boolean;
	ml_model_version?: string | null;
	ml_confidence_threshold?: number;
	ml_combine_with_rules?: boolean;
}

export interface ConfigPreset {
	id: string;
	name: string;
	description: string;
	config: Partial<TradingConfig>;
}

export async function getTradingConfig(): Promise<TradingConfig> {
	const { data } = await api.get<TradingConfig>('/user/trading-config');
	return data;
}

export async function updateTradingConfig(config: TradingConfigUpdate): Promise<TradingConfig> {
	const { data } = await api.put<TradingConfig>('/user/trading-config', config);
	return data;
}

export async function resetTradingConfig(): Promise<TradingConfig> {
	const { data } = await api.post<TradingConfig>('/user/trading-config/reset');
	return data;
}

// Default configuration values (for comparison)
export const DEFAULT_CONFIG: TradingConfig = {
	rsi_period: 10,
	rsi_oversold: 30.0,
	rsi_extreme_oversold: 20.0,
	rsi_near_oversold: 40.0,
	user_capital: 200000.0,
	max_portfolio_size: 6,
	max_position_volume_ratio: 0.1,
	min_absolute_avg_volume: 10000,
	chart_quality_enabled: true,
	chart_quality_min_score: 50.0,
	chart_quality_max_gap_frequency: 25.0,
	chart_quality_min_daily_range_pct: 1.0,
	chart_quality_max_extreme_candle_frequency: 20.0,
	default_stop_loss_pct: 0.08,
	tight_stop_loss_pct: 0.06,
	min_stop_loss_pct: 0.03,
	default_target_pct: 0.1,
	strong_buy_target_pct: 0.12,
	excellent_target_pct: 0.15,
	strong_buy_risk_reward: 3.0,
	buy_risk_reward: 2.5,
	excellent_risk_reward: 3.5,
	default_exchange: 'NSE',
	default_product: 'CNC',
	default_order_type: 'MARKET',
	default_variety: 'AMO',
	default_validity: 'DAY',
	allow_duplicate_recommendations_same_day: false,
	exit_on_ema9_or_rsi50: true,
	min_combined_score: 50,
	news_sentiment_enabled: false,
	news_sentiment_lookback_days: 7,
	news_sentiment_min_articles: 3,
	news_sentiment_pos_threshold: 0.6,
	news_sentiment_neg_threshold: -0.4,
	ml_enabled: false,
	ml_model_version: null,
	ml_confidence_threshold: 0.7,
	ml_combine_with_rules: true,
};

// Configuration presets
export const CONFIG_PRESETS: ConfigPreset[] = [
	{
		id: 'conservative',
		name: 'Conservative',
		description: 'Lower risk, fewer positions, stricter filters',
		config: {
			max_portfolio_size: 4,
			rsi_oversold: 25.0,
			rsi_extreme_oversold: 15.0,
			chart_quality_min_score: 60.0,
			default_target_pct: 0.08,
			strong_buy_target_pct: 0.10,
			excellent_target_pct: 0.12,
			min_combined_score: 60,
		},
	},
	{
		id: 'moderate',
		name: 'Moderate',
		description: 'Balanced risk and position sizing (default)',
		config: {
			max_portfolio_size: 6,
			rsi_oversold: 30.0,
			rsi_extreme_oversold: 20.0,
			chart_quality_min_score: 50.0,
			default_target_pct: 0.1,
			strong_buy_target_pct: 0.12,
			excellent_target_pct: 0.15,
			min_combined_score: 50,
		},
	},
	{
		id: 'aggressive',
		name: 'Aggressive',
		description: 'Higher risk, more positions, relaxed filters',
		config: {
			max_portfolio_size: 8,
			rsi_oversold: 35.0,
			rsi_extreme_oversold: 25.0,
			chart_quality_min_score: 40.0,
			default_target_pct: 0.12,
			strong_buy_target_pct: 0.15,
			excellent_target_pct: 0.18,
			min_combined_score: 40,
		},
	},
];
