import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, useRef } from 'react';
import { getTradingConfig, updateTradingConfig, resetTradingConfig, type TradingConfig, DEFAULT_CONFIG } from '@/api/trading-config';
import { StrategyConfigSection } from './StrategyConfigSection';
import { RiskConfigSection } from './RiskConfigSection';
import { CapitalConfigSection } from './CapitalConfigSection';
import { OrderConfigSection } from './OrderConfigSection';
import { BehaviorConfigSection } from './BehaviorConfigSection';
import { ConfigPresets } from './ConfigPresets';

export function TradingConfigPage() {
	const qc = useQueryClient();
	const [hasChanges, setHasChanges] = useState(false);
	const [localConfig, setLocalConfig] = useState<TradingConfig | null>(null);
	const justSavedRef = useRef(false);

	const { data: config, isLoading } = useQuery<TradingConfig>({
		queryKey: ['tradingConfig'],
		queryFn: getTradingConfig,
	});

	const updateMutation = useMutation({
		mutationFn: updateTradingConfig,
		onSuccess: (updatedConfig) => {
			// Immediately update localConfig with the response to avoid stale comparisons
			setLocalConfig(updatedConfig);
			setHasChanges(false);
			justSavedRef.current = true;
			// Update query cache directly to avoid refetch race condition
			qc.setQueryData(['tradingConfig'], updatedConfig);
			// Still invalidate for background refresh
			qc.invalidateQueries({ queryKey: ['tradingConfig'] });
		},
	});

	const resetMutation = useMutation({
		mutationFn: resetTradingConfig,
		onSuccess: (resetConfig) => {
			// Update localConfig immediately with the server response
			setLocalConfig(resetConfig);
			setHasChanges(false);
			// Invalidate query to refetch in background (for consistency check)
			qc.invalidateQueries({ queryKey: ['tradingConfig'] });
		},
	});

	useEffect(() => {
		document.title = 'Trading Configuration';
	}, []);

	useEffect(() => {
		if (config) {
			// Skip updating localConfig if we just saved (to avoid overwriting with stale refetch)
			if (justSavedRef.current) {
				justSavedRef.current = false;
				return;
			}
			setLocalConfig(config);
			setHasChanges(false); // Config from server is always "saved"
		}
	}, [config]);

	const handleConfigChange = (updates: Partial<TradingConfig>) => {
		if (!localConfig) return;
		setLocalConfig({ ...localConfig, ...updates });
		setHasChanges(true);
	};

	const handleSave = () => {
		if (!localConfig || !config) return;
		const updates: Record<string, any> = {};
		// Only include changed fields
		Object.keys(localConfig).forEach((key) => {
			const typedKey = key as keyof TradingConfig;
			const localValue = localConfig[typedKey];
			const configValue = config[typedKey];
			// Handle null/undefined comparison
			if (localValue !== configValue && (localValue !== null || configValue !== null)) {
				// Convert null to undefined for optional fields
				updates[typedKey] = localValue === null ? undefined : localValue;
			}
		});
		if (Object.keys(updates).length > 0) {
			updateMutation.mutate(updates);
		}
	};

	const handleReset = () => {
		if (confirm('Are you sure you want to reset all configuration to defaults? This cannot be undone.')) {
			resetMutation.mutate();
		}
	};

	const handlePresetApply = (presetConfig: Partial<TradingConfig>) => {
		if (!localConfig) return;
		setLocalConfig({ ...localConfig, ...presetConfig });
		setHasChanges(true);
	};

	if (isLoading || !localConfig) {
		return <div className="p-4">Loading trading configuration...</div>;
	}

	return (
		<div className="p-2 sm:p-4 space-y-4 sm:space-y-6 max-w-6xl">
			<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
				<h1 className="text-lg sm:text-xl font-semibold">Trading Configuration</h1>
				<div className="flex flex-col sm:flex-row gap-2 sm:gap-3 w-full sm:w-auto">
					{hasChanges && (
						<span className="text-xs sm:text-sm text-yellow-400 self-center">Unsaved changes</span>
					)}
					<button
						onClick={handleReset}
						disabled={resetMutation.isPending}
						className="px-4 py-3 sm:py-2 rounded bg-gray-600 hover:bg-gray-700 text-white disabled:opacity-50 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
					>
						{resetMutation.isPending ? 'Resetting...' : 'Reset to Defaults'}
					</button>
					<button
						onClick={handleSave}
						disabled={!hasChanges || updateMutation.isPending}
						className="px-4 py-3 sm:py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 min-h-[44px] sm:min-h-0 text-sm sm:text-base"
					>
						{updateMutation.isPending ? 'Saving...' : 'Save Changes'}
					</button>
				</div>
			</div>

			{/* Configuration Presets */}
			<ConfigPresets onApply={handlePresetApply} />

			{/* Strategy Parameters Section */}
			<StrategyConfigSection
				config={localConfig}
				defaultConfig={DEFAULT_CONFIG}
				onChange={handleConfigChange}
			/>

			{/* Capital & Position Management Section */}
			<CapitalConfigSection
				config={localConfig}
				defaultConfig={DEFAULT_CONFIG}
				onChange={handleConfigChange}
			/>

			{/* Risk Management Section */}
			<RiskConfigSection
				config={localConfig}
				defaultConfig={DEFAULT_CONFIG}
				onChange={handleConfigChange}
			/>

			{/* Order Defaults Section */}
			<OrderConfigSection
				config={localConfig}
				defaultConfig={DEFAULT_CONFIG}
				onChange={handleConfigChange}
			/>

			{/* Behavior Settings Section */}
			<BehaviorConfigSection
				config={localConfig}
				defaultConfig={DEFAULT_CONFIG}
				onChange={handleConfigChange}
			/>

			{/* Save button at bottom */}
			{hasChanges && (
				<div className="sticky bottom-4 bg-[var(--panel)] border border-[#1e293b] rounded-lg p-4 shadow-lg">
					<div className="flex items-center justify-between">
						<span className="text-sm text-yellow-400">You have unsaved changes</span>
						<div className="flex gap-3">
							<button
								onClick={() => {
									setLocalConfig(config!);
									setHasChanges(false);
								}}
								className="px-4 py-2 rounded bg-gray-600 hover:bg-gray-700 text-white"
							>
								Cancel
							</button>
							<button
								onClick={handleSave}
								disabled={updateMutation.isPending}
								className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
							>
								{updateMutation.isPending ? 'Saving...' : 'Save Changes'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
