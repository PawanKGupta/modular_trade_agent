import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PnlTrendChart } from '../PnlTrendChart';
import * as pnlApi from '@/api/pnl';

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

vi.mock('@/api/pnl', () => ({
	getDailyPnl: vi.fn(),
}));

describe('PnlTrendChart', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(pnlApi.getDailyPnl).mockResolvedValue([
			{ date: '2025-01-01', pnl: 100, realized_pnl: 80, unrealized_pnl: 20, fees: 1, trades_count: 1, symbols: ['INFY'] },
			{ date: '2025-01-02', pnl: -50, realized_pnl: -50, unrealized_pnl: 0, fees: 1, trades_count: 1, symbols: ['TCS'] },
		]);
	});

	it('renders chart with time range controls', async () => {
		render(withProviders(<PnlTrendChart tradeMode="paper" includeUnrealized />));

		await waitFor(() => {
			expect(screen.getByTestId('line-chart')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: '7d' }));
		fireEvent.click(screen.getByRole('button', { name: '90d' }));
		fireEvent.click(screen.getByRole('button', { name: '1y' }));
		fireEvent.click(screen.getByRole('button', { name: 'all' }));

		await waitFor(() => {
			expect(pnlApi.getDailyPnl).toHaveBeenCalled();
		});
	});

	it('shows loading and error states', async () => {
		vi.mocked(pnlApi.getDailyPnl).mockImplementation(() => new Promise(() => {}));
		const { unmount } = render(withProviders(<PnlTrendChart />));
		expect(screen.getByText(/Loading chart/i)).toBeInTheDocument();
		unmount();

		vi.mocked(pnlApi.getDailyPnl).mockRejectedValue(new Error('fail'));
		render(withProviders(<PnlTrendChart />));
		await waitFor(() => {
			expect(screen.getByText(/Failed to load chart data/i)).toBeInTheDocument();
		});
	});

	it('toggles unrealized series when uncontrolled', async () => {
		render(withProviders(<PnlTrendChart />));
		await waitFor(() => expect(screen.getByTestId('line-chart')).toBeInTheDocument());

		const toggle = screen.getByLabelText(/Show Unrealized/i);
		fireEvent.click(toggle);
		await waitFor(() => {
			expect(pnlApi.getDailyPnl).toHaveBeenCalledWith(
				expect.any(Date),
				expect.any(Date),
				undefined,
				true
			);
		});
	});
});
