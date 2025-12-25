import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { ChartContainer } from './ChartContainer';
import { ResponsiveChart } from './ResponsiveChart';
import { chartStyles } from './chartStyles';
import { useQuery } from '@tanstack/react-query';
import { getPaperTradingPortfolio } from '@/api/paper-trading';

export function PortfolioValueChart() {
  const { data } = useQuery({
    queryKey: ['portfolio', 'current'],
    queryFn: getPaperTradingPortfolio,
  });

  // Placeholder: the real historical data endpoint isn't implemented yet
  const chartData = data
    ? [
        { name: 'Now', value: data.account.total_value },
      ]
    : [];

  return (
    <ChartContainer title="Portfolio Value" height={360}>
      <ResponsiveChart height={360}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid {...chartStyles.grid} />
          <XAxis dataKey="name" {...chartStyles.axis} />
          <YAxis {...chartStyles.axis} />
          <Tooltip {...chartStyles.tooltip} />
          <Legend {...chartStyles.legend} />
          <Line type="monotone" dataKey="value" {...chartStyles.line} name="Portfolio Value" />
        </LineChart>
      </ResponsiveChart>
    </ChartContainer>
  );
}
