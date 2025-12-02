import { type TradingConfig } from '@/api/trading-config';

interface StrategyConfigSectionProps {
	config: TradingConfig;
	defaultConfig: TradingConfig;
	onChange: (updates: Partial<TradingConfig>) => void;
}

export function StrategyConfigSection({ config, defaultConfig, onChange }: StrategyConfigSectionProps) {
	const isDefault = (key: keyof TradingConfig) => config[key] === defaultConfig[key];

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
			<h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Strategy Parameters</h2>

			{/* RSI Configuration */}
			<div className="mb-4 sm:mb-6">
				<h3 className="text-xs sm:text-sm font-medium mb-2 sm:mb-3 text-[var(--muted)]">RSI Configuration</h3>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
					<div>
						<label htmlFor="rsi_period" className="block text-xs sm:text-sm mb-1">
							RSI Period
							{!isDefault('rsi_period') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="rsi_period"
							type="number"
							min="1"
							max="50"
							value={config.rsi_period}
							onChange={(e) => onChange({ rsi_period: parseInt(e.target.value) || 10 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.rsi_period}</div>
					</div>
					<div>
						<label htmlFor="rsi_oversold" className="block text-xs sm:text-sm mb-1">
							RSI Oversold Threshold
							{!isDefault('rsi_oversold') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="rsi_oversold"
							type="number"
							step="0.1"
							min="0"
							max="50"
							value={config.rsi_oversold}
							onChange={(e) => onChange({ rsi_oversold: parseFloat(e.target.value) || 30 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.rsi_oversold}</div>
					</div>
					<div>
						<label htmlFor="rsi_extreme_oversold" className="block text-xs sm:text-sm mb-1">
							RSI Extreme Oversold
							{!isDefault('rsi_extreme_oversold') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="rsi_extreme_oversold"
							type="number"
							step="0.1"
							min="0"
							max="30"
							value={config.rsi_extreme_oversold}
							onChange={(e) => onChange({ rsi_extreme_oversold: parseFloat(e.target.value) || 20 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.rsi_extreme_oversold}</div>
						<div className="text-xs text-red-400 mt-1">
							Must be &lt; RSI Oversold ({config.rsi_oversold})
						</div>
					</div>
					<div>
						<label htmlFor="rsi_near_oversold" className="block text-xs sm:text-sm mb-1">
							RSI Near Oversold
							{!isDefault('rsi_near_oversold') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="rsi_near_oversold"
							type="number"
							step="0.1"
							min="30"
							max="50"
							value={config.rsi_near_oversold}
							onChange={(e) => onChange({ rsi_near_oversold: parseFloat(e.target.value) || 40 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.rsi_near_oversold}</div>
						<div className="text-xs text-red-400 mt-1">
							Must be &gt; RSI Oversold ({config.rsi_oversold})
						</div>
					</div>
				</div>
			</div>

			{/* Chart Quality Filters */}
			<div className="mb-6">
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">Chart Quality Filters</h3>
					<div className="mb-4">
					<label htmlFor="chart_quality_enabled" className="flex items-center gap-2 min-h-[44px] sm:min-h-0">
						<input
							id="chart_quality_enabled"
							type="checkbox"
							checked={config.chart_quality_enabled}
							onChange={(e) => onChange({ chart_quality_enabled: e.target.checked })}
							className="rounded w-4 h-4 sm:w-auto sm:h-auto"
						/>
						<span className="text-xs sm:text-sm">
							Enable Chart Quality Filter
							{!isDefault('chart_quality_enabled') && <span className="text-yellow-400 ml-1">*</span>}
						</span>
					</label>
					<div className="text-xs text-[var(--muted)] mt-1 ml-6">
						Recommended: Enabled (filters out low-quality charts)
					</div>
				</div>
				{config.chart_quality_enabled && (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 ml-6">
						<div>
						<label htmlFor="chart_quality_min_score" className="block text-xs sm:text-sm mb-1">
							Min Quality Score
							{!isDefault('chart_quality_min_score') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
							<input
								id="chart_quality_min_score"
								type="number"
								step="0.1"
								min="0"
								max="100"
								value={config.chart_quality_min_score}
								onChange={(e) => onChange({ chart_quality_min_score: parseFloat(e.target.value) || 50 })}
								className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.chart_quality_min_score}</div>
						</div>
						<div>
							<label htmlFor="chart_quality_max_gap_frequency" className="block text-sm mb-1">
								Max Gap Frequency (%)
								{!isDefault('chart_quality_max_gap_frequency') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="chart_quality_max_gap_frequency"
								type="number"
								step="0.1"
								min="0"
								max="100"
								value={config.chart_quality_max_gap_frequency}
								onChange={(e) => onChange({ chart_quality_max_gap_frequency: parseFloat(e.target.value) || 25 })}
								className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.chart_quality_max_gap_frequency}</div>
						</div>
						<div>
							<label htmlFor="chart_quality_min_daily_range_pct" className="block text-sm mb-1">
								Min Daily Range (%)
								{!isDefault('chart_quality_min_daily_range_pct') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="chart_quality_min_daily_range_pct"
								type="number"
								step="0.1"
								min="0"
								max="10"
								value={config.chart_quality_min_daily_range_pct}
								onChange={(e) => onChange({ chart_quality_min_daily_range_pct: parseFloat(e.target.value) || 1.0 })}
								className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.chart_quality_min_daily_range_pct}</div>
						</div>
						<div>
							<label htmlFor="chart_quality_max_extreme_candle_frequency" className="block text-sm mb-1">
								Max Extreme Candle Frequency (%)
								{!isDefault('chart_quality_max_extreme_candle_frequency') && <span className="text-yellow-400 ml-1">*</span>}
							</label>
							<input
								id="chart_quality_max_extreme_candle_frequency"
								type="number"
								step="0.1"
								min="0"
								max="100"
								value={config.chart_quality_max_extreme_candle_frequency}
								onChange={(e) => onChange({ chart_quality_max_extreme_candle_frequency: parseFloat(e.target.value) || 20 })}
								className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
							/>
							<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.chart_quality_max_extreme_candle_frequency}</div>
						</div>
					</div>
				)}
			</div>

			{/* Volume Settings */}
			<div>
				<h3 className="text-xs sm:text-sm font-medium mb-2 sm:mb-3 text-[var(--muted)]">Volume Settings</h3>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
					<div>
						<label htmlFor="min_absolute_avg_volume" className="block text-sm mb-1">
							Min Absolute Avg Volume
							{!isDefault('min_absolute_avg_volume') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="min_absolute_avg_volume"
							type="number"
							min="0"
							value={config.min_absolute_avg_volume}
							onChange={(e) => onChange({ min_absolute_avg_volume: parseInt(e.target.value) || 10000 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.min_absolute_avg_volume.toLocaleString()}</div>
					</div>
					<div>
						<label htmlFor="max_position_volume_ratio" className="block text-sm mb-1">
							Max Position Volume Ratio
							{!isDefault('max_position_volume_ratio') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="max_position_volume_ratio"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.max_position_volume_ratio}
							onChange={(e) => onChange({ max_position_volume_ratio: parseFloat(e.target.value) || 0.1 })}
							className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {(defaultConfig.max_position_volume_ratio * 100).toFixed(0)}%</div>
						<div className="text-xs text-blue-400 mt-1">
							Max {((config.max_position_volume_ratio || 0.1) * 100).toFixed(0)}% of daily volume per position
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
