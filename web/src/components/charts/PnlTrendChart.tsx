import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ChartContainer } from './ChartContainer';
import { ResponsiveChart } from './ResponsiveChart';
import { chartStyles } from './chartStyles';
import { DailyPnl, getDailyPnl } from '@/api/pnl';
import { useQuery } from '@tanstack/react-query';

export function PnlTrendChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['pnl', 'daily', '30d'],
    queryFn: () => getDailyPnl(),
  });

  const chartData = (data || []).map((d: DailyPnl) => ({ name: d.date, pnl: d.pnl }));

  return (
    <ChartContainer title="P&L Trend" height={360}>
      <ResponsiveChart height={360}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid {...chartStyles.grid} />
          <XAxis dataKey="name" {...chartStyles.axis} />
          <YAxis {...chartStyles.axis} />
          <Tooltip {...chartStyles.tooltip} />
          <Legend {...chartStyles.legend} />
          <Line type="monotone" dataKey="pnl" {...chartStyles.line} name="P&L" />
        </LineChart>
      </ResponsiveChart>
    </ChartContainer>
  );
}
