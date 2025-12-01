import { type TradingConfig } from '@/api/trading-config';

interface CapitalConfigSectionProps {
	config: TradingConfig;
	defaultConfig: TradingConfig;
	onChange: (updates: Partial<TradingConfig>) => void;
}

export function CapitalConfigSection({ config, defaultConfig, onChange }: CapitalConfigSectionProps) {
	const isDefault = (key: keyof TradingConfig) => config[key] === defaultConfig[key];

	const maxPositionsChange = config.max_portfolio_size - defaultConfig.max_portfolio_size;
	const capitalChange = config.user_capital - defaultConfig.user_capital;
	const paperCapitalChange = config.paper_trading_initial_capital - (defaultConfig.paper_trading_initial_capital ?? 300000);

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
			<h2 className="text-lg font-semibold mb-4">Capital & Position Management</h2>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label htmlFor="user_capital" className="block text-sm mb-1">
						Capital per Trade (Rs )
						{!isDefault('user_capital') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<input
						id="user_capital"
						type="number"
						step="1000"
						min="0"
						value={config.user_capital}
						onChange={(e) => onChange({ user_capital: parseFloat(e.target.value) || 200000 })}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
					/>
					<div className="text-xs text-[var(--muted)] mt-1">
						Default: Rs {defaultConfig.user_capital.toLocaleString('en-IN')}
					</div>
					{capitalChange !== 0 && (
						<div className={`text-xs mt-1 ${capitalChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
							{capitalChange > 0 ? '+' : ''}Rs {Math.abs(capitalChange).toLocaleString('en-IN')} from default
						</div>
					)}
				</div>
				<div>
					<label htmlFor="paper_trading_initial_capital" className="block text-sm mb-1">
						Paper Trading Initial Capital (Rs )
						{!isDefault('paper_trading_initial_capital') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<input
						id="paper_trading_initial_capital"
						type="number"
						step="10000"
						min="0"
						value={config.paper_trading_initial_capital ?? 300000}
						onChange={(e) => onChange({ paper_trading_initial_capital: parseFloat(e.target.value) || 300000 })}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
					/>
					<div className="text-xs text-[var(--muted)] mt-1">
						Default: Rs {(defaultConfig.paper_trading_initial_capital ?? 300000).toLocaleString('en-IN')}
					</div>
					{paperCapitalChange !== 0 && (
						<div className={`text-xs mt-1 ${paperCapitalChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
							{paperCapitalChange > 0 ? '+' : ''}Rs {Math.abs(paperCapitalChange).toLocaleString('en-IN')} from default
						</div>
					)}
					<div className="text-xs text-blue-400 mt-1">
						💡 Starting balance for paper trading simulation
					</div>
				</div>
			</div>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
				<div>
					<label htmlFor="max_portfolio_size" className="block text-sm mb-1">
						Max Portfolio Size
						{!isDefault('max_portfolio_size') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<input
						id="max_portfolio_size"
						type="number"
						min="1"
						max="20"
						value={config.max_portfolio_size}
						onChange={(e) => onChange({ max_portfolio_size: parseInt(e.target.value) || 6 })}
						className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]"
					/>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.max_portfolio_size}</div>
					{maxPositionsChange !== 0 && (
						<div className={`text-xs mt-1 ${maxPositionsChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
							{maxPositionsChange > 0 ? '+' : ''}{maxPositionsChange} positions from default
							{maxPositionsChange > 0 && (
								<span className="text-blue-400 ml-1">
									(Allows {maxPositionsChange} more concurrent position{maxPositionsChange > 1 ? 's' : ''})
								</span>
							)}
						</div>
					)}
				</div>
			</div>

			{/* Impact Summary */}
			{maxPositionsChange !== 0 && (
				<div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded">
					<div className="text-sm font-medium text-blue-400 mb-1">Configuration Impact</div>
					<div className="text-xs text-blue-300">
						With max portfolio size of {config.max_portfolio_size}, you can hold up to {config.max_portfolio_size} positions
						concurrently. Total capital allocation: Rs {(config.user_capital * config.max_portfolio_size).toLocaleString('en-IN')}
					</div>
				</div>
			)}
		</div>
	);
}
