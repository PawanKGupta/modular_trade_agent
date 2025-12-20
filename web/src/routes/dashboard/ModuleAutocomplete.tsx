import { useEffect, useMemo, useState } from 'react';
import type { ServiceLogEntry } from '@/api/logs';

type Props = {
	logs: ServiceLogEntry[];
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
};

export function ModuleAutocomplete({ logs, value, onChange, placeholder = 'scheduler' }: Props) {
	const [isOpen, setIsOpen] = useState(false);
	const [filteredModules, setFilteredModules] = useState<string[]>([]);

	// Extract unique modules from logs
	const availableModules = useMemo(() => {
		const modules = new Set<string>();
		logs.forEach((log) => {
			if (log.module) {
				modules.add(log.module);
			}
		});
		return Array.from(modules).sort();
	}, [logs]);

	// Filter modules based on input
	useEffect(() => {
		if (!value) {
			setFilteredModules(availableModules.slice(0, 10)); // Show top 10 when empty
		} else {
			const filtered = availableModules
				.filter((module) => module.toLowerCase().includes(value.toLowerCase()))
				.slice(0, 10);
			setFilteredModules(filtered);
		}
	}, [value, availableModules]);

	const handleSelect = (module: string) => {
		onChange(module);
		setIsOpen(false);
	};

	return (
		<div className="relative">
			<input
				type="text"
				value={value}
				onChange={(e) => {
					onChange(e.target.value);
					setIsOpen(true);
				}}
				onFocus={() => setIsOpen(true)}
				onBlur={() => {
					// Delay to allow click on dropdown item
					setTimeout(() => setIsOpen(false), 200);
				}}
				placeholder={placeholder}
				className="bg-[#0f172a] border border-[#1f2937] rounded px-3 py-2 sm:px-2 sm:py-1 min-h-[44px] sm:min-h-0 w-full"
			/>
			{isOpen && filteredModules.length > 0 && (
				<div className="absolute z-20 w-full mt-1 bg-[#0f172a] border border-[#1f2937] rounded shadow-lg max-h-48 overflow-y-auto">
					{filteredModules.map((module) => (
						<button
							key={module}
							type="button"
							onClick={() => handleSelect(module)}
							className="w-full text-left px-3 py-2 text-xs sm:text-sm hover:bg-[#1a2332] transition-colors"
						>
							{module}
						</button>
					))}
				</div>
			)}
		</div>
	);
}
