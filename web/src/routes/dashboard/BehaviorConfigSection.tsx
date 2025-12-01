import { type TradingConfig } from '@/api/trading-config';

interface BehaviorConfigSectionProps {
	config: TradingConfig;
	defaultConfig: TradingConfig;
	onChange: (updates: Partial<TradingConfig>) => void;
}

export function BehaviorConfigSection({ config, defaultConfig, onChange }: BehaviorConfigSectionProps) {
	const isDefault = (key: keyof TradingConfig) => config[key] === defaultConfig[key];

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
			<h2 className="text-lg font-semibold mb-4">Behavior Settings</h2>

			<div className="space-y-4">
				<div>
					<label htmlFor="allow_duplicate_recommendations_same_day" className="flex items-center gap-2">
						<input
							id="allow_duplicate_recommendations_same_day"
							type="checkbox"
							checked={config.allow_duplicate_recommendations_same_day}
							onChange={(e) => onChange({ allow_duplicate_recommendations_same_day: e.target.checked })}
							className="rounded"
						/>
						<span className="text-sm">
							Allow Duplicate Recommendations Same Day
							{!isDefault('allow_duplicate_recommendations_same_day') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Default: {defaultConfig.allow_duplicate_recommendations_same_day ? 'Enabled' : 'Disabled'}
					</div>
				</div>

				<div>
					<label htmlFor="exit_on_ema9_or_rsi50" className="flex items-center gap-2">
						<input
							id="exit_on_ema9_or_rsi50"
							type="checkbox"
							checked={config.exit_on_ema9_or_rsi50}
							onChange={(e) => onChange({ exit_on_ema9_or_rsi50: e.target.checked })}
							className="rounded"
						/>
						<span className="text-sm">
							Exit on EMA9 or RSI50
							{!isDefault('exit_on_ema9_or_rsi50') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Default: {defaultConfig.exit_on_ema9_or_rsi50 ? 'Enabled' : 'Disabled'}
					</div>
					<div className="text-xs text-blue-400 mt-1 ml-6">
						When enabled, positions will exit when price reaches EMA9 or RSI reaches 50
					</div>
				</div>

				<div>
					<label htmlFor="enable_premarket_amo_adjustment" className="flex items-center gap-2">
						<input
							id="enable_premarket_amo_adjustment"
							type="checkbox"
							checked={config.enable_premarket_amo_adjustment}
							onChange={(e) => onChange({ enable_premarket_amo_adjustment: e.target.checked })}
							className="rounded"
						/>
						<span className="text-sm">
							Enable Pre-Market AMO Adjustment (9:05 AM)
							{!isDefault('enable_premarket_amo_adjustment') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Default: {defaultConfig.enable_premarket_amo_adjustment ? 'Enabled' : 'Disabled'}
					</div>
					<div className="text-xs text-blue-400 mt-1 ml-6">
						Automatically adjust AMO order quantities at 9:05 AM based on pre-market prices to keep capital constant
					</div>
				</div>

				<div>
					<label htmlFor="min_combined_score" className="block text-sm mb-1">
						Min Combined Score
						{!isDefault('min_combined_score') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<input
						id="min_combined_score"
						type="number"
						min="0"
						max="100"
						value={config.min_combined_score}
						onChange={(e) => onChange({ min_combined_score: parseInt(e.target.value) || 50 })}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
					/>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.min_combined_score}</div>
					<div className="text-xs text-blue-400 mt-1">
						Minimum combined score (0-100) required for trade recommendations
					</div>
				</div>
			</div>

			{/* News Sentiment Settings */}
			<div className="mt-6 pt-6 border-t border-[#1e293b]">
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">News Sentiment</h3>
				<div className="mb-4">
					<label htmlFor="news_sentiment_enabled" className="flex items-center gap-2">
						<input
							id="news_sentiment_enabled"
							type="checkbox"
							checked={config.news_sentiment_enabled}
							onChange={(e) => onChange({ news_sentiment_enabled: e.target.checked })}
							className="rounded"
						/>
						<span className="text-sm">
							Enable News Sentiment Analysis
							{!isDefault('news_sentiment_enabled') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Default: {defaultConfig.news_sentiment_enabled ? 'Enabled' : 'Disabled'}
					</div>
				</div>
				{config.news_sentiment_enabled && (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 ml-6">
						<div>
							<label htmlFor="news_sentiment_lookback_days" className="block text-sm mb-1">
								Lookback Days
								{!isDefault('news_sentiment_lookback_days') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="news_sentiment_lookback_days"
								type="number"
								min="1"
								max="365"
								value={config.news_sentiment_lookback_days}
								onChange={(e) => onChange({ news_sentiment_lookback_days: parseInt(e.target.value) || 7 })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.news_sentiment_lookback_days}</div>
						</div>
						<div>
							<label htmlFor="news_sentiment_min_articles" className="block text-sm mb-1">
								Min Articles
								{!isDefault('news_sentiment_min_articles') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="news_sentiment_min_articles"
								type="number"
								min="0"
								value={config.news_sentiment_min_articles}
								onChange={(e) => onChange({ news_sentiment_min_articles: parseInt(e.target.value) || 3 })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.news_sentiment_min_articles}</div>
						</div>
						<div>
							<label htmlFor="news_sentiment_pos_threshold" className="block text-sm mb-1">
								Positive Threshold
								{!isDefault('news_sentiment_pos_threshold') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="news_sentiment_pos_threshold"
								type="number"
								step="0.1"
								min="-1"
								max="1"
								value={config.news_sentiment_pos_threshold}
								onChange={(e) => onChange({ news_sentiment_pos_threshold: parseFloat(e.target.value) || 0.6 })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.news_sentiment_pos_threshold}</div>
						</div>
						<div>
							<label htmlFor="news_sentiment_neg_threshold" className="block text-sm mb-1">
								Negative Threshold
								{!isDefault('news_sentiment_neg_threshold') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="news_sentiment_neg_threshold"
								type="number"
								step="0.1"
								min="-1"
								max="1"
								value={config.news_sentiment_neg_threshold}
								onChange={(e) => onChange({ news_sentiment_neg_threshold: parseFloat(e.target.value) || -0.4 })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.news_sentiment_neg_threshold}</div>
						</div>
					</div>
				)}
			</div>

			{/* ML Configuration */}
			<div className="mt-6 pt-6 border-t border-[#1e293b]">
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">ML Configuration</h3>
				<div className="mb-4">
					<label htmlFor="ml_enabled" className="flex items-center gap-2">
						<input
							id="ml_enabled"
							type="checkbox"
							checked={config.ml_enabled}
							onChange={(e) => onChange({ ml_enabled: e.target.checked })}
							className="rounded"
						/>
						<span className="text-sm">
							Enable ML Predictions
							{!isDefault('ml_enabled') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Default: {defaultConfig.ml_enabled ? 'Enabled' : 'Disabled'}
					</div>
				</div>
				{config.ml_enabled && (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 ml-6">
						<div>
							<label htmlFor="ml_model_version" className="block text-sm mb-1">
								ML Model Version
								{!isDefault('ml_model_version') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="ml_model_version"
								type="text"
								value={config.ml_model_version || ''}
								onChange={(e) => onChange({ ml_model_version: e.target.value || null })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
								placeholder="v1.0"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">
								Default: {defaultConfig.ml_model_version || 'None'}
							</div>
						</div>
						<div>
							<label htmlFor="ml_confidence_threshold" className="block text-sm mb-1">
								Confidence Threshold
								{!isDefault('ml_confidence_threshold') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="ml_confidence_threshold"
								type="number"
								step="0.1"
								min="0"
								max="1"
								value={config.ml_confidence_threshold}
								onChange={(e) => onChange({ ml_confidence_threshold: parseFloat(e.target.value) || 0.7 })}
								className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.ml_confidence_threshold}</div>
						</div>
						<div>
							<label htmlFor="ml_combine_with_rules" className="flex items-center gap-2">
								<input
									id="ml_combine_with_rules"
									type="checkbox"
									checked={config.ml_combine_with_rules}
									onChange={(e) => onChange({ ml_combine_with_rules: e.target.checked })}
									className="rounded"
								/>
								<span className="text-sm">
									Combine ML with Rule-Based Logic
									{!isDefault('ml_combine_with_rules') && <span className="text-yellow-400 ml-1">*</span>}
								</span>
							</label>
							<div className="text-xs text-[var(--muted)] mt-1 ml-6">
								Default: {defaultConfig.ml_combine_with_rules ? 'Enabled' : 'Disabled'}
							</div>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
