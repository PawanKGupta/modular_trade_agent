type QuickFilter = {
	label: string;
	apply: () => void;
};

type Props = {
	onFilter: (filter: {
		level?: string;
		startTime?: string;
		endTime?: string;
		daysBack?: number;
	}) => void;
	onClear: () => void;
};

export function QuickFilters({ onFilter, onClear }: Props) {
	const now = new Date();
	const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
	const todayStart = new Date(now);
	todayStart.setHours(0, 0, 0, 0);
	const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

	const filters: QuickFilter[] = [
		{
			label: 'Last Hour',
			apply: () => {
				onFilter({
					startTime: oneHourAgo.toISOString(),
					endTime: now.toISOString(),
				});
			},
		},
		{
			label: 'Errors Only',
			apply: () => {
				onFilter({
					level: 'ERROR',
				});
			},
		},
		{
			label: 'Today',
			apply: () => {
				onFilter({
					startTime: todayStart.toISOString(),
					endTime: now.toISOString(),
				});
			},
		},
		{
			label: 'This Week',
			apply: () => {
				onFilter({
					daysBack: 7,
				});
			},
		},
	];

	return (
		<div className="flex flex-wrap gap-2">
			{filters.map((filter) => (
				<button
					key={filter.label}
					type="button"
					onClick={filter.apply}
					className="px-3 py-1.5 text-xs sm:text-sm bg-[#0f172a] border border-[#1f2937] hover:bg-[#1a2332] text-[var(--muted)] rounded transition-colors"
				>
					{filter.label}
				</button>
			))}
			<button
				type="button"
				onClick={onClear}
				className="px-3 py-1.5 text-xs sm:text-sm bg-red-600/20 border border-red-600/30 hover:bg-red-600/30 text-red-400 rounded transition-colors"
			>
				Clear Filters
			</button>
		</div>
	);
}
