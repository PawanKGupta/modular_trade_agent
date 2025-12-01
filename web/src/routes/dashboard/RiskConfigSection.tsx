import { type TradingConfig } from '@/api/trading-config';

interface RiskConfigSectionProps {
	config: TradingConfig;
	defaultConfig: TradingConfig;
	onChange: (updates: Partial<TradingConfig>) => void;
}

export function RiskConfigSection({ config, defaultConfig, onChange }: RiskConfigSectionProps) {
	const isDefault = (key: keyof TradingConfig) => {
		const configVal = config[key];
		const defaultVal = defaultConfig[key];
		return configVal === defaultVal || (configVal === null && defaultVal === null);
	};

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
			<h2 className="text-lg font-semibold mb-4">Risk Management</h2>

			{/* Stop Loss Configuration */}
			<div className="mb-6">
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">Stop Loss Percentages</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div>
						<label htmlFor="min_stop_loss_pct" className="block text-sm mb-1">
							Min Stop Loss (%)
							{!isDefault('min_stop_loss_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="min_stop_loss_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.min_stop_loss_pct ?? ''}
							onChange={(e) => onChange({ min_stop_loss_pct: e.target.value ? parseFloat(e.target.value) : null })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							placeholder="0.03"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">
							Default: {defaultConfig.min_stop_loss_pct ? `${(defaultConfig.min_stop_loss_pct * 100).toFixed(0)}%` : 'None'}
						</div>
					</div>
					<div>
						<label htmlFor="tight_stop_loss_pct" className="block text-sm mb-1">
							Tight Stop Loss (%)
							{!isDefault('tight_stop_loss_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="tight_stop_loss_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.tight_stop_loss_pct ?? ''}
							onChange={(e) => onChange({ tight_stop_loss_pct: e.target.value ? parseFloat(e.target.value) : null })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							placeholder="0.06"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">
							Default: {defaultConfig.tight_stop_loss_pct ? `${(defaultConfig.tight_stop_loss_pct * 100).toFixed(0)}%` : 'None'}
						</div>
					</div>
					<div>
						<label htmlFor="default_stop_loss_pct" className="block text-sm mb-1">
							Default Stop Loss (%)
							{!isDefault('default_stop_loss_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="default_stop_loss_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.default_stop_loss_pct ?? ''}
							onChange={(e) => onChange({ default_stop_loss_pct: e.target.value ? parseFloat(e.target.value) : null })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
							placeholder="0.08"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">
							Default: {defaultConfig.default_stop_loss_pct ? `${(defaultConfig.default_stop_loss_pct * 100).toFixed(0)}%` : 'None'}
						</div>
						<div className="text-xs text-red-400 mt-1">
							Must be &gt; Tight ({config.tight_stop_loss_pct ? `${(config.tight_stop_loss_pct * 100).toFixed(0)}%` : 'N/A'})
						</div>
					</div>
				</div>
			</div>

			{/* Target Percentages */}
			<div className="mb-6">
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">Target Percentages</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div>
						<label htmlFor="default_target_pct" className="block text-sm mb-1">
							Default Target (%)
							{!isDefault('default_target_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="default_target_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.default_target_pct}
							onChange={(e) => onChange({ default_target_pct: parseFloat(e.target.value) || 0.1 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {(defaultConfig.default_target_pct * 100).toFixed(0)}%</div>
					</div>
					<div>
						<label htmlFor="strong_buy_target_pct" className="block text-sm mb-1">
							Strong Buy Target (%)
							{!isDefault('strong_buy_target_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="strong_buy_target_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.strong_buy_target_pct}
							onChange={(e) => onChange({ strong_buy_target_pct: parseFloat(e.target.value) || 0.12 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {(defaultConfig.strong_buy_target_pct * 100).toFixed(0)}%</div>
					</div>
					<div>
						<label htmlFor="excellent_target_pct" className="block text-sm mb-1">
							Excellent Target (%)
							{!isDefault('excellent_target_pct') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="excellent_target_pct"
							type="number"
							step="0.01"
							min="0"
							max="1"
							value={config.excellent_target_pct}
							onChange={(e) => onChange({ excellent_target_pct: parseFloat(e.target.value) || 0.15 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {(defaultConfig.excellent_target_pct * 100).toFixed(0)}%</div>
					</div>
				</div>
			</div>

			{/* Risk-Reward Ratios */}
			<div>
				<h3 className="text-sm font-medium mb-3 text-[var(--muted)]">Risk-Reward Ratios</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div>
						<label htmlFor="buy_risk_reward" className="block text-sm mb-1">
							Buy Risk-Reward
							{!isDefault('buy_risk_reward') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="buy_risk_reward"
							type="number"
							step="0.1"
							min="0"
							value={config.buy_risk_reward}
							onChange={(e) => onChange({ buy_risk_reward: parseFloat(e.target.value) || 2.5 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.buy_risk_reward}</div>
					</div>
					<div>
						<label htmlFor="strong_buy_risk_reward" className="block text-sm mb-1">
							Strong Buy Risk-Reward
							{!isDefault('strong_buy_risk_reward') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="strong_buy_risk_reward"
							type="number"
							step="0.1"
							min="0"
							value={config.strong_buy_risk_reward}
							onChange={(e) => onChange({ strong_buy_risk_reward: parseFloat(e.target.value) || 3.0 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.strong_buy_risk_reward}</div>
					</div>
					<div>
						<label htmlFor="excellent_risk_reward" className="block text-sm mb-1">
							Excellent Risk-Reward
							{!isDefault('excellent_risk_reward') && <span className="text-yellow-400 ml-1">*</span>}
						</label>
						<input
							id="excellent_risk_reward"
							type="number"
							step="0.1"
							min="0"
							value={config.excellent_risk_reward}
							onChange={(e) => onChange({ excellent_risk_reward: parseFloat(e.target.value) || 3.5 })}
							className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
						/>
						<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.excellent_risk_reward}</div>
					</div>
				</div>
			</div>
		</div>
	);
}
