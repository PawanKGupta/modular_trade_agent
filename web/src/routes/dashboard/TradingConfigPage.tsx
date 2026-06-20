import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, useRef, useCallback, type ReactNode } from 'react';
import { getTradingConfig, updateTradingConfig, resetTradingConfig, type TradingConfig, DEFAULT_CONFIG } from '@/api/trading-config';
import { StrategyConfigSection } from './StrategyConfigSection';
import { RiskConfigSection } from './RiskConfigSection';
import { CapitalConfigSection } from './CapitalConfigSection';
import { OrderConfigSection } from './OrderConfigSection';
import { BehaviorConfigSection } from './BehaviorConfigSection';
import { ConfigPresets } from './ConfigPresets';

type SectionCardProps = {
	id: string;
	icon: string;
	title: string;
	isOpen: boolean;
	onToggle: () => void;
	children: ReactNode;
};

function SectionCard({ id, icon, title, isOpen, onToggle, children }: SectionCardProps) {
	return (
		<div className="rounded-lg border border-[#1e293b] bg-[#0c1521] overflow-hidden transition-shadow hover:shadow-[0_0_0_1px_#334155]">
			<button
				type="button"
				id={`${id}-header`}
				aria-expanded={isOpen}
				aria-controls={`${id}-body`}
				onClick={onToggle}
				className="w-full flex items-center justify-between px-4 py-3.5 text-left gap-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
			>
				<div className="flex items-center gap-3 min-w-0">
					<span className="text-base shrink-0">{icon}</span>
					<span className="font-medium text-sm sm:text-base truncate">{title}</span>
				</div>
				<svg
					className={`w-4 h-4 shrink-0 text-[var(--muted)] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
					viewBox="0 0 20 20"
					fill="currentColor"
					aria-hidden="true"
				>
					<path
						fillRule="evenodd"
						d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
						clipRule="evenodd"
					/>
				</svg>
			</button>
			<div
				id={`${id}-body`}
				role="region"
				aria-labelledby={`${id}-header`}
				className={`transition-all duration-200 ease-in-out ${isOpen ? 'max-h-[9999px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden pointer-events-none'}`}
			>
				<div className="px-4 pb-5 pt-1 border-t border-[#1e293b]">{children}</div>
			</div>
		</div>
	);
}

type SectionKey = 'presets' | 'strategy' | 'capital' | 'risk' | 'order' | 'behavior';

export function TradingConfigPage() {
	const qc = useQueryClient();
	const [hasChanges, setHasChanges] = useState(false);
	const [localConfig, setLocalConfig] = useState<TradingConfig | null>(null);
	const justSavedRef = useRef(false);
	const [openSection, setOpenSection] = useState<SectionKey | ''>('');

	const toggle = useCallback(
		(key: SectionKey) => setOpenSection((prev) => (prev === key ? '' : key)),
		[],
	);

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
		const updates: Record<string, unknown> = {};
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
		return <div className="p-2 sm:p-4 text-xs sm:text-sm">Loading trading configuration...</div>;
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

			<SectionCard id="tc-presets" icon="🗂️" title="Configuration Presets" isOpen={openSection === 'presets'} onToggle={() => toggle('presets')}>
				<ConfigPresets onApply={handlePresetApply} />
			</SectionCard>

			<SectionCard id="tc-strategy" icon="📊" title="Strategy Parameters" isOpen={openSection === 'strategy'} onToggle={() => toggle('strategy')}>
				<StrategyConfigSection
					config={localConfig}
					defaultConfig={DEFAULT_CONFIG}
					onChange={handleConfigChange}
				/>
			</SectionCard>

			<SectionCard id="tc-capital" icon="💰" title="Capital & Position Management" isOpen={openSection === 'capital'} onToggle={() => toggle('capital')}>
				<CapitalConfigSection
					config={localConfig}
					defaultConfig={DEFAULT_CONFIG}
					onChange={handleConfigChange}
				/>
			</SectionCard>

			<SectionCard id="tc-risk" icon="🛡️" title="Risk Management" isOpen={openSection === 'risk'} onToggle={() => toggle('risk')}>
				<RiskConfigSection
					config={localConfig}
					defaultConfig={DEFAULT_CONFIG}
					onChange={handleConfigChange}
				/>
			</SectionCard>

			<SectionCard id="tc-order" icon="📋" title="Order Defaults" isOpen={openSection === 'order'} onToggle={() => toggle('order')}>
				<OrderConfigSection
					config={localConfig}
					defaultConfig={DEFAULT_CONFIG}
					onChange={handleConfigChange}
				/>
			</SectionCard>

			<SectionCard id="tc-behavior" icon="⚡" title="Behavior Settings" isOpen={openSection === 'behavior'} onToggle={() => toggle('behavior')}>
				<BehaviorConfigSection
					config={localConfig}
					defaultConfig={DEFAULT_CONFIG}
					onChange={handleConfigChange}
				/>
			</SectionCard>

			{/* Save button at bottom */}
			{hasChanges && (
				<div className="sticky bottom-2 sm:bottom-4 bg-[var(--panel)] border border-[#1e293b] rounded-lg p-3 sm:p-4 shadow-lg">
					<div className="flex items-center justify-between">
						<span className="text-sm text-yellow-400">You have unsaved changes</span>
						<div className="flex gap-3">
							<button
								onClick={() => {
									setLocalConfig(config!);
									setHasChanges(false);
								}}
								className="px-4 py-3 sm:py-2 rounded bg-gray-600 hover:bg-gray-700 text-white text-sm sm:text-base min-h-[44px] sm:min-h-0"
							>
								Cancel
							</button>
							<button
								onClick={handleSave}
								disabled={updateMutation.isPending}
								className="px-4 py-3 sm:py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 text-sm sm:text-base min-h-[44px] sm:min-h-0"
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
