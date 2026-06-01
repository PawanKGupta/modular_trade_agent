import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PortfolioValueChart } from '../PortfolioValueChart';
import * as portfolioApi from '@/api/portfolio';

vi.mock('recharts', () => ({
	ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
	Line: () => null,
	XAxis: () => null,
	YAxis: () => null,
	CartesianGrid: () => null,
	Tooltip: () => null,
	Legend: () => null,
	ReferenceLine: () => null,
}));

vi.mock('@/api/portfolio', () => ({
	getPortfolioHistory: vi.fn(),
}));

describe('PortfolioValueChart', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(portfolioApi.getPortfolioHistory).mockResolvedValue([
			{
				date: '2025-01-01',
				total_value: 100000,
				available_cash: 50000,
				invested_value: 50000,
				unrealized_pnl: 1000,
				realized_pnl: 500,
			},
			{
				date: '2025-01-02',
				total_value: 101000,
				available_cash: 49000,
				invested_value: 52000,
				unrealized_pnl: 1500,
				realized_pnl: 600,
			},
		]);
	});

	it('renders portfolio value chart with range controls', async () => {
		render(withProviders(<PortfolioValueChart />));

		await waitFor(() => {
			expect(screen.getByTestId('line-chart')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: '7d' }));
		fireEvent.click(screen.getByRole('button', { name: '30d' }));
		fireEvent.click(screen.getByRole('button', { name: '90d' }));
		fireEvent.click(screen.getByRole('button', { name: '1y' }));
		fireEvent.click(screen.getByRole('button', { name: 'all' }));
	});

	it('shows loading and error states', async () => {
		vi.mocked(portfolioApi.getPortfolioHistory).mockImplementation(() => new Promise(() => {}));
		const { unmount } = render(withProviders(<PortfolioValueChart />));
		expect(screen.getByText(/Loading chart/i)).toBeInTheDocument();
		unmount();

		vi.mocked(portfolioApi.getPortfolioHistory).mockRejectedValue(new Error('fail'));
		render(withProviders(<PortfolioValueChart />));
		await waitFor(() => {
			expect(screen.getByText(/Failed to load chart data/i)).toBeInTheDocument();
		});
	});

	it('shows empty state when history returns no rows', async () => {
		vi.mocked(portfolioApi.getPortfolioHistory).mockResolvedValue([]);
		render(withProviders(<PortfolioValueChart />));
		await waitFor(() => {
			expect(screen.getByText(/No data available for this period/i)).toBeInTheDocument();
		});
	});
});
