import { type TradingConfig } from '@/api/trading-config';

interface OrderConfigSectionProps {
	config: TradingConfig;
	defaultConfig: TradingConfig;
	onChange: (updates: Partial<TradingConfig>) => void;
}

export function OrderConfigSection({ config, defaultConfig, onChange }: OrderConfigSectionProps) {
	const isDefault = (key: keyof TradingConfig) => config[key] === defaultConfig[key];

	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-6">
			<h2 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Order Defaults</h2>

			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
				<div>
					<label htmlFor="default_exchange" className="block text-xs sm:text-sm mb-1">
						Default Exchange
						{!isDefault('default_exchange') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<select
						id="default_exchange"
						value={config.default_exchange}
						onChange={(e) => onChange({ default_exchange: e.target.value as 'NSE' | 'BSE' })}
						className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="NSE">NSE</option>
						<option value="BSE">BSE</option>
					</select>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.default_exchange}</div>
				</div>
				<div>
					<label htmlFor="default_product" className="block text-sm mb-1">
						Default Product
						{!isDefault('default_product') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<select
						id="default_product"
						value={config.default_product}
						onChange={(e) => onChange({ default_product: e.target.value as 'CNC' | 'MIS' | 'NRML' })}
						className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="CNC">CNC (Cash & Carry)</option>
						<option value="MIS">MIS (Margin Intraday)</option>
						<option value="NRML">NRML (Normal)</option>
					</select>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.default_product}</div>
				</div>
				<div>
					<label htmlFor="default_order_type" className="block text-sm mb-1">
						Default Order Type
						{!isDefault('default_order_type') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<select
						id="default_order_type"
						value={config.default_order_type}
						onChange={(e) => onChange({ default_order_type: e.target.value as 'MARKET' | 'LIMIT' })}
						className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="MARKET">MARKET</option>
						<option value="LIMIT">LIMIT</option>
					</select>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.default_order_type}</div>
				</div>
				<div>
					<label htmlFor="default_variety" className="block text-sm mb-1">
						Default Variety
						{!isDefault('default_variety') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<select
						id="default_variety"
						value={config.default_variety}
						onChange={(e) => onChange({ default_variety: e.target.value as 'AMO' | 'REGULAR' })}
						className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="AMO">AMO (After Market Order)</option>
						<option value="REGULAR">REGULAR</option>
					</select>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.default_variety}</div>
				</div>
				<div>
					<label htmlFor="default_validity" className="block text-sm mb-1">
						Default Validity
						{!isDefault('default_validity') && <span className="text-yellow-400 ml-1">*</span>}
					</label>
					<select
						id="default_validity"
						value={config.default_validity}
						onChange={(e) => onChange({ default_validity: e.target.value as 'DAY' | 'IOC' | 'GTC' })}
						className="w-full px-3 py-2 sm:p-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm min-h-[44px] sm:min-h-0"
					>
						<option value="DAY">DAY</option>
						<option value="IOC">IOC (Immediate or Cancel)</option>
						<option value="GTC">GTC (Good Till Cancel)</option>
					</select>
					<div className="text-xs text-[var(--muted)] mt-1">Default: {defaultConfig.default_validity}</div>
				</div>
			</div>
		</div>
	);
}
