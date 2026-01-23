import { useMemo, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine } from 'recharts';
import { ChartContainer } from './ChartContainer';
import { ResponsiveChart } from './ResponsiveChart';
import { chartStyles } from './chartStyles';
import { useQuery } from '@tanstack/react-query';
import { getPortfolioHistory } from '@/api/portfolio';
import { subDays, format } from 'date-fns';

type TimeRange = '7d' | '30d' | '90d' | '1y' | 'all';

interface PortfolioValueChartProps {
	height?: number;
}

export function PortfolioValueChart({ height = 360 }: PortfolioValueChartProps) {
	const [timeRange, setTimeRange] = useState<TimeRange>('30d');

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

	const { data, isLoading, isError } = useQuery({
		queryKey: ['portfolio', 'history', timeRange],
		queryFn: () => getPortfolioHistory(startDate, endDate, 500),
	});

	const chartData = useMemo(() => {
		if (!data || data.length === 0) return [];

		// Get initial capital from first snapshot
		const initialCapital = data[0]?.invested_value || 0;

		return data.map((snapshot) => ({
			name: format(new Date(snapshot.date), 'MMM d'),
			value: snapshot.total_value,
			initialCapital: initialCapital,
			returnPct: initialCapital > 0 ? ((snapshot.total_value - initialCapital) / initialCapital) * 100 : 0,
			cash: snapshot.available_cash,
			invested: snapshot.invested_value,
			unrealized: snapshot.unrealized_pnl,
			realized: snapshot.realized_pnl,
		}));
	}, [data]);

	const stats = useMemo(() => {
		if (!chartData || chartData.length === 0) {
			return { min: 0, max: 0, current: 0, initialCapital: 0, totalReturn: 0 };
		}

		const values = chartData.map((d) => d.value);
		const min = Math.min(...values);
		const max = Math.max(...values);
		const current = values[values.length - 1];
		const initialCapital = chartData[0]?.initialCapital || 0;
		const totalReturn = initialCapital > 0 ? ((current - initialCapital) / initialCapital) * 100 : 0;

		return {
			min: Math.round(min),
			max: Math.round(max),
			current: Math.round(current),
			initialCapital: Math.round(initialCapital),
			totalReturn: Math.round(totalReturn * 100) / 100,
		};
	}, [chartData]);

	return (
		<ChartContainer title="Portfolio Value" height={height}>
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
			</div>

			{/* Stats */}
			{chartData.length > 0 && (
				<div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4 px-3">
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Initial Capital</div>
						<div className="text-sm font-semibold text-blue-400">
							₹{stats.initialCapital.toLocaleString('en-IN')}
						</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Current Value</div>
						<div className="text-sm font-semibold text-green-400">
							₹{stats.current.toLocaleString('en-IN')}
						</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Total Return</div>
						<div
							className={`text-sm font-semibold ${
								stats.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{stats.totalReturn >= 0 ? '+' : ''}{stats.totalReturn.toFixed(2)}%
						</div>
					</div>
					<div className="bg-[#0f172a]/50 p-2 rounded border border-[#1e293b]">
						<div className="text-xs text-[var(--muted)]">Range</div>
						<div className="text-sm font-semibold text-yellow-400">
							₹{(stats.max - stats.min).toLocaleString('en-IN')}
						</div>
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
						{chartData.length > 0 && (
							<ReferenceLine
								y={chartData[0]?.initialCapital}
								stroke="#64748b"
								strokeDasharray="5 5"
								name="Initial Capital"
							/>
						)}
						<Line
							type="monotone"
							dataKey="value"
							stroke="#3b82f6"
							strokeWidth={2}
							dot={false}
							name="Portfolio Value"
						/>
					</LineChart>
				</ResponsiveChart>
			)}
			{!isLoading && !isError && chartData.length === 0 && (
				<div className="text-sm text-[var(--muted)] text-center py-8">No data available for this period</div>
			)}
		</ChartContainer>
	);
}
