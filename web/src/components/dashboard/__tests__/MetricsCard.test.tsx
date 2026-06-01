import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { MetricsCard } from '../MetricsCard';
import * as metricsApi from '@/api/metrics';

vi.mock('@/api/metrics', () => ({
	getDashboardMetrics: vi.fn(),
}));

const sampleMetrics = {
	total_trades: 12,
	win_rate: 66.7,
	total_realized_pnl: 5000,
	days_traded: 8,
	profitable_trades: 8,
	losing_trades: 4,
	average_profit_per_trade: 625,
	avg_holding_period_days: 3,
	best_trade_profit: 1200,
	best_trade_symbol: 'INFY',
	worst_trade_loss: -400,
	worst_trade_symbol: 'TCS',
};

describe('MetricsCard', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(metricsApi.getDashboardMetrics).mockResolvedValue(sampleMetrics);
	});

	it('renders metrics after loading', async () => {
		render(withProviders(<MetricsCard periodDays={30} tradeMode="paper" />));

		await waitFor(() => {
			expect(screen.getByText('Trading Metrics (30d)')).toBeInTheDocument();
			expect(screen.getByText('12')).toBeInTheDocument();
			expect(screen.getByText('66.7%')).toBeInTheDocument();
		});
	});

	it('shows error state when query fails', async () => {
		vi.mocked(metricsApi.getDashboardMetrics).mockRejectedValue(new Error('fail'));
		render(withProviders(<MetricsCard />));

		await waitFor(() => {
			expect(screen.getByText('Failed to load metrics')).toBeInTheDocument();
		});
	});
});
