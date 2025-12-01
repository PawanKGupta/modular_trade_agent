import { CONFIG_PRESETS, type TradingConfig } from '@/api/trading-config';

interface ConfigPresetsProps {
	onApply: (presetConfig: Partial<TradingConfig>) => void;
}

export function ConfigPresets({ onApply }: ConfigPresetsProps) {
	return (
		<div className="bg-[var(--panel)] border border-[#1e293b] rounded-lg p-6">
			<h2 className="text-lg font-semibold mb-4">Configuration Presets</h2>
			<p className="text-sm text-[var(--muted)] mb-4">
				Apply predefined configuration templates. This will update your settings but won't save until you click "Save Changes".
			</p>
			<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
				{CONFIG_PRESETS.map((preset) => (
					<div
						key={preset.id}
						className="p-4 border border-[#1e293b] rounded-lg hover:border-blue-500/50 transition-colors"
					>
						<h3 className="font-medium mb-1">{preset.name}</h3>
						<p className="text-xs text-[var(--muted)] mb-3">{preset.description}</p>
						<button
							onClick={() => onApply(preset.config)}
							className="w-full px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm"
						>
							Apply Preset
						</button>
					</div>
				))}
			</div>
		</div>
	);
}
