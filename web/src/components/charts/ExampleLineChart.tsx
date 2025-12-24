import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ChartContainer } from './ChartContainer';
import { ResponsiveChart } from './ResponsiveChart';
import { chartStyles } from './chartStyles';

interface DataPoint {
	name: string;
	value: number;
}

interface ExampleLineChartProps {
	data: DataPoint[];
	title?: string;
	description?: string;
}

/**
 * Example line chart component demonstrating chart usage
 * This can be used as a reference for creating other charts
 */
export function ExampleLineChart({ data, title, description }: ExampleLineChartProps) {
	return (
		<ChartContainer title={title} description={description} height={400}>
			<ResponsiveChart height={400}>
				<LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
					<CartesianGrid {...chartStyles.grid} />
					<XAxis dataKey="name" {...chartStyles.axis} />
					<YAxis {...chartStyles.axis} />
					<Tooltip {...chartStyles.tooltip} />
					<Legend {...chartStyles.legend} />
					<Line
						type="monotone"
						dataKey="value"
						{...chartStyles.line}
						name="Value"
					/>
				</LineChart>
			</ResponsiveChart>
		</ChartContainer>
	);
}

