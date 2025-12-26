import { useMemo, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine } from 'recharts';
import { ChartContainer } from './ChartContainer';
import { ResponsiveChart } from './ResponsiveChart';
import { chartStyles } from './chartStyles';
import { DailyPnl, getDailyPnl } from '@/api/pnl';
import { useQuery } from '@tanstack/react-query';
import { subDays, format } from 'date-fns';

type TimeRange = '7d' | '30d' | '90d' | '1y' | 'all';

interface ChartData {
	name: string;
	pnl: number;
	unrealized?: number;
	realized?: number;
}

interface PnlTrendChartProps {
	height?: number;
	tradeMode?: 'paper' | 'broker';
	includeUnrealized?: boolean;
}

export function PnlTrendChart({ height = 360, tradeMode, includeUnrealized }: PnlTrendChartProps) {
	const [timeRange, setTimeRange] = useState<TimeRange>('30d');
	const [showUnrealized, setShowUnrealized] = useState(false);

	const getDatesForRange = (range: TimeRange) => {
		const today = new Date();
		const endDate = today;
		let startDate = today;

		switch (range) {
			case '7d':
				startDate = subDays(today, 7);
				break;
			case '30d':
				startDate = subDays(today, 30);
				break;
			case '90d':
				startDate = subDays(today, 90);
				break;
			case '1y':
				startDate = subDays(today, 365);
				break;
			case 'all':
				startDate = subDays(today, 1825); // 5 years as default
				break;
		}

		return { startDate, endDate };
	};

	const { startDate, endDate } = getDatesForRange(timeRange);

	const includeUnrealizedEffective = includeUnrealized ?? showUnrealized;

	const { data, isLoading, isError } = useQuery({
		queryKey: ['pnl', 'daily', timeRange, tradeMode, includeUnrealizedEffective],
		queryFn: () => getDailyPnl(startDate, endDate, tradeMode, includeUnrealizedEffective),
	});

	const chartData = useMemo(() => {
		if (!data) return [];

		const cumulative: Record<string, number> = {};
		let runningTotal = 0;

		return data.map((d: DailyPnl) => {
			runningTotal += d.pnl;
			return {
				name: format(new Date(d.date), 'MMM d'),
				pnl: runningTotal,
				dailyPnl: d.pnl,
			};
		});
	}, [data]);

	const stats = useMemo(() => {
		if (!chartData || chartData.length === 0) {
			return { min: 0, max: 0, avg: 0, range: 0 };
		}

		const values = chartData.map((d) => d.pnl);
		const min = Math.min(...values);
		const max = Math.max(...values);
		const avg = values.reduce((a, b) => a + b, 0) / values.length;

		return {
			min: Math.round(min),
			max: Math.round(max),
			avg: Math.round(avg),
			range: max - min,
		};
	}, [chartData]);

	return (
		<ChartContainer title="P&L Trend" height={height}>
			{/* Controls */}
			<div className="flex flex-wrap gap-2 mb-4 p-3 bg-[#0f172a]/50 rounded border border-[#1e293b]">
				<div className="flex gap-1">
					{(['7d', '30d', '90d', '1y', 'all'] as const).map((range) => (
						<button
							key={range}
							onClick={() => setTimeRange(range)}
							className={`px-2 py-1 text-xs rounded transition-colors ${
								timeRange === range
									? 'bg-[var(--accent)] text-white'
									: 'bg-[#1e293b] text-[var(--muted)] hover:bg-[#334155]'
							}`}
						>
							{range}
						</button>
					))}
				</div>
				<div className="flex-1" />
				<label className="flex items-center gap-2 text-xs text-[var(--muted)] cursor-pointer">
					<input
						type="checkbox"
						checked={includeUnrealizedEffective}
						onChange={(e) => setShowUnrealized(e.target.checked)}
						className="w-4 h-4"
					/>
					Show Unrealized
				</label>
			</div>

			{/* Stats */}
			{chartData.length > 0 && (
				<div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4 px-3">
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Min</div>
						<div className="text-sm font-semibold text-red-400">{stats.min.toLocaleString()}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Max</div>
						<div className="text-sm font-semibold text-green-400">{stats.max.toLocaleString()}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Avg</div>
						<div className="text-sm font-semibold text-blue-400">{stats.avg.toLocaleString()}</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Range</div>
						<div className="text-sm font-semibold text-yellow-400">{stats.range.toLocaleString()}</div>
					</div>
				</div>
			)}

			{/* Chart */}
			{isLoading && <div className="text-sm text-[var(--muted)] text-center py-8">Loading chart...</div>}
			{isError && <div className="text-sm text-red-400 text-center py-8">Failed to load chart data</div>}
			{!isLoading && !isError && chartData.length > 0 && (
				<ResponsiveChart height={height}>
					<LineChart data={chartData} margin={{ top: 10, right: 24, left: 8, bottom: 36 }}>
						<CartesianGrid {...chartStyles.grid} />
						<XAxis
							dataKey="name"
							{...chartStyles.axis}
							tickMargin={14}
							minTickGap={10}
							height={32}
							interval="preserveStartEnd"
							tickCount={6}
						/>
						<YAxis {...chartStyles.axis} tickMargin={12} />
						<Tooltip
							{...chartStyles.tooltip}
							formatter={(value: number | undefined) => value ? `₹${value.toLocaleString('en-IN')}` : '-'}
						/>
						<Legend {...chartStyles.legend} />
						<ReferenceLine y={0} stroke="#64748b" strokeDasharray="5 5" />
						<Line
							type="monotone"
							dataKey="pnl"
							stroke="#3b82f6"
							strokeWidth={2}
							dot={false}
							name="Cumulative P&L"
						/>
						{showUnrealized && (
							<Line
								type="monotone"
								dataKey="unrealized"
								stroke="#8b5cf6"
								strokeWidth={1}
								strokeDasharray="5 5"
								dot={false}
								name="Unrealized"
							/>
						)}
					</LineChart>
				</ResponsiveChart>
			)}
			{!isLoading && !isError && chartData.length === 0 && (
				<div className="text-sm text-[var(--muted)] text-center py-8">No data available for this period</div>
			)}
		</ChartContainer>
	);
}
